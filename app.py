from flask import Flask

app = Flask(__name__)
import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "avif"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file):
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        return None
    filename = secure_filename(file.filename)
    stem, ext = os.path.splitext(filename)
    filename = f"{stem}_{os.urandom(6).hex()}{ext.lower()}"
    file.save(UPLOAD_FOLDER / filename)
    return filename


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin"))
        return view(*args, **kwargs)
    return wrapped


def super_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "superadmin":
            flash("Super administrator access is required.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "student_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def password_matches(stored, supplied):
    try:
        return check_password_hash(stored, supplied)
    except (ValueError, TypeError):
        return stored == supplied


def ensure_settings(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(settings)").fetchall()}
    needed = {
        "results_published": "INTEGER NOT NULL DEFAULT 0",
        "school_name": "TEXT DEFAULT 'Kigezi High School'",
        "school_logo": "TEXT DEFAULT 'default.png'",
        "voting_status": "TEXT DEFAULT 'Open'",
        "start_date": "TEXT",
        "end_date": "TEXT",
    }
    conn.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY)")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(settings)").fetchall()}
    for col, definition in needed.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE settings ADD COLUMN {col} {definition}")
    conn.execute("INSERT OR IGNORE INTO settings(id) VALUES(1)")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        student = conn.execute(
            "SELECT id, student_id, fullname, password, has_voted FROM students WHERE student_id=?",
            (student_id,),
        ).fetchone()
        if student and password_matches(student["password"], password):
            # Upgrade legacy plain-text passwords after a successful login.
            if not str(student["password"]).startswith(("scrypt:", "pbkdf2:", "argon2:")):
                conn.execute("UPDATE students SET password=? WHERE id=?", (generate_password_hash(password), student["id"]))
                conn.commit()
            session.clear()
            session["student_id"] = student["student_id"]
            session["fullname"] = student["fullname"]
            conn.close()
            return redirect(url_for("student_dashboard"))
        conn.close()
        flash("Invalid Student ID or Password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/student_dashboard")
@student_required
def student_dashboard():
    conn = get_db()
    student = conn.execute("SELECT fullname, has_voted, photo FROM students WHERE student_id=?", (session["student_id"],)).fetchone()
    conn.close()
    if not student:
        session.clear()
        return redirect(url_for("login"))
    return render_template("student_dashboard.html", fullname=student["fullname"], student_id=session["student_id"], has_voted=student["has_voted"], photo=student["photo"])


@app.route("/student_account", methods=["GET", "POST"])
@student_required
def student_account():
    conn = get_db()
    if request.method == "POST":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        student = conn.execute("SELECT password FROM students WHERE student_id=?", (session["student_id"],)).fetchone()
        if not student or not password_matches(student["password"], old_password):
            flash("Current password is incorrect.", "danger")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "danger")
        elif len(new_password) < 4:
            flash("New password must be at least 4 characters.", "danger")
        else:
            conn.execute("UPDATE students SET password=? WHERE student_id=?", (generate_password_hash(new_password), session["student_id"]))
            conn.commit()
            flash("Password changed successfully.", "success")
        if request.files.get("photo") and request.files["photo"].filename:
            filename = save_upload(request.files["photo"])
            if filename:
                conn.execute("UPDATE students SET photo=? WHERE student_id=?", (filename, session["student_id"]))
                conn.commit()
                flash("Profile photo updated.", "success")
            else:
                flash("Invalid image file.", "danger")
        conn.close()
        return redirect(url_for("student_account"))
    student = conn.execute("SELECT * FROM students WHERE student_id=?", (session["student_id"],)).fetchone()
    conn.close()
    return render_template("student_account.html", student=student, fullname=student["fullname"], student_id=student["student_id"], photo=student["photo"])


@app.route("/update_account", methods=["POST"])
@student_required
def update_account():
    return student_account()


@app.route("/change_password", methods=["POST"])
@student_required
def change_password():
    return student_account()


@app.route("/vote")
@student_required
def vote():
    conn = get_db()
    student = conn.execute("SELECT has_voted FROM students WHERE student_id=?", (session["student_id"],)).fetchone()
    settings = conn.execute("SELECT voting_status FROM settings WHERE id=1").fetchone()
    if student and student["has_voted"]:
        conn.close()
        flash("You have already voted.", "info")
        return redirect(url_for("student_dashboard"))
    if settings and settings["voting_status"] != "Open":
        conn.close()
        flash("Voting is currently closed.", "warning")
        return redirect(url_for("student_dashboard"))
    rows = conn.execute("SELECT * FROM candidates ORDER BY position, fullname").fetchall()
    conn.close()
    positions = {}
    for row in rows:
        positions.setdefault(row["position"], []).append(row)
    return render_template("vote.html", positions=positions)


@app.route("/cast_vote", methods=["POST"])
@student_required
def cast_vote():
    conn = get_db()
    student_id = session["student_id"]
    student = conn.execute("SELECT has_voted FROM students WHERE student_id=?", (student_id,)).fetchone()
    settings = conn.execute("SELECT voting_status FROM settings WHERE id=1").fetchone()
    if not student:
        conn.close(); return redirect(url_for("login"))
    if student["has_voted"]:
        conn.close(); flash("You have already voted.", "info"); return redirect(url_for("student_dashboard"))
    if settings and settings["voting_status"] != "Open":
        conn.close(); flash("Voting is currently closed.", "warning"); return redirect(url_for("student_dashboard"))
    selections = [(position, value) for position, value in request.form.items() if position and value]
    if not selections:
        conn.close(); flash("Please select a candidate for every position.", "danger"); return redirect(url_for("vote"))
    position_count = conn.execute("SELECT COUNT(DISTINCT position) FROM candidates").fetchone()[0]
    if len(selections) != position_count:
        conn.close(); flash("Please select one candidate for every position.", "danger"); return redirect(url_for("vote"))
    try:
        for position, candidate_id in selections:
            candidate = conn.execute("SELECT id FROM candidates WHERE id=? AND position=?", (candidate_id, position)).fetchone()
            if not candidate:
                raise ValueError("Invalid candidate selection")
            conn.execute("INSERT INTO votes(student_id, candidate_id) VALUES(?, ?)", (student_id, candidate_id))
        conn.execute("UPDATE students SET has_voted=1 WHERE student_id=?", (student_id,))
        conn.commit()
    except Exception:
        conn.rollback(); conn.close(); flash("Your vote could not be recorded. Please try again.", "danger"); return redirect(url_for("vote"))
    conn.close(); flash("Your vote has been submitted successfully.", "success"); return redirect(url_for("student_dashboard"))


@app.route("/student_results")
@student_required
def student_results():
    conn = get_db()
    status = conn.execute("SELECT results_published FROM settings WHERE id=1").fetchone()
    if not status or not status["results_published"]:
        conn.close(); return render_template("results_not_published.html")
    rows = conn.execute("""
        SELECT c.id, c.fullname, c.position, c.photo, COUNT(v.id) AS votes
        FROM candidates c LEFT JOIN votes v ON c.id=v.candidate_id
        GROUP BY c.id ORDER BY c.position, votes DESC, c.fullname
    """).fetchall()
    conn.close()
    results = {}
    winners = {}
    for row in rows:
        results.setdefault(row["position"], []).append(row)
    for position, candidates in results.items():
        winners[position] = candidates[0]
    return render_template("student_results.html", results=results, winners=winners)


@app.route("/results")
@admin_required
def results():
    conn = get_db()
    rows = conn.execute("""
        SELECT c.id, c.fullname, c.position, c.photo, COUNT(v.id) AS total_votes
        FROM candidates c LEFT JOIN votes v ON c.id=v.candidate_id
        GROUP BY c.id ORDER BY c.position, total_votes DESC, c.fullname
    """).fetchall()
    positions = [r["position_name"] for r in conn.execute("SELECT position_name FROM positions ORDER BY position_name").fetchall()]
    status = conn.execute("SELECT results_published FROM settings WHERE id=1").fetchone()
    published = status["results_published"] if status else 0
    winners = []
    for position in positions:
        winner = conn.execute("""
            SELECT c.fullname, c.position, c.photo, COUNT(v.id) AS total_votes
            FROM candidates c LEFT JOIN votes v ON c.id=v.candidate_id
            WHERE c.position=? GROUP BY c.id ORDER BY total_votes DESC, c.fullname LIMIT 1
        """, (position,)).fetchone()
        if winner: winners.append(winner)
    conn.close()
    return render_template("admin/results.html", results=rows, positions=positions, winners=winners, published=published)


@app.route("/publish_results")
@admin_required
def publish_results():
    conn=get_db(); conn.execute("UPDATE settings SET results_published=1 WHERE id=1"); conn.commit(); conn.close()
    flash("Results published to students.", "success"); return redirect(url_for("results"))


@app.route("/unpublish_results")
@admin_required
def unpublish_results():
    conn=get_db(); conn.execute("UPDATE settings SET results_published=0 WHERE id=1"); conn.commit(); conn.close()
    flash("Results hidden from students.", "success"); return redirect(url_for("results"))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    error = None
    if request.method == "POST":
        username=request.form.get("username", "").strip(); password=request.form.get("password", "")
        conn=get_db(); row=conn.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        if row and password_matches(row["password"], password):
            if row["status"] != "Active": error="Your account has been deactivated."
            else:
                if not str(row["password"]).startswith(("scrypt:", "pbkdf2:", "argon2:")):
                    conn.execute("UPDATE admins SET password=? WHERE id=?", (generate_password_hash(password), row["id"])); conn.commit()
                session.clear(); session["admin_id"]=row["id"]; session["admin"]=row["username"]; session["admin_username"]=row["username"]; session["role"]=row["role"]; session["photo"]=row["photo"]
                conn.close(); return redirect(url_for("dashboard"))
        else: error="Invalid username or password."
        conn.close()
    return render_template("admin_login.html", error=error)


@app.route("/dashboard")
@admin_required
def dashboard():
    conn=get_db()
    total_students=conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_candidates=conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    total_positions=conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    total_votes=conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
    votes_remaining=conn.execute("SELECT COUNT(*) FROM students WHERE has_voted=0").fetchone()[0]
    leaders=conn.execute("""
        SELECT c.fullname,c.position,c.photo,COUNT(v.id) AS votes
        FROM candidates c LEFT JOIN votes v ON c.id=v.candidate_id
        GROUP BY c.id ORDER BY c.position,votes DESC,c.fullname
    """).fetchall()
    status=conn.execute("SELECT results_published FROM settings WHERE id=1").fetchone()
    published=status["results_published"] if status else 0
    conn.close()
    return render_template("admin/dashboard.html", total_students=total_students,total_candidates=total_candidates,total_positions=total_positions,total_votes=total_votes,votes_remaining=votes_remaining,leaders=leaders,published=published,admin=session.get("admin"))


@app.route("/account")
@admin_required
def account():
    return redirect(url_for("profile"))


@app.route("/profile")
@admin_required
def profile():
    conn=get_db(); admin=conn.execute("SELECT * FROM admins WHERE id=?",(session["admin_id"],)).fetchone(); conn.close()
    return render_template("admin/profile.html",admin=admin)


@app.route("/edit_profile", methods=["GET","POST"])
@admin_required
def edit_profile():
    conn=get_db()
    if request.method=="POST":
        username=request.form.get("username","").strip(); email=request.form.get("email","").strip(); phone=request.form.get("phone","").strip()
        current=conn.execute("SELECT photo FROM admins WHERE id=?",(session["admin_id"],)).fetchone(); photo=current["photo"] if current else "default.png"
        if request.files.get("photo") and request.files["photo"].filename:
            uploaded=save_upload(request.files["photo"])
            if uploaded: photo=uploaded
            else: flash("Invalid image file.","danger")
        try:
            conn.execute("UPDATE admins SET username=?,email=?,phone=?,photo=? WHERE id=?",(username,email,phone,photo,session["admin_id"])); conn.commit()
            session["admin"]=username; session["admin_username"]=username; session["photo"]=photo; flash("Profile updated successfully.","success")
        except sqlite3.IntegrityError: flash("Username already exists.","danger")
        conn.close(); return redirect(url_for("profile"))
    admin=conn.execute("SELECT * FROM admins WHERE id=?",(session["admin_id"],)).fetchone(); conn.close(); return render_template("admin/edit_profile.html",admin=admin)


@app.route("/admin_change_password", methods=["GET","POST"])
@admin_required
def admin_change_password():
    conn=get_db()
    if request.method=="POST":
        current=request.form.get("current_password",""); new=request.form.get("new_password",""); confirm=request.form.get("confirm_password","")
        row=conn.execute("SELECT password FROM admins WHERE id=?",(session["admin_id"],)).fetchone()
        if not row or not password_matches(row["password"],current): flash("Current password is incorrect.","danger")
        elif new!=confirm: flash("New passwords do not match.","danger")
        elif len(new)<4: flash("New password must be at least 4 characters.","danger")
        else: conn.execute("UPDATE admins SET password=? WHERE id=?",(generate_password_hash(new),session["admin_id"])); conn.commit(); flash("Password changed successfully.","success")
        conn.close(); return redirect(url_for("profile"))
    conn.close(); return render_template("admin/account_control.html",admin=get_db().execute("SELECT * FROM admins WHERE id=?",(session["admin_id"],)).fetchone())


@app.route("/account_control")
@admin_required
@super_admin_required
def account_control():
    conn=get_db(); admins=conn.execute("SELECT * FROM admins ORDER BY username").fetchall(); conn.close(); return render_template("admin/account_control.html",admins=admins)


@app.route("/manage_admins")
@admin_required
@super_admin_required
def manage_admins():
    conn=get_db(); admins=conn.execute("SELECT * FROM admins ORDER BY username").fetchall(); conn.close(); return render_template("admin/manage_admins.html",admins=admins)


@app.route("/add_admin", methods=["GET","POST"])
@admin_required
@super_admin_required
def add_admin():
    error=success=None
    if request.method=="POST":
        username=request.form.get("username","").strip(); password=request.form.get("password",""); role=request.form.get("role","admin"); status=request.form.get("status","Active")
        conn=get_db()
        try:
            conn.execute("INSERT INTO admins(username,password,role,photo,status) VALUES(?,?,?,?,?)",(username,generate_password_hash(password),role,"default.png",status)); conn.commit(); success="Administrator created successfully."
        except sqlite3.IntegrityError: error="Username already exists."
        conn.close()
    return render_template("admin/add_admin.html",error=error,success=success)


@app.route("/edit_admin/<int:id>", methods=["GET","POST"])
@admin_required
@super_admin_required
def edit_admin(id):
    conn=get_db(); admin_row=conn.execute("SELECT * FROM admins WHERE id=?",(id,)).fetchone()
    if not admin_row: conn.close(); flash("Administrator not found.","danger"); return redirect(url_for("manage_admins"))
    if request.method=="POST":
        username=request.form.get("username","").strip(); role=request.form.get("role","admin"); status=request.form.get("status","Active"); password=request.form.get("password","")
        try:
            if password: conn.execute("UPDATE admins SET username=?,role=?,status=?,password=? WHERE id=?",(username,role,status,generate_password_hash(password),id))
            else: conn.execute("UPDATE admins SET username=?,role=?,status=? WHERE id=?",(username,role,status,id))
            conn.commit(); flash("Administrator updated.","success"); conn.close(); return redirect(url_for("manage_admins"))
        except sqlite3.IntegrityError: flash("Username already exists.","danger")
    conn.close(); return render_template("admin/edit_admin.html",admin=admin_row)


@app.route("/delete_admin/<int:id>")
@admin_required
@super_admin_required
def delete_admin(id):
    if id==session["admin_id"]: flash("You cannot delete your own account.","danger"); return redirect(url_for("manage_admins"))
    conn=get_db(); conn.execute("DELETE FROM admins WHERE id=?",(id,)); conn.commit(); conn.close(); flash("Administrator deleted.","success"); return redirect(url_for("manage_admins"))


@app.route("/upload_admin_photo", methods=["POST"])
@admin_required
def upload_admin_photo():
    filename=save_upload(request.files.get("photo"))
    if not filename: flash("Please select a valid image file.","danger")
    else:
        conn=get_db(); conn.execute("UPDATE admins SET photo=? WHERE id=?",(filename,session["admin_id"])); conn.commit(); conn.close(); session["photo"]=filename; flash("Photo updated.","success")
    return redirect(url_for("profile"))


@app.route("/students")
@admin_required
def students():
    conn=get_db(); rows=conn.execute("SELECT * FROM students ORDER BY fullname").fetchall(); conn.close(); return render_template("admin/students.html",students=rows)


@app.route("/add_student", methods=["GET","POST"])
@admin_required
def add_student():
    if request.method=="POST":
        sid=request.form.get("student_id","").strip(); fullname=request.form.get("fullname","").strip(); password=request.form.get("password","")
        conn=get_db()
        try:
            conn.execute("INSERT INTO students(student_id,fullname,password) VALUES(?,?,?)",(sid,fullname,generate_password_hash(password))); conn.commit(); flash("Student added successfully.","success"); conn.close(); return redirect(url_for("students"))
        except sqlite3.IntegrityError: conn.close(); flash("Student ID already exists.","danger")
    return render_template("admin/add_student.html")


@app.route("/edit_student/<int:id>", methods=["GET","POST"])
@admin_required
def edit_student(id):
    conn=get_db(); student=conn.execute("SELECT * FROM students WHERE id=?",(id,)).fetchone()
    if not student: conn.close(); flash("Student not found.","danger"); return redirect(url_for("students"))
    if request.method=="POST":
        sid=request.form.get("student_id","").strip(); fullname=request.form.get("fullname","").strip(); password=request.form.get("password","")
        try:
            if password: conn.execute("UPDATE students SET student_id=?,fullname=?,password=? WHERE id=?",(sid,fullname,generate_password_hash(password),id))
            else: conn.execute("UPDATE students SET student_id=?,fullname=? WHERE id=?",(sid,fullname,id))
            conn.commit(); flash("Student updated.","success"); conn.close(); return redirect(url_for("students"))
        except sqlite3.IntegrityError: flash("Student ID already exists.","danger")
    conn.close(); return render_template("admin/edit_student.html",student=student)


@app.route("/delete_student/<int:id>")
@admin_required
def delete_student(id):
    conn=get_db(); row=conn.execute("SELECT student_id FROM students WHERE id=?",(id,)).fetchone()
    if row:
        conn.execute("DELETE FROM votes WHERE student_id=?",(row["student_id"],)); conn.execute("DELETE FROM students WHERE id=?",(id,)); conn.commit(); flash("Student deleted.","success")
    conn.close(); return redirect(url_for("students"))


@app.route("/positions", methods=["GET","POST"])
@admin_required
def positions():
    conn=get_db()
    if request.method=="POST":
        name=request.form.get("position","").strip()
        if not name: flash("Position name is required.","danger")
        else:
            try: conn.execute("INSERT INTO positions(position_name) VALUES(?)",(name,)); conn.commit(); flash("Position added successfully.","success")
            except sqlite3.IntegrityError: flash("Position already exists.","danger")
        conn.close(); return redirect(url_for("positions"))
    rows=conn.execute("SELECT * FROM positions ORDER BY position_name").fetchall(); conn.close(); return render_template("admin/positions.html",positions=rows)


@app.route("/add_position", methods=["GET","POST"])
@admin_required
def add_position():
    if request.method=="POST":
        name=request.form.get("position_name","").strip()
        conn=get_db()
        try: conn.execute("INSERT INTO positions(position_name) VALUES(?)",(name,)); conn.commit(); flash("Position added successfully.","success"); conn.close(); return redirect(url_for("positions"))
        except sqlite3.IntegrityError: conn.close(); flash("Position already exists.","danger")
    return render_template("admin/add_position.html")


@app.route("/delete_position/<int:id>")
@admin_required
def delete_position(id):
    conn=get_db(); row=conn.execute("SELECT position_name FROM positions WHERE id=?",(id,)).fetchone()
    if row:
        conn.execute("DELETE FROM votes WHERE candidate_id IN (SELECT id FROM candidates WHERE position=?)",(row["position_name"],)); conn.execute("DELETE FROM candidates WHERE position=?",(row["position_name"],)); conn.execute("DELETE FROM positions WHERE id=?",(id,)); conn.commit(); flash("Position deleted.","success")
    conn.close(); return redirect(url_for("positions"))


@app.route("/candidates")
@admin_required
def candidates():
    conn=get_db(); rows=conn.execute("SELECT * FROM candidates ORDER BY position,fullname").fetchall(); conn.close(); return render_template("admin/candidates.html",candidates=rows)


@app.route("/add_candidate", methods=["GET","POST"])
@admin_required
def add_candidate():
    conn=get_db(); positions=conn.execute("SELECT position_name FROM positions ORDER BY position_name").fetchall()
    if request.method=="POST":
        fullname=request.form.get("fullname","").strip(); position=request.form.get("position","").strip(); filename=save_upload(request.files.get("photo")) or "default.png"
        conn.execute("INSERT INTO candidates(fullname,position,photo) VALUES(?,?,?)",(fullname,position,filename)); conn.commit(); conn.close(); flash("Candidate added successfully.","success"); return redirect(url_for("candidates"))
    conn.close(); return render_template("admin/add_candidate.html",positions=positions)


@app.route("/edit_candidate/<int:id>", methods=["GET","POST"])
@admin_required
def edit_candidate(id):
    conn=get_db(); candidate=conn.execute("SELECT * FROM candidates WHERE id=?",(id,)).fetchone(); positions=conn.execute("SELECT position_name FROM positions ORDER BY position_name").fetchall()
    if not candidate: conn.close(); flash("Candidate not found.","danger"); return redirect(url_for("candidates"))
    if request.method=="POST":
        fullname=request.form.get("fullname","").strip(); position=request.form.get("position","").strip(); photo=candidate["photo"] or "default.png"; uploaded=save_upload(request.files.get("photo")); photo=uploaded or photo
        conn.execute("UPDATE candidates SET fullname=?,position=?,photo=? WHERE id=?",(fullname,position,photo,id)); conn.commit(); conn.close(); flash("Candidate updated.","success"); return redirect(url_for("candidates"))
    conn.close(); return render_template("admin/edit_candidate.html",candidate=candidate,positions=positions)


@app.route("/delete_candidate/<int:id>")
@admin_required
def delete_candidate(id):
    conn=get_db(); conn.execute("DELETE FROM votes WHERE candidate_id=?",(id,)); conn.execute("DELETE FROM candidates WHERE id=?",(id,)); conn.commit(); conn.close(); flash("Candidate deleted.","success"); return redirect(url_for("candidates"))


@app.route("/system_settings", methods=["GET","POST"])
@admin_required
@super_admin_required
def system_settings():
    conn=get_db()
    if request.method=="POST":
        school_name=request.form.get("school_name","").strip(); voting_status=request.form.get("voting_status","Open"); start_date=request.form.get("start_date") or None; end_date=request.form.get("end_date") or None; logo=request.form.get("current_logo") or "default.png"; uploaded=save_upload(request.files.get("logo")); logo=uploaded or logo
        conn.execute("UPDATE settings SET school_name=?,school_logo=?,voting_status=?,start_date=?,end_date=? WHERE id=1",(school_name,logo,voting_status,start_date,end_date)); conn.commit(); flash("Settings updated successfully.","success")
    settings=conn.execute("SELECT * FROM settings WHERE id=1").fetchone(); conn.close(); return render_template("admin/system_settings.html",settings=settings)


@app.route("/reset_election")
@admin_required
@super_admin_required
def reset_election():
    conn=get_db(); conn.execute("DELETE FROM votes"); conn.execute("UPDATE students SET has_voted=0"); conn.execute("UPDATE settings SET results_published=0 WHERE id=1"); conn.commit(); conn.close(); flash("Election reset successfully.","success"); return redirect(url_for("dashboard"))


@app.context_processor
def inject_settings():
    try:
        conn=get_db(); row=conn.execute("SELECT * FROM settings WHERE id=1").fetchone(); conn.close(); return {"site_settings": row}
    except sqlite3.Error:
        return {"site_settings": None}


if __name__ == "__main__":
    app.run(debug=True)
