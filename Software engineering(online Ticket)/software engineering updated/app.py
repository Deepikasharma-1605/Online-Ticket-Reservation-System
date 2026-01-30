import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"
DATABASE = os.path.join(os.path.dirname(__file__), "tickets.db")


# ---------------- Database helpers ----------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------- Database initialization ----------------
def init_db():
    db = get_db()

    # Create tables if they do not exist
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        date TEXT NOT NULL,
        total_seats INTEGER NOT NULL,
        price REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        seats INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(event_id) REFERENCES events(id)
    );
    """)

    # Ensure 'seats' column exists (for old databases)
    cur = db.cursor()
    cur.execute("PRAGMA table_info(tickets)")
    columns = [row["name"] for row in cur.fetchall()]
    if "seats" not in columns:
        db.execute("ALTER TABLE tickets ADD COLUMN seats INTEGER DEFAULT 0;")
    
    # Insert sample events if not present
    existing = db.execute("SELECT COUNT(*) as count FROM events").fetchone()["count"]
    if existing == 0:
        sample_events = [
            ("Music Concert", "City Arena", "2025-10-05", 200, 499.0),
            ("Tech Talk", "Lecture Hall 3", "2025-09-20", 150, 0.0),
            ("Food Festival", "Central Park", "2025-11-01", 500, 99.0),
        ]
        db.executemany(
            "INSERT INTO events (name, location, date, total_seats, price) VALUES (?, ?, ?, ?, ?)",
            sample_events,
        )

        # Add default admin user
        db.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), 1),
        )

    db.commit()


# ---------------- Routes ----------------
@app.route("/")
def index():
    db = get_db()
    events = db.execute("SELECT * FROM events ORDER BY date").fetchall()
    return render_template("index.html", events=events)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        existing = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))

        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        db.commit()
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = bool(user["is_admin"])
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials!", "danger")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    tickets = db.execute(
        """SELECT t.id, e.name, e.date, t.seats
           FROM tickets t 
           JOIN events e ON t.event_id = e.id
           WHERE t.user_id = ?""",
        (session["user_id"],),
    ).fetchall()
    return render_template("dashboard.html", tickets=tickets, username=session["username"])


@app.route("/book/<int:event_id>", methods=["GET", "POST"])
def book(event_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        seats = int(request.form["seats"])
        db = get_db()
        event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()

        if event and event["total_seats"] >= seats:
            db.execute(
                "INSERT INTO tickets (user_id, event_id, seats) VALUES (?, ?, ?)",
                (session["user_id"], event_id, seats),
            )
            db.execute(
                "UPDATE events SET total_seats = total_seats - ? WHERE id = ?",
                (seats, event_id),
            )
            db.commit()
            flash("Booking successful!", "success")
        else:
            flash("Not enough seats available.", "danger")
        return redirect(url_for("dashboard"))

    # If accessed via GET, redirect to homepage or dashboard
    return redirect(url_for("dashboard"))


@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect(url_for("login"))

    db = get_db()
    events = db.execute("SELECT * FROM events ORDER BY date").fetchall()
    return render_template("admin.html", events=events)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------- Main entry ----------------
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
