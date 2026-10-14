"""
admin.py
Admin panel blueprint
"""
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from database import execute

admin_bp = Blueprint("admin", __name__)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not getattr(current_user, "is_admin", False):
            flash("Admin access required.", "error")
            return redirect(url_for("welcome"))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    total_predictions = execute(
        "SELECT COUNT(*) as c FROM predictions",
        fetchone=True)["c"]
    total_users = execute(
        "SELECT COUNT(*) as c FROM users",
        fetchone=True)["c"]
    avg_eligible = execute(
        "SELECT AVG(eligible_count) as a FROM predictions",
        fetchone=True)["a"] or 0
    recent = execute(
        "SELECT p.id, u.full_name, p.z_score, p.stream, "
        "p.annual_income, p.district, p.eligible_count, p.created_at "
        "FROM predictions p "
        "LEFT JOIN users u ON p.user_id = u.id "
        "ORDER BY p.id DESC LIMIT 20",
        fetchall=True)
    users = execute(
        "SELECT id, full_name, email, is_verified, is_admin, created_at "
        "FROM users ORDER BY id DESC",
        fetchall=True)
    return render_template("admin/dashboard.html",
        total_predictions=total_predictions,
        total_users=total_users,
        avg_eligible=round(avg_eligible, 1),
        recent=recent,
        users=users)
