import datetime
import functools
import os
import sqlite3

import jwt
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount REAL NOT NULL CHECK (amount > 0),
    category TEXT NOT NULL,
    note TEXT DEFAULT '',
    date TEXT NOT NULL
);
"""


def create_app(config=None):
    app = Flask(__name__, static_folder="static")
    app.config.update(
        DATABASE=os.path.join(os.path.dirname(__file__), "expenses.db"),
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production"),
    )
    if config:
        app.config.update(config)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with app.app_context():
        get_db().executescript(SCHEMA)

    def error(message, status):
        return jsonify({"error": message}), status

    def token_required(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return error("Missing or malformed token", 401)
            try:
                payload = jwt.decode(header[7:], app.config["SECRET_KEY"], algorithms=["HS256"])
                g.user_id = int(payload["sub"])
            except (jwt.InvalidTokenError, ValueError, KeyError):
                return error("Invalid or expired token", 401)
            return view(*args, **kwargs)
        return wrapped

    def parse_expense(data):
        data = data or {}
        try:
            amount = float(data.get("amount"))
        except (TypeError, ValueError):
            return None, "amount must be a number"
        if amount <= 0:
            return None, "amount must be greater than 0"
        category = str(data.get("category", "")).strip()
        if not category or len(category) > 40:
            return None, "category is required (max 40 characters)"
        date = data.get("date") or datetime.date.today().isoformat()
        try:
            datetime.date.fromisoformat(date)
        except (TypeError, ValueError):
            return None, "date must be YYYY-MM-DD"
        return {"amount": round(amount, 2), "category": category,
                "note": str(data.get("note", ""))[:200], "date": date}, None

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.post("/api/register")
    def register():
        data = request.get_json(silent=True) or {}
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        if not 3 <= len(username) <= 30:
            return error("username must be 3-30 characters", 400)
        if len(password) < 6:
            return error("password must be at least 6 characters", 400)
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                       (username, generate_password_hash(password)))
            db.commit()
        except sqlite3.IntegrityError:
            return error("username already taken", 409)
        return jsonify({"message": "registered"}), 201

    @app.post("/api/login")
    def login():
        data = request.get_json(silent=True) or {}
        row = get_db().execute("SELECT * FROM users WHERE username = ?",
                               (str(data.get("username", "")).strip(),)).fetchone()
        if not row or not check_password_hash(row["password_hash"], str(data.get("password", ""))):
            return error("invalid username or password", 401)
        token = jwt.encode(
            {"sub": str(row["id"]),
             "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=12)},
            app.config["SECRET_KEY"], algorithm="HS256")
        return jsonify({"token": token})

    @app.get("/api/expenses")
    @token_required
    def list_expenses():
        sql, params = "SELECT * FROM expenses WHERE user_id = ?", [g.user_id]
        category = request.args.get("category")
        if category:
            sql += " AND category = ?"
            params.append(category)
        rows = get_db().execute(sql + " ORDER BY date DESC, id DESC", params).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.post("/api/expenses")
    @token_required
    def create_expense():
        clean, err = parse_expense(request.get_json(silent=True))
        if err:
            return error(err, 400)
        db = get_db()
        cur = db.execute(
            "INSERT INTO expenses (user_id, amount, category, note, date) VALUES (?, ?, ?, ?, ?)",
            (g.user_id, clean["amount"], clean["category"], clean["note"], clean["date"]))
        db.commit()
        return jsonify({"id": cur.lastrowid, **clean}), 201

    @app.put("/api/expenses/<int:expense_id>")
    @token_required
    def update_expense(expense_id):
        clean, err = parse_expense(request.get_json(silent=True))
        if err:
            return error(err, 400)
        db = get_db()
        cur = db.execute(
            "UPDATE expenses SET amount=?, category=?, note=?, date=? WHERE id=? AND user_id=?",
            (clean["amount"], clean["category"], clean["note"], clean["date"], expense_id, g.user_id))
        db.commit()
        if cur.rowcount == 0:
            return error("expense not found", 404)
        return jsonify({"id": expense_id, **clean})

    @app.delete("/api/expenses/<int:expense_id>")
    @token_required
    def delete_expense(expense_id):
        db = get_db()
        cur = db.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (expense_id, g.user_id))
        db.commit()
        if cur.rowcount == 0:
            return error("expense not found", 404)
        return "", 204

    @app.get("/api/summary")
    @token_required
    def summary():
        rows = get_db().execute(
            "SELECT category, ROUND(SUM(amount), 2) AS total, COUNT(*) AS count "
            "FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (g.user_id,)).fetchall()
        by_category = [dict(r) for r in rows]
        return jsonify({"total": round(sum(r["total"] for r in by_category), 2),
                        "by_category": by_category})

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
