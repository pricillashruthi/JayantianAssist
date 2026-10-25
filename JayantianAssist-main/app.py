"""Kristu Jayanti University chatbot: sign up, log in, chat.

Run:  python app.py   then open http://127.0.0.1:5000
"""
import json
import os
import re
import secrets
import sqlite3
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from chatbot import Chatbot

ALLOWED_DOMAIN = "kristujayanti.com"
DB_PATH = Path(__file__).parent / "users.db"

app = Flask(__name__)
# Set SECRET_KEY in the environment for production; a random key is used otherwise
# (sessions will reset whenever the server restarts).
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

bot = Chatbot()

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@kristujayanti\.com$", re.IGNORECASE)

DEGREE_MAP = {
    "mca": "Master of Computer Applications (MCA)",
    "bca": "Bachelor of Computer Applications (BCA)",
    "mba": "Master of Business Administration (MBA)",
    "bba": "Bachelor of Business Administration (BBA)",
    "bcom": "Bachelor of Commerce (B.Com)",
    "bsc": "Bachelor of Science (B.Sc)",
    "ba": "Bachelor of Arts (BA)",
    "mcom": "Master of Commerce (M.Com)",
    "msc": "Master of Science (M.Sc)",
    "ma": "Master of Arts (MA)",
    "msw": "Master of Social Work (MSW)",
    "llb": "Bachelor of Law (LLB)",
}


def parse_student_profile(email: str):
    prefix = email.split("@")[0].lower() if email else ""
    match = re.match(r"^(\d{2})([a-z]+)(\d.*)?$", prefix)
    if match:
        year = "20" + match.group(1)
        code = match.group(2)
        deg_name = None
        for k, v in DEGREE_MAP.items():
            if code.startswith(k):
                deg_name = v
                break
        if not deg_name:
            deg_name = code.upper()
        return {
            "batch": f"Class of {year}",
            "program": deg_name,
            "reg_no": prefix.upper(),
        }
    return {
        "batch": "Jayantian",
        "program": "Kristu Jayanti College",
        "reg_no": prefix.upper() if prefix else "STUDENT",
    }


# ---------- database ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id))"""
        )


# ---------- helpers ----------
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf") or request.headers.get("X-CSRF-Token")
        if not sent or sent != session.get("csrf"):
            abort(400, "Invalid CSRF token")


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def valid_password(pw: str):
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Password must contain letters and numbers."
    return None


# ---------- routes ----------
@app.route("/")
def index():
    return redirect(url_for("chat") if "user_id" in session else url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        error = None
        if not name:
            error = "Please enter your name."
        elif not EMAIL_RE.match(email):
            error = f"Only college emails ending in @{ALLOWED_DOMAIN} are allowed (e.g. example@{ALLOWED_DOMAIN})."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            error = valid_password(password)

        if not error:
            try:
                db = get_db()
                db.execute("INSERT INTO users (name, email, password_hash) VALUES (?,?,?)",
                           (name, email, generate_password_hash(password)))
                db.commit()
            except sqlite3.IntegrityError:
                error = "An account with this email already exists. Please log in."
            else:
                flash("Account created. Please log in.", "ok")
                return redirect(url_for("login"))
        flash(error, "error")
        return render_template("signup.html", name=name, email=email, domain=ALLOWED_DOMAIN)
    return render_template("signup.html", name="", email="", domain=ALLOWED_DOMAIN)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "1"
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.permanent = remember
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["email"] = user["email"]
            return redirect(url_for("chat"))
        flash("Invalid email or password.", "error")
        return render_template("login.html", email=email)
    return render_template("login.html", email="")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        error = None
        if not email:
            error = "Please enter your college email."
        elif not EMAIL_RE.match(email):
            error = f"Only college emails ending in @{ALLOWED_DOMAIN} are allowed (e.g. example@{ALLOWED_DOMAIN})."
        elif not password:
            error = "Please enter a new password."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            error = valid_password(password)

        if not error:
            db = get_db()
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not user:
                error = "No account found with this college email. Please check your email or sign up."
            else:
                db.execute(
                    "UPDATE users SET password_hash = ? WHERE email = ?",
                    (generate_password_hash(password), email),
                )
                db.commit()
                flash("Your password has been reset successfully. Please log in.", "ok")
                return redirect(url_for("login"))

        flash(error, "error")
        return render_template("forgot_password.html", email=email, domain=ALLOWED_DOMAIN)

    initial_email = request.args.get("email", "").strip().lower()
    return render_template("forgot_password.html", email=initial_email, domain=ALLOWED_DOMAIN)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/chat")
@login_required
def chat():
    email = session.get("email", "")
    profile = parse_student_profile(email)
    return render_template("chat.html", name=session.get("name", ""), email=email, profile=profile)


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="Empty message"), 400

    user_id = session["user_id"]
    db = get_db()
    # Save user message
    db.execute(
        "INSERT INTO messages (user_id, role, content) VALUES (?, 'user', ?)",
        (user_id, message[:500]),
    )
    db.commit()

    ans = bot.answer(message[:500])
    answer_text = ans.get("answer") or ""
    sources_str = json.dumps(ans.get("sources", []))

    # Save bot answer
    db.execute(
        "INSERT INTO messages (user_id, role, content, sources_json) VALUES (?, 'bot', ?, ?)",
        (user_id, answer_text, sources_str),
    )
    db.commit()
    return jsonify(ans)


@app.route("/api/history", methods=["GET"])
@login_required
def api_history():
    user_id = session["user_id"]
    rows = get_db().execute(
        "SELECT role, content, sources_json, created_at FROM messages WHERE user_id = ? ORDER BY id ASC",
        (user_id,),
    ).fetchall()
    history = []
    for r in rows:
        sources = []
        if r["sources_json"]:
            try:
                sources = json.loads(r["sources_json"])
            except Exception:
                sources = []
        history.append({
            "role": r["role"],
            "content": r["content"],
            "sources": sources,
            "created_at": r["created_at"],
        })
    return jsonify(history)


@app.route("/api/clear", methods=["POST"])
@login_required
def api_clear():
    user_id = session["user_id"]
    db = get_db()
    db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
    db.commit()
    return jsonify(ok=True)


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
