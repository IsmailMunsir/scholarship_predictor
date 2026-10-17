import csv, io, os
from functools import wraps
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, Response, jsonify, session)
from database import execute

admin_bp = Blueprint("admin", __name__)

# ── Hardcoded admin credentials ──────────────────────────────
ADMIN_EMAIL    = "admin123@gmail.com"
ADMIN_PASSWORD = "Admin@2025!"

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated

# ── Admin Login ──────────────────────────────────────────────
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin.dashboard"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            session["admin_email"] = ADMIN_EMAIL
            return redirect(url_for("admin.dashboard"))
        error = "Invalid admin credentials. Please try again."
    return render_template("admin/login.html", error=error)

@admin_bp.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_email", None)
    return redirect(url_for("admin.login"))

# ── Dashboard ────────────────────────────────────────────────
@admin_bp.route("/")
@admin_required
def dashboard():
    total_predictions = (execute("SELECT COUNT(*) FROM predictions", fetchone=True) or [0])[0]
    total_users       = (execute("SELECT COUNT(*) FROM users", fetchone=True) or [0])[0]
    verified_users    = (execute("SELECT COUNT(*) FROM users WHERE is_verified=1", fetchone=True) or [0])[0]
    guest_predictions = (execute("SELECT COUNT(*) FROM predictions WHERE user_id IS NULL", fetchone=True) or [0])[0]
    avg_row = execute("SELECT AVG(eligible_count), AVG(z_score), AVG(annual_income) FROM predictions", fetchone=True) or (0,0,0)
    avg_eligible = round(avg_row[0] or 0, 1)
    avg_zscore   = round(avg_row[1] or 0, 4)
    avg_income   = int(avg_row[2] or 0)

    recent = execute("""
        SELECT p.id, u.full_name, p.z_score, p.stream, p.annual_income,
               p.district, p.eligible_count, p.created_at
        FROM predictions p LEFT JOIN users u ON p.user_id=u.id
        ORDER BY p.id DESC LIMIT 50
    """, fetchall=True) or []
    recent = [{"id":r[0],"full_name":r[1],"z_score":r[2],"stream":r[3],
               "annual_income":r[4],"district":r[5],"eligible_count":r[6],"created_at":r[7]} for r in recent]

    users = execute("""
        SELECT id, full_name, email, is_verified, is_admin, created_at,
               (SELECT COUNT(*) FROM predictions WHERE user_id=users.id) as pred_count
        FROM users ORDER BY id DESC
    """, fetchall=True) or []
    users = [{"id":u[0],"full_name":u[1],"email":u[2],"is_verified":u[3],
               "is_admin":u[4],"created_at":u[5],"pred_count":u[6]} for u in users]

    sd = execute("SELECT stream, COUNT(*) FROM predictions GROUP BY stream", fetchall=True) or []
    stream_data = {r[0]: r[1] for r in sd}
    ed = execute("SELECT eligible_count, COUNT(*) FROM predictions GROUP BY eligible_count ORDER BY eligible_count", fetchall=True) or []
    eligible_data = {str(r[0])+" schemes": r[1] for r in ed}
    dd = execute("SELECT district, COUNT(*) FROM predictions GROUP BY district ORDER BY COUNT(*) DESC LIMIT 10", fetchall=True) or []
    district_data = {r[0]: r[1] for r in dd}
    rows = execute("SELECT annual_income FROM predictions", fetchall=True) or []
    brackets = {"<100K":0,"100K-300K":0,"300K-600K":0,"600K-1M":0,">1M":0}
    for (inc,) in rows:
        if inc < 100000: brackets["<100K"] += 1
        elif inc < 300000: brackets["100K-300K"] += 1
        elif inc < 600000: brackets["300K-600K"] += 1
        elif inc < 1000000: brackets["600K-1M"] += 1
        else: brackets[">1M"] += 1
    zscore_hist = {"0.0-0.5":0,"0.5-1.0":0,"1.0-1.5":0,"1.5-2.0":0,"2.0-2.5":0,"2.5+":0}
    zrows = execute("SELECT z_score FROM predictions", fetchall=True) or []
    for (z,) in zrows:
        if z < 0.5: zscore_hist["0.0-0.5"] += 1
        elif z < 1.0: zscore_hist["0.5-1.0"] += 1
        elif z < 1.5: zscore_hist["1.0-1.5"] += 1
        elif z < 2.0: zscore_hist["1.5-2.0"] += 1
        elif z < 2.5: zscore_hist["2.0-2.5"] += 1
        else: zscore_hist["2.5+"] += 1
    monthly = execute("""
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*)
        FROM predictions GROUP BY month ORDER BY month DESC LIMIT 6
    """, fetchall=True) or []
    monthly_data = {r[0]: r[1] for r in reversed(monthly)}
    model_stats = [
        {"id":"SCH001","name":"Mahapola Merit","f1":0.982,"auc":0.9997},
        {"id":"SCH002","name":"UGC Bursary","f1":0.986,"auc":0.9998},
        {"id":"SCH003","name":"NW Provincial","f1":0.985,"auc":0.9989},
        {"id":"SCH004","name":"Science Merit","f1":0.971,"auc":0.9992},
        {"id":"SCH005","name":"Arts Bursary","f1":0.9947,"auc":1.0000},
        {"id":"SCH006","name":"Rural Excellence","f1":1.000,"auc":1.0000},
    ]
    return render_template("admin/dashboard.html",
        total_predictions=total_predictions, total_users=total_users,
        verified_users=verified_users, guest_predictions=guest_predictions,
        avg_eligible=avg_eligible, avg_zscore=avg_zscore, avg_income=avg_income,
        recent=recent, users=users,
        stream_data=stream_data, eligible_data=eligible_data,
        district_data=district_data, income_brackets=brackets,
        zscore_hist=zscore_hist, monthly_data=monthly_data,
        model_stats=model_stats)

# ── Dataset Editor ───────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "student_profiles_10000.csv")

def _load_csv():
    if not os.path.exists(DATA_FILE):
        return [], []
    with open(DATA_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = list(reader)
    for i, r in enumerate(rows):
        r["_idx"] = i
    return headers, rows

def _save_csv(headers, rows):
    clean = [{h: r.get(h, "") for h in headers} for r in rows]
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(clean)

def _filter_rows(rows, search, stream_f, district_f, zscore_f):
    if search:
        q = search.lower()
        rows = [r for r in rows if any(q in str(v).lower() for v in r.values())]
    if stream_f:
        rows = [r for r in rows if stream_f.lower() in str(r.get("stream", r.get("Stream", ""))).lower()]
    if district_f:
        rows = [r for r in rows if district_f.lower() == str(r.get("district", r.get("District", ""))).lower()]
    if zscore_f:
        def _zv(r):
            try: return float(r.get("z_score", r.get("Z_Score", r.get("zscore", 0))))
            except: return 0.0
        if zscore_f == "high":   rows = [r for r in rows if _zv(r) >= 1.8]
        elif zscore_f == "mid":  rows = [r for r in rows if 1.0 <= _zv(r) < 1.8]
        elif zscore_f == "low":  rows = [r for r in rows if _zv(r) < 1.0]
    return rows

def _sort_rows(rows, sort_field, sort_dir):
    if not sort_field:
        return rows
    reverse = (sort_dir == "desc")
    def _key(r):
        v = r.get(sort_field, "")
        try: return (0, float(v))
        except: return (1, str(v).lower())
    return sorted(rows, key=_key, reverse=reverse)

def _build_pg_html(page, total_pages, args):
    if total_pages <= 1:
        return ""
    def _url(p):
        a = dict(args)
        a["page"] = p
        return "?" + "&".join(f"{k}={v}" for k, v in a.items())
    parts = []
    pd = "disabled" if page <= 1 else ""
    parts.append(f'<a href="{_url(page-1)}" class="page-btn {pd}"><i class="bi bi-chevron-left"></i></a>')
    if total_pages <= 7:
        nums = list(range(1, total_pages + 1))
    elif page <= 4:
        nums = [1,2,3,4,5,"...",total_pages]
    elif page >= total_pages - 3:
        nums = [1,"...",total_pages-4,total_pages-3,total_pages-2,total_pages-1,total_pages]
    else:
        nums = [1,"...",page-1,page,page+1,"...",total_pages]
    for p in nums:
        if p == "...":
            parts.append('<span class="page-btn ellipsis">...</span>')
        else:
            ac = "active" if p == page else ""
            parts.append(f'<a href="{_url(p)}" class="page-btn {ac}">{p}</a>')
    nd = "disabled" if page >= total_pages else ""
    parts.append(f'<a href="{_url(page+1)}" class="page-btn {nd}"><i class="bi bi-chevron-right"></i></a>')
    return "".join(parts)

@admin_bp.route("/dataset")
@admin_required
def dataset():
    page       = max(1, int(request.args.get("page", 1)))
    per_page   = int(request.args.get("per_page", 50))
    if per_page not in (25, 50, 100): per_page = 50
    search     = request.args.get("q", "").strip()
    stream_f   = request.args.get("stream", "").strip()
    district_f = request.args.get("district", "").strip()
    zscore_f   = request.args.get("zscore", "").strip()
    sort_field = request.args.get("sort", "")
    sort_dir   = request.args.get("dir", "asc")
    headers, all_rows = _load_csv()
    total_rows = len(all_rows)
    dist_key = next((h for h in headers if h.lower() == "district"), None)
    districts = sorted(set(r.get(dist_key, "") for r in all_rows if r.get(dist_key, ""))) if dist_key else []
    filtered = _filter_rows(all_rows, search, stream_f, district_f, zscore_f)
    filtered = _sort_rows(filtered, sort_field, sort_dir)
    filtered_count = len(filtered)
    total_pages = max(1, (filtered_count + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    rows = filtered[start:start + per_page]
    for i, r in enumerate(rows):
        r["_display_num"] = start + i + 1
    pagination_html = _build_pg_html(page, total_pages, request.args)
    return render_template("admin/dataset.html",
        headers=headers, rows=rows,
        page=page, per_page=per_page,
        total_rows=total_rows, filtered_count=filtered_count,
        total_pages=total_pages,
        search=search, stream_filter=stream_f,
        district_filter=district_f, zscore_filter=zscore_f,
        districts=districts, pagination_html=pagination_html)

@admin_bp.route("/dataset/data")
@admin_required
def dataset_data():
    page       = max(1, int(request.args.get("page", 1)))
    per_page   = int(request.args.get("per_page", 50))
    if per_page not in (25, 50, 100): per_page = 50
    search     = request.args.get("q", "").strip()
    stream_f   = request.args.get("stream", "").strip()
    district_f = request.args.get("district", "").strip()
    zscore_f   = request.args.get("zscore", "").strip()
    sort_field = request.args.get("sort", "")
    sort_dir   = request.args.get("dir", "asc")
    headers, all_rows = _load_csv()
    filtered = _filter_rows(all_rows, search, stream_f, district_f, zscore_f)
    filtered = _sort_rows(filtered, sort_field, sort_dir)
    filtered_count = len(filtered)
    total_pages = max(1, (filtered_count + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    rows = filtered[start:start + per_page]
    for i, r in enumerate(rows):
        r["_display_num"] = start + i + 1
    return jsonify({"rows": rows, "headers": headers, "page": page,
        "per_page": per_page, "total_pages": total_pages,
        "filtered_count": filtered_count, "total_rows": len(all_rows)})

@admin_bp.route("/dataset/row/<int:idx>", methods=["GET"])
@admin_required
def dataset_get_row(idx):
    headers, rows = _load_csv()
    if idx < 0 or idx >= len(rows):
        return jsonify({"error": "Row not found"}), 404
    row = {k: v for k, v in rows[idx].items() if k != "_idx"}
    return jsonify(row)

@admin_bp.route("/dataset/row/<int:idx>", methods=["POST"])
@admin_required
def dataset_update_row(idx):
    headers, rows = _load_csv()
    if idx < 0 or idx >= len(rows):
        return jsonify({"error": "Row not found"}), 404
    data = request.get_json() or {}
    for k in headers:
        if k in data:
            rows[idx][k] = data[k]
    _save_csv(headers, rows)
    return jsonify({"success": True})

@admin_bp.route("/dataset/row/<int:idx>/delete", methods=["POST"])
@admin_required
def dataset_delete_row(idx):
    headers, rows = _load_csv()
    if idx < 0 or idx >= len(rows):
        return jsonify({"error": "Row not found"}), 404
    rows.pop(idx)
    _save_csv(headers, rows)
    return jsonify({"success": True})

@admin_bp.route("/dataset/add", methods=["POST"])
@admin_required
def dataset_add_row():
    headers, rows = _load_csv()
    data = request.get_json() or {}
    rows.append({h: data.get(h, "") for h in headers})
    _save_csv(headers, rows)
    return jsonify({"success": True, "index": len(rows) - 1})

@admin_bp.route("/dataset/export")
@admin_required
def dataset_export_filtered():
    search     = request.args.get("q", "").strip()
    stream_f   = request.args.get("stream", "").strip()
    district_f = request.args.get("district", "").strip()
    zscore_f   = request.args.get("zscore", "").strip()
    headers, all_rows = _load_csv()
    filtered = _filter_rows(all_rows, search, stream_f, district_f, zscore_f)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    w.writeheader()
    for r in filtered:
        w.writerow({h: r.get(h, "") for h in headers})
    buf.seek(0)
    fname = "dataset_filtered.csv" if any([search, stream_f, district_f, zscore_f]) else "dataset_full.csv"
    return Response(buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"})

# ── CSV Export ───────────────────────────────────────────────
@admin_bp.route("/export/predictions")
@admin_required
def export_predictions():
    rows=execute("""SELECT p.id,u.full_name,p.z_score,p.stream,p.annual_income,
        p.district,p.eligible_count,p.created_at FROM predictions p
        LEFT JOIN users u ON p.user_id=u.id ORDER BY p.id DESC""",fetchall=True) or []
    buf=io.StringIO(); w=csv.writer(buf)
    w.writerow(["ID","Student","Z-Score","Stream","Income","District","EligibleSchemes","Date"])
    for r in rows: w.writerow(r)
    buf.seek(0)
    return Response(buf.getvalue(),mimetype="text/csv",
        headers={"Content-Disposition":"attachment; filename=predictions.csv"})

@admin_bp.route("/export/users")
@admin_required
def export_users():
    rows=execute("SELECT id,full_name,email,is_verified,is_admin,created_at FROM users ORDER BY id",fetchall=True) or []
    buf=io.StringIO(); w=csv.writer(buf)
    w.writerow(["ID","FullName","Email","Verified","IsAdmin","Joined"])
    for r in rows: w.writerow(r)
    buf.seek(0)
    return Response(buf.getvalue(),mimetype="text/csv",
        headers={"Content-Disposition":"attachment; filename=users.csv"})

# ── User Management ──────────────────────────────────────────
@admin_bp.route("/user/<int:uid>/toggle-admin", methods=["POST"])
@admin_required
def toggle_admin(uid):
    row=execute("SELECT is_admin FROM users WHERE id=?",(uid,),fetchone=True)
    if not row: return jsonify({"error":"User not found"}),404
    new_val=0 if row[0] else 1
    execute("UPDATE users SET is_admin=? WHERE id=?",(new_val,uid),commit=True)
    return jsonify({"ok":True,"is_admin":new_val})

@admin_bp.route("/user/<int:uid>/toggle-verify", methods=["POST"])
@admin_required
def toggle_verify(uid):
    row=execute("SELECT is_verified FROM users WHERE id=?",(uid,),fetchone=True)
    if not row: return jsonify({"error":"User not found"}),404
    new_val=0 if row[0] else 1
    execute("UPDATE users SET is_verified=? WHERE id=?",(new_val,uid),commit=True)
    return jsonify({"ok":True,"is_verified":new_val})

@admin_bp.route("/user/<int:uid>/delete", methods=["POST"])
@admin_required
def delete_user(uid):
    execute("DELETE FROM predictions WHERE user_id=?",(uid,),commit=True)
    execute("DELETE FROM users WHERE id=?",(uid,),commit=True)
    return jsonify({"ok":True})

@admin_bp.route("/api/stats")
@admin_required
def api_stats():
    return jsonify({
        "total_predictions":(execute("SELECT COUNT(*) FROM predictions",fetchone=True) or [0])[0],
        "total_users":(execute("SELECT COUNT(*) FROM users",fetchone=True) or [0])[0]
    })

