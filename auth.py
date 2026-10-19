"""
auth.py
=======
Authentication module — Register, Login, OTP, Password Reset
"""

import os
import re
import random
import string
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request,
                   redirect, url_for, flash, session, jsonify)
from flask_bcrypt import Bcrypt
from flask_login import (LoginManager, UserMixin,
                         login_user, logout_user,
                         login_required, current_user)
from database import get_db, execute

# ── Blueprint & extensions ──────────────────────────────────────
auth_bp = Blueprint("auth", __name__)
bcrypt = Bcrypt()
login_manager = LoginManager()


# ── User model ──────────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.full_name = row["full_name"]
        self.email = row["email"]
        self.is_verified = bool(row["is_verified"])
        self.is_admin = bool(row["is_admin"])
        self.created_at = row["created_at"]

    @staticmethod
    def get(user_id):
        row = execute(
            "SELECT * FROM users WHERE id=?",
            (user_id,), fetchone=True)
        return User(row) if row else None

    @staticmethod
    def get_by_email(email):
        return execute(
            "SELECT * FROM users WHERE email=?",
            (email.lower().strip(),), fetchone=True)


@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    flash("Please log in to access this page.", "warning")
    return redirect(url_for("auth.login"))


# ── Helpers ─────────────────────────────────────────────────────
def generate_otp(length=6):
    return "".join(random.choices(string.digits, k=length))


def is_valid_email(email):
    return re.match(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def is_strong_password(pwd):
    return (len(pwd) >= 8 and
            re.search(r"[A-Z]", pwd) and
            re.search(r"[a-z]", pwd) and
            re.search(r"\d",    pwd))


def send_otp(email, otp, purpose="verify"):
    import smtplib, ssl
    from email.mime.text import MIMEText
    from flask import current_app
    subject = "Your ScholarPredict Verification Code" if purpose == "verify" else "Your ScholarPredict Password Reset Code"
    body = f"Hi,\n\nYour one-time verification code is: {otp}\n\nThis code expires in 15 minutes.\n\n- ScholarPredict Team"
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls(context=ctx)
            s.login(current_app.config["MAIL_USERNAME"], current_app.config["MAIL_PASSWORD"])
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = current_app.config["MAIL_USERNAME"]
            msg["To"] = email
            s.sendmail(current_app.config["MAIL_USERNAME"], email, msg.as_string())
        print(f"[MAIL SENT] OTP sent to {email}")
    except Exception as e:
        print(f"[MAIL ERROR] {e}")
        pass  # fallback: check terminal for OTP


def save_otp(email, otp, purpose="verify", minutes=15):
    expires = (datetime.utcnow() +
               timedelta(minutes=minutes)).isoformat()
    execute(
        "UPDATE otp_codes SET used=1 "
        "WHERE email=? AND purpose=? AND used=0",
        (email, purpose), commit=True)
    execute(
        "INSERT INTO otp_codes "
        "(email, otp, purpose, expires_at) "
        "VALUES (?, ?, ?, ?)",
        (email, otp, purpose, expires), commit=True)


def verify_otp_code(email, otp_input, purpose="verify"):
    row = execute(
        "SELECT * FROM otp_codes "
        "WHERE email=? AND purpose=? AND used=0 "
        "ORDER BY id DESC LIMIT 1",
        (email, purpose), fetchone=True)

    if not row:
        return False, "OTP not found. Please request a new one."
    if datetime.utcnow().isoformat() > row["expires_at"]:
        return False, "OTP has expired. Please request a new one."
    if row["otp"] != otp_input.strip():
        return False, "Incorrect OTP. Please try again."

    execute("UPDATE otp_codes SET used=1 WHERE id=?",
            (row["id"],), commit=True)
    return True, "OK"


# ══════════════════════════════════════════════════════════════
# REGISTER
# ══════════════════════════════════════════════════════════════
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("welcome"))

    errors = {}
    form = {}

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        form = {"full_name": full_name, "email": email}

        if not full_name or len(full_name) < 2:
            errors["full_name"] = \
                "Full name must be at least 2 characters."
        if not is_valid_email(email):
            errors["email"] = \
                "Please enter a valid email address."
        elif execute("SELECT id FROM users WHERE email=?",
                     (email,), fetchone=True):
            errors["email"] = \
                "An account with this email already exists."
        if not is_strong_password(password):
            errors["password"] = (
                "Password must be at least 8 characters "
                "with uppercase, lowercase, and a number.")
        if password != confirm:
            errors["confirm_password"] = \
                "Passwords do not match."

        if not errors:
            session["pending_register"] = {
                "full_name": full_name,
                "email":     email,
                "password":  password,
            }
            otp = generate_otp()
            save_otp(email, otp, purpose="verify")
            send_otp(email, otp, purpose="verify")
            flash("A verification code has been sent "
                  "to your email.", "info")
            return redirect(url_for("auth.verify_otp_page"))

    return render_template(
        "auth/register.html", errors=errors, form=form)


# ── OTP Verification ─────────────────────────────────────────
@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp_page():
    pending = session.get("pending_register")
    if not pending:
        return redirect(url_for("auth.register"))

    error = None
    if request.method == "POST":
        otp_input = request.form.get("otp", "").strip()
        ok, msg = verify_otp_code(
            pending["email"], otp_input, purpose="verify")

        if ok:
            pw_hash = bcrypt.generate_password_hash(
                pending["password"]).decode("utf-8")
            execute(
                "INSERT INTO users "
                "(full_name, email, password_hash, is_verified) "
                "VALUES (?, ?, ?, 1)",
                (pending["full_name"],
                 pending["email"], pw_hash),
                commit=True)
            session.pop("pending_register", None)
            flash("Account created! Please log in.", "success")
            return redirect(url_for("auth.login"))
        else:
            error = msg

    demo_otp = session.get("demo_otp_verify", "")
    return render_template(
        "auth/verify_otp.html",
        email=pending["email"],
        error=error,
        demo_otp=demo_otp)


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    pending = session.get("pending_register", {})
    email = pending.get("email", "")
    purpose = request.form.get("purpose", "verify")
    if email:
        otp = generate_otp()
        save_otp(email, otp, purpose=purpose)
        send_otp(email, otp, purpose=purpose)
        return jsonify({"ok": True,
                        "message": "OTP resent successfully."})
    return jsonify({"ok": False,
                    "message": "Email not found."}), 400


# ══════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("welcome"))

    error = None
    form = {}

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember_me"))
        form = {"email": email}

        row = User.get_by_email(email)
        if not row:
            error = "No account found with this email address."
        elif not bcrypt.check_password_hash(
                row["password_hash"], password):
            error = "Incorrect password. Please try again."
        elif not row["is_verified"]:
            error = ("Email not verified. "
                     "Please check your inbox.")
        else:
            user = User(row)
            login_user(user, remember=remember)
            next_page = (request.args.get("next") or
                         url_for("academic"))
            flash(f"Welcome back, "
                  f"{user.full_name.split()[0]}!", "success")
            return redirect(next_page)

    return render_template(
        "auth/login.html", error=error, form=form)


# ══════════════════════════════════════════════════════════════
# LOGOUT
# ══════════════════════════════════════════════════════════════
@auth_bp.route("/logout")
@login_required
def logout():
    name = current_user.full_name.split()[0]
    logout_user()
    flash(f"Goodbye, {name}. You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ══════════════════════════════════════════════════════════════
# FORGOT PASSWORD
# ══════════════════════════════════════════════════════════════
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        row = execute(
            "SELECT * FROM users WHERE email=?",
            (email,), fetchone=True)
        if row:
            otp = generate_otp()
            save_otp(email, otp, purpose="reset")
            send_otp(email, otp, purpose="reset")
            session["reset_email"] = email
        flash("If that email exists, "
              "a reset code has been sent.", "info")
        return redirect(url_for("auth.reset_otp"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-otp", methods=["GET", "POST"])
def reset_otp():
    email = session.get("reset_email", "")
    if not email:
        return redirect(url_for("auth.forgot_password"))

    error = None
    if request.method == "POST":
        otp_input = request.form.get("otp", "").strip()
        ok, msg = verify_otp_code(
            email, otp_input, purpose="reset")
        if ok:
            session["reset_verified"] = True
            return redirect(url_for("auth.reset_password"))
        error = msg

    demo_otp = session.get("demo_otp_reset", "")
    return render_template(
        "auth/reset_otp.html",
        email=email, error=error, demo_otp=demo_otp)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    email = session.get("reset_email", "")
    verified = session.get("reset_verified", False)
    if not email or not verified:
        return redirect(url_for("auth.forgot_password"))

    errors = {}
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not is_strong_password(password):
            errors["password"] = (
                "Password must be at least 8 characters "
                "with uppercase, lowercase, and a number.")
        if password != confirm:
            errors["confirm_password"] = \
                "Passwords do not match."

        if not errors:
            pw_hash = bcrypt.generate_password_hash(
                password).decode("utf-8")
            execute(
                "UPDATE users SET password_hash=?, "
                "updated_at=? WHERE email=?",
                (pw_hash,
                 datetime.utcnow().isoformat(),
                 email), commit=True)
            session.pop("reset_email", None)
            session.pop("reset_verified", None)
            flash("Password reset successfully. "
                  "Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template(
        "auth/reset_password.html", errors=errors)


# ══════════════════════════════════════════════════════════════
# PROFILE
# ══════════════════════════════════════════════════════════════
@auth_bp.route("/profile")
@login_required
def profile():
    history = execute(
        "SELECT * FROM predictions "
        "WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (current_user.id,), fetchall=True)
    return render_template(
        "auth/profile.html", history=history)


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    current = request.form.get("current_password", "")
    new_pwd = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    row = execute(
        "SELECT password_hash FROM users WHERE id=?",
        (current_user.id,), fetchone=True)

    if not bcrypt.check_password_hash(
            row["password_hash"], current):
        flash("Current password is incorrect.", "error")
    elif not is_strong_password(new_pwd):
        flash("New password must be at least 8 chars "
              "with uppercase, lowercase and number.", "error")
    elif new_pwd != confirm:
        flash("New passwords do not match.", "error")
    else:
        pw_hash = bcrypt.generate_password_hash(
            new_pwd).decode("utf-8")
        execute(
            "UPDATE users SET password_hash=?, "
            "updated_at=? WHERE id=?",
            (pw_hash,
             datetime.utcnow().isoformat(),
             current_user.id), commit=True)
        flash("Password changed successfully.", "success")

    return redirect(url_for("auth.profile"))
