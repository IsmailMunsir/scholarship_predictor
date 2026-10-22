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
from flask_mail import Mail

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
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_EMAIL')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_EMAIL')
    Mail(app)
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


@app.route("/history")
@login_required
def history():
    rows = execute("""
        SELECT id, z_score, stream, grade_a_count,
               annual_income, district, eligible_count,
               results_json, created_at
        FROM predictions WHERE user_id=?
        ORDER BY created_at DESC
    """, (current_user.id,), fetchall=True)
    predictions = []
    for r in (rows or []):
        predictions.append({
            "id": r["id"], "z_score": r["z_score"],
            "stream": r["stream"], "grade_a_count": r["grade_a_count"],
            "annual_income": r["annual_income"], "district": r["district"],
            "eligible_count": r["eligible_count"],
            "results": json.loads(r["results_json"] or "[]"),
            "created_at": r["created_at"],
        })
    return render_template("history.html", predictions=predictions)


# â”€â”€ Error pages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

@app.route("/delete-prediction/<int:pred_id>", methods=["POST"])
@login_required
def delete_prediction(pred_id):
    from database import execute
    execute("DELETE FROM predictions WHERE id=? AND user_id=?",
            (pred_id, current_user.id), commit=True)
    flash("Prediction deleted.", "info")
    return redirect(url_for("history"))

@app.route("/export-prediction/<int:pred_id>")
@login_required
def export_prediction(pred_id):
    import io
    import json
    from datetime import datetime
    from xml.sax.saxutils import escape

    from flask import make_response
    from database import execute
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )

    try:
        p = execute(
            "SELECT * FROM predictions WHERE id=? AND user_id=?",
            (pred_id, current_user.id),
            fetchone=True
        )

        if not p:
            flash("Prediction not found.", "error")
            return redirect(url_for("history"))

        def safe_text(value):
            return escape(str(value if value is not None else "-"))

        def safe_number(value, decimals=2):
            try:
                return f"{float(value):,.{decimals}f}"
            except (TypeError, ValueError):
                return "-"

        try:
            results = json.loads(p["results_json"] or "[]")
            if not isinstance(results, list):
                results = []
        except (json.JSONDecodeError, TypeError):
            results = []

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=1.8 * cm,
            bottomMargin=1.8 * cm,
            title="ScholarshipAI Eligibility Report",
            author="ScholarshipAI"
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="Cell",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
            wordWrap="CJK"
        ))
        styles.add(ParagraphStyle(
            name="SmallHeader",
            parent=styles["Cell"],
            fontName="Helvetica-Bold",
            textColor=colors.white
        ))

        story = [
            Paragraph("ScholarshipAI - Eligibility Report", styles["Title"]),
            Spacer(1, 0.35 * cm),
            Paragraph(
                "Student: " + safe_text(current_user.full_name),
                styles["Normal"]
            ),
            Paragraph(
                "Date: " + safe_text(p["created_at"]),
                styles["Normal"]
            ),
            Spacer(1, 0.5 * cm)
        ]

        summary = [
            ["Field", "Value"],
            ["Stream", safe_text(p["stream"])],
            ["Z-Score", safe_number(p["z_score"], 4)],
            ["District", safe_text(p["district"])],
            [
                "Annual Income",
                "Rs. " + safe_number(p["annual_income"], 2)
            ],
            ["Eligible Schemes", safe_text(p["eligible_count"])]
        ]

        summary_table = Table(
            summary,
            colWidths=[5 * cm, 11 * cm],
            repeatRows=1
        )
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3864")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f4f6fa")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([summary_table, Spacer(1, 0.6 * cm)])

        if results:
            story.extend([
                Paragraph("Scholarship Results", styles["Heading2"]),
                Spacer(1, 0.2 * cm)
            ])

            rows = [[
                Paragraph("Scholarship", styles["SmallHeader"]),
                Paragraph("Awarding Body", styles["SmallHeader"]),
                Paragraph("Amount", styles["SmallHeader"]),
                Paragraph("Status", styles["SmallHeader"])
            ]]

            for item in results:
                if not isinstance(item, dict):
                    continue

                amount = item.get("monthly_amount")
                try:
                    amount_text = (
                        "Rs. " + f"{float(amount):,.2f}" + "/mo"
                        if amount is not None and amount != ""
                        else "-"
                    )
                except (TypeError, ValueError):
                    amount_text = "-"

                status = (
                    "Eligible" if item.get("eligible") else "Not Eligible"
                )

                rows.append([
                    Paragraph(
                        safe_text(item.get("scheme_name", "-")),
                        styles["Cell"]
                    ),
                    Paragraph(
                        safe_text(item.get("awarding_body", "-")),
                        styles["Cell"]
                    ),
                    Paragraph(safe_text(amount_text), styles["Cell"]),
                    Paragraph(safe_text(status), styles["Cell"])
                ])

            if len(rows) > 1:
                result_table = Table(
                    rows,
                    colWidths=[5.3 * cm, 4.5 * cm, 3.3 * cm, 2.9 * cm],
                    repeatRows=1,
                    hAlign="LEFT"
                )
                result_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0),
                     colors.HexColor("#2e75b6")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [colors.white, colors.HexColor("#f0fdf4")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                story.append(result_table)

        doc.build(story)
        buffer.seek(0)

        response = make_response(buffer.getvalue())
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = (
            f'attachment; filename="scholarship_report_{pred_id}.pdf"'
        )
        response.headers["Content-Length"] = str(len(buffer.getvalue()))
        return response

    except Exception:
        import logging
        logging.exception("Scholarship PDF export failed for prediction %s", pred_id)
        flash("Could not generate the PDF report. Please check the server terminal.", "error")
        return redirect(url_for("history"))