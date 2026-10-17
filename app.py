"""
app.py
======
Main Flask Application
University Scholarship Eligibility Predictor
"""

import os
import json
from datetime import datetime
from flask import (Flask, render_template, request,
                   redirect, url_for, flash,
                   session, jsonify)
from flask_login import login_required, current_user
from dotenv import load_dotenv

from database import init_db, get_db, execute
from auth import auth_bp, bcrypt, login_manager
from admin import admin_bp
from scholarship_predictor import (
    SCHEMES, DISTRICT_FACTORS,
    STREAM_CODES, predict_for_student
)

load_dotenv()


# â”€â”€ App factory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv(
        "SECRET_KEY", "dev-secret-key-2026")
    app.config["SESSION_COOKIE_HTTPONLY"]  = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_DURATION"] = \
        60 * 60 * 24 * 30  # 30 days

    # Init extensions
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view             = "auth.login"
    login_manager.login_message          = \
        "Please log in to access this page."
    login_manager.login_message_category = "warning"

    # Register auth blueprint
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Init database
    with app.app_context():
        init_db()

    return app


app = create_app()


# â”€â”€ Context processor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.context_processor
def inject_globals():
    return {"current_year": datetime.now().year}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SCREEN 1 â€” Welcome
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route("/")
def welcome():
    return render_template("screen1_welcome.html")


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SCREEN 2 â€” Academic Results
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route("/academic", methods=["GET", "POST"])
def academic():
    if request.method == "POST":
        z_str = request.form.get("z_score", "").strip()
        try:
            z_val = float(z_str)
            if not (0.5 <= z_val <= 2.8):
                raise ValueError
        except ValueError:
            flash("Z-score must be between 0.50 and 2.80.",
                  "error")
            return render_template(
                "screen2_academic.html",
                streams=list(STREAM_CODES.keys()),
                form=request.form)

        g1 = request.form.get("grade1", "C")
        g2 = request.form.get("grade2", "C")
        g3 = request.form.get("grade3", "C")

        session["z_score"]       = z_val
        session["stream"]        = request.form.get(
            "stream", "Arts")
        session["grade1"]        = g1
        session["grade2"]        = g2
        session["grade3"]        = g3
        session["grade_a_count"] = sum(
            1 for g in [g1, g2, g3] if g == "A")

        return redirect(url_for("family"))

    return render_template(
        "screen2_academic.html",
        streams=list(STREAM_CODES.keys()),
        form={})


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SCREEN 3 â€” Family & Location
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route("/family", methods=["GET", "POST"])
def family():
    if request.method == "POST":
        try:
            inc = int(request.form.get("annual_income", "0"))
            if not (0 <= inc <= 5_000_000):
                raise ValueError
        except ValueError:
            flash("Income must be between Rs. 0 and Rs. 5,000,000.", "error")
            return render_template(
                "screen3_family.html",
                districts=sorted(DISTRICT_FACTORS.keys()),
                form=request.form)

        district = request.form.get("district", "Colombo")
        if district not in DISTRICT_FACTORS:
            flash("Please select a valid district.", "error")
            return render_template(
                "screen3_family.html",
                districts=sorted(DISTRICT_FACTORS.keys()),
                form=request.form)
        session["annual_income"] = inc
        session["district"]      = district
        return redirect(url_for("processing"))

    return render_template(
        "screen3_family.html",
        districts=sorted(DISTRICT_FACTORS.keys()),
        form={})


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SCREEN 4 â€” Processing
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route("/processing")
def processing():
    if not session.get("z_score"):
        return redirect(url_for("academic"))
    return render_template("screen4_processing.html")


# â”€â”€ AJAX Predict endpoint â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/predict", methods=["POST"])
@login_required
def predict():
    try:
        profile = {
            "z_score":           session.get("z_score",   1.0),
            "stream":            session.get("stream",    "Arts"),
            "grade_a_count":     session.get("grade_a_count", 0),
            "annual_income_lkr": session.get("annual_income",
                                             500000),
            "district":          session.get("district",
                                             "Colombo"),
        }

        results        = predict_for_student(profile)
        eligible_count = sum(
            1 for r in results if r["eligible"])
        session["results"] = results

        # Save to database
        from scholarship_predictor import DISTRICT_FACTORS as DF
        clf  = DF.get(profile["district"], 1.0)
        iadj = int(profile["annual_income_lkr"] / clf)

        user_id = (current_user.id
                   if current_user.is_authenticated else None)

        execute("""
            INSERT INTO predictions
            (user_id, z_score, stream, grade_a_count,
             annual_income, district, income_adjusted,
             results_json, eligible_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            profile["z_score"],
            profile["stream"],
            profile["grade_a_count"],
            profile["annual_income_lkr"],
            profile["district"],
            iadj,
            json.dumps(results),
            eligible_count,
            datetime.now().isoformat(),
        ), commit=True)

        return jsonify({
            "ok":             True,
            "results":        results,
            "eligible_count": eligible_count,
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SCREEN 5 â€” Results
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route("/results")
def results():
    all_r    = session.get("results", [])
    eligible = [r for r in all_r if r["eligible"]]
    high     = [r for r in all_r
                if r["probability_pct"] >= 70]
    profile  = {
        "z_score":  session.get("z_score"),
        "stream":   session.get("stream"),
        "district": session.get("district"),
        "income":   session.get("annual_income"),
    }
    return render_template(
        "screen5_results.html",
        results=all_r,
        eligible=eligible,
        high_match=high,
        profile=profile)


# â”€â”€ Reset session â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/reset")
def reset():
    for k in ["z_score", "stream", "grade1", "grade2",
              "grade3", "grade_a_count",
              "annual_income", "district", "results"]:
        session.pop(k, None)
    return redirect(url_for("welcome"))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# REST API endpoints
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route("/api/districts")
def api_districts():
    return jsonify(sorted(DISTRICT_FACTORS.keys()))


@app.route("/api/schemes")
def api_schemes():
    rows = execute(
        "SELECT * FROM scholarship_schemes",
        fetchall=True)
    return jsonify([dict(r) for r in rows])


@app.route("/api/history")
def api_history():
    rows = execute(
        "SELECT id, z_score, stream, annual_income, "
        "district, eligible_count, created_at "
        "FROM predictions "
        "ORDER BY id DESC LIMIT 20",
        fetchall=True)
    return jsonify([dict(r) for r in rows])


# â”€â”€ Error pages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route("/debug-user")
def debug_user():
    from flask_login import current_user
    if current_user.is_authenticated:
        return f"Logged in as: {current_user.email} | is_admin: {current_user.is_admin}"
    return "Not logged in"

@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html"), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("errors/500.html"), 500


# â”€â”€ Run â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    port  = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    print(f"\n{'='*55}")
    print(f"  Scholarship Predictor â†’ http://localhost:{port}")
    print(f"  Login  â†’ http://localhost:{port}/auth/login")
    print(f"  Register â†’ http://localhost:{port}/auth/register")
    print(f"{'='*55}\n")
    app.run(debug=debug, host="0.0.0.0", port=port)
