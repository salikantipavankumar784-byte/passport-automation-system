from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "passport-secret-key"


# Database connection
def get_db_connection():
    conn = sqlite3.connect("passport.db")
    conn.row_factory = sqlite3.Row
    return conn


# Create database tables
def init_db():

    conn = get_db_connection()

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    # Applications table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            date_of_birth TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            passport_type TEXT NOT NULL,
            status TEXT DEFAULT 'Submitted',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# Home
@app.route("/")
def home():
    return render_template("index.html")


# Register
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()

        try:

            conn.execute(
                """
                INSERT INTO users
                (name, email, password)
                VALUES (?, ?, ?)
                """,
                (name, email, hashed_password)
            )

            conn.commit()
            conn.close()

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            conn.close()

            return "Email already registered."

    return render_template("register.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("dashboard"))

        return "Invalid email or password."

    return render_template("login.html")


# Dashboard
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        name=session["user_name"]
    )


# Passport application
@app.route("/application", methods=["GET", "POST"])
def application():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        full_name = request.form["full_name"]
        date_of_birth = request.form["date_of_birth"]
        phone = request.form["phone"]
        address = request.form["address"]
        passport_type = request.form["passport_type"]

        conn = get_db_connection()

        cursor = conn.execute(
            """
            INSERT INTO applications
            (
                user_id,
                full_name,
                date_of_birth,
                phone,
                address,
                passport_type
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                full_name,
                date_of_birth,
                phone,
                address,
                passport_type
            )
        )

        conn.commit()

        application_id = cursor.lastrowid

        conn.close()

        return render_template(
            "application_success.html",
            application_id=application_id
        )

    return render_template("application.html")


# Application tracking
@app.route("/track", methods=["GET", "POST"])
def track():

    if "user_id" not in session:
        return redirect(url_for("login"))

    application = None

    if request.method == "POST":

        application_id = request.form["application_id"]

        conn = get_db_connection()

        application = conn.execute(
            """
            SELECT *
            FROM applications
            WHERE id = ?
            AND user_id = ?
            """,
            (application_id, session["user_id"])
        ).fetchone()

        conn.close()

    return render_template(
        "track.html",
        application=application
    )


# Logout
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


if __name__ == "__main__":

    init_db()

    app.run(debug=True)