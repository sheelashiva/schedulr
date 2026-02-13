from flask import Flask, render_template, request, redirect, session, jsonify, url_for
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

DB_NAME = "schedulr.db"


# ---------------- DB Helpers ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mentors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mentor_name TEXT NOT NULL,
        mentor_code TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        mentor_id INTEGER,
        FOREIGN KEY (mentor_id) REFERENCES mentors(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        exam_date TEXT NOT NULL,
        total_units INTEGER NOT NULL,
        difficulty TEXT NOT NULL,
        units_completed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    conn.commit()

    # Create default mentor (so your mentor login works immediately)
    cur.execute("SELECT * FROM mentors WHERE mentor_code=?", ("MENTOR123",))
    existing = cur.fetchone()
    if not existing:
        cur.execute(
            "INSERT INTO mentors (mentor_name, mentor_code, password_hash) VALUES (?, ?, ?)",
            ("Default Mentor", "MENTOR123", generate_password_hash("mentorpass"))
        )
        conn.commit()

    conn.close()


init_db()


# ---------------- Auth Helpers ----------------
def login_required():
    return "user_id" in session


def mentor_login_required():
    return "mentor_id" in session


# ---------------- Student Auth ----------------
@app.route("/", methods=["GET"])
def home():
    # Student login page
    if login_required():
        return redirect("/add-subject")
    return render_template("student_login.html")


@app.route("/login", methods=["POST"])
def student_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cur.fetchone()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return render_template("student_login.html", error="Invalid username or password")

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["mentor_id_for_user"] = user["mentor_id"]
    return redirect("/add-subject")


@app.route("/register", methods=["GET"])
def register_page():
    return render_template("student_register.html")


@app.route("/register", methods=["POST"])
def student_register():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    mentor_code = request.form.get("mentor_code", "").strip()

    if not username or not password:
        return render_template("student_register.html", error="Username and password required")

    conn = get_db()
    cur = conn.cursor()

    mentor_id = None
    if mentor_code:
        cur.execute("SELECT id FROM mentors WHERE mentor_code=?", (mentor_code,))
        m = cur.fetchone()
        if not m:
            conn.close()
            return render_template("student_register.html", error="Invalid mentor code")
        mentor_id = m["id"]

    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, mentor_id) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), mentor_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return render_template("student_register.html", error="Username already exists")

    conn.close()
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- Student Pages ----------------
@app.route("/add-subject")
def add_subject_page():
    if not login_required():
        return redirect("/")
    return render_template("add_subject.html", username=session.get("username"))


@app.route("/dashboard")
def dashboard_page():
    if not login_required():
        return redirect("/")
    return render_template("dashboard.html", username=session.get("username"))


# ---------------- Student API ----------------
@app.route("/api/subjects", methods=["GET"])
def api_get_subjects():
    if not login_required():
        return jsonify({"error": "not logged in"}), 401

    user_id = session["user_id"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM subjects WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = cur.fetchall()
    conn.close()

    subjects = [dict(r) for r in rows]
    return jsonify({"subjects": subjects})


@app.route("/api/subjects", methods=["POST"])
def api_add_subject():
    if not login_required():
        return jsonify({"error": "not logged in"}), 401

    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    exam_date = (data.get("exam_date") or "").strip()
    total_units = data.get("total_units")
    difficulty = (data.get("difficulty") or "Medium").strip()

    if not name or not exam_date or not total_units:
        return jsonify({"error": "Missing fields"}), 400

    try:
        total_units = int(total_units)
        if total_units <= 0:
            return jsonify({"error": "Total units must be > 0"}), 400
    except:
        return jsonify({"error": "Total units must be a number"}), 400

    # Validate date basic format (yyyy-mm-dd from input type=date)
    try:
        datetime.strptime(exam_date, "%Y-%m-%d")
    except:
        return jsonify({"error": "Invalid exam date"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO subjects (user_id, name, exam_date, total_units, difficulty, units_completed, created_at)
        VALUES (?, ?, ?, ?, ?, 0, ?)
    """, (session["user_id"], name, exam_date, total_units, difficulty, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@app.route("/api/subjects/<int:subject_id>", methods=["PATCH"])
def api_update_subject(subject_id):
    if not login_required():
        return jsonify({"error": "not logged in"}), 401

    data = request.get_json(force=True)
    units_completed = data.get("units_completed")

    try:
        units_completed = int(units_completed)
        if units_completed < 0:
            units_completed = 0
    except:
        return jsonify({"error": "units_completed must be number"}), 400

    conn = get_db()
    cur = conn.cursor()
    # Check ownership + get total_units
    cur.execute("SELECT * FROM subjects WHERE id=? AND user_id=?", (subject_id, session["user_id"]))
    s = cur.fetchone()
    if not s:
        conn.close()
        return jsonify({"error": "not found"}), 404

    if units_completed > int(s["total_units"]):
        units_completed = int(s["total_units"])

    cur.execute("UPDATE subjects SET units_completed=? WHERE id=?", (units_completed, subject_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/subjects/<int:subject_id>", methods=["DELETE"])
def api_delete_subject(subject_id):
    if not login_required():
        return jsonify({"error": "not logged in"}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM subjects WHERE id=? AND user_id=?", (subject_id, session["user_id"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ---------------- Mentor Auth ----------------
@app.route("/mentor/login", methods=["GET"])
def mentor_login_page():
    return render_template("mentor_login.html")


@app.route("/mentor/login", methods=["POST"])
def mentor_login():
    code = request.form.get("mentor_code", "").strip()
    password = request.form.get("password", "")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM mentors WHERE mentor_code=?", (code,))
    mentor = cur.fetchone()
    conn.close()

    if not mentor or not check_password_hash(mentor["password_hash"], password):
        return render_template("mentor_login.html", error="Invalid mentor login")

    session.clear()
    session["mentor_id"] = mentor["id"]
    session["mentor_name"] = mentor["mentor_name"]
    return redirect("/mentor/dashboard")


@app.route("/mentor/logout")
def mentor_logout():
    session.clear()
    return redirect("/mentor/login")


@app.route("/mentor/dashboard")
def mentor_dashboard():
    if not mentor_login_required():
        return redirect("/mentor/login")
    return render_template("mentor_dashboard.html", mentor_name=session.get("mentor_name"))


@app.route("/mentor/api/students")
def mentor_api_students():
    if not mentor_login_required():
        return jsonify({"error": "not logged in"}), 401

    mentor_id = session["mentor_id"]
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, username FROM users WHERE mentor_id=? ORDER BY username", (mentor_id,))
    students = cur.fetchall()

    result = []
    for st in students:
        cur.execute("SELECT * FROM subjects WHERE user_id=? ORDER BY id DESC", (st["id"],))
        subs = [dict(r) for r in cur.fetchall()]
        result.append({"student": dict(st), "subjects": subs})

    conn.close()
    return jsonify({"students": result})


if __name__ == "__main__":
    app.run(debug=True)