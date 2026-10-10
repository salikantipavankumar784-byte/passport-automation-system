from flask import send_file
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
app = Flask(__name__)

app.secret_key = "passport-secret-key"
app.config["UPLOAD_FOLDER"] = "uploads"

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
    conn.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL,
        document_name TEXT NOT NULL,
        FOREIGN KEY (application_id) REFERENCES applications(id)
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

        application_id = cursor.lastrowid

        document = request.files["document"]

        if document and document.filename:

            filename = secure_filename(document.filename)

            document.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

            conn.execute(
                """
                INSERT INTO documents (application_id, document_name)
                VALUES (?, ?)
                """,
                (application_id, filename)
            )

        conn.commit()
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

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        print("Username entered:", repr(username))
        print("Password length:", len(password))

        if username == "admin" and password == "admin123":
            session["admin"] = True
            return redirect(url_for("admin"))

        return "Invalid admin username or password."

    return render_template("admin_login.html")




@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    total = conn.execute(
        "SELECT COUNT(*) FROM applications"
    ).fetchone()[0]

    approved = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status = 'Approved'"
    ).fetchone()[0]

    under_review = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status = 'Under Review'"
    ).fetchone()[0]

    rejected = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE status = 'Rejected'"
    ).fetchone()[0]

    # Count applications by status for the pie chart
    status_rows = conn.execute("""
        SELECT status, COUNT(*) AS count
        FROM applications
        GROUP BY status
    """).fetchall()

    status_labels = [row["status"] for row in status_rows]
    status_values = [row["count"] for row in status_rows]

    conn.close()

    return render_template(
        "admin.html",
        total=total,
        approved=approved,
        under_review=under_review,
        rejected=rejected,
        status_labels=status_labels,
        status_values=status_values
    )

@app.route("/admin/users")
def admin_users():

    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    users = conn.execute(
        "SELECT id, name, email FROM users"
    ).fetchall()

    conn.close()

    return render_template(
        "admin_users.html",
        users=users
    )


@app.route("/admin/applications")
def admin_applications():

    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    applications = conn.execute(
        "SELECT * FROM applications"
    ).fetchall()

    document_rows = conn.execute(
        "SELECT application_id, document_name FROM documents"
    ).fetchall()

    documents = {}

    for document in document_rows:
        documents[document["application_id"]] = document["document_name"]

    conn.close()

    return render_template(
        "admin_applications.html",
        applications=applications,
        documents=documents
    )

@app.route("/admin/update-status/<int:application_id>", methods=["POST"])
def update_status(application_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    status = request.form["status"]

    conn = get_db_connection()

    conn.execute(
        """
        UPDATE applications
        SET status = ?
        WHERE id = ?
        """,
        (status, application_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_applications"))

@app.route("/admin/download-report")
def download_report():
    # Allow only logged-in admins
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    applications = conn.execute("""
        SELECT id, full_name, date_of_birth, phone,
               address, passport_type, status
        FROM applications
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    # Create PDF in memory
    pdf_buffer = BytesIO()

    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4)
    )

    styles = getSampleStyleSheet()
    content = []

    content.append(
        Paragraph("Passport Application Report", styles["Title"])
    )
    content.append(Spacer(1, 15))

    content.append(Paragraph(
        f"Total Applications: {len(applications)}",
        styles["Normal"]
    ))
    content.append(Spacer(1, 15))

    data = [[
        "ID", "Full Name", "Date of Birth",
        "Phone", "Address", "Passport Type", "Status"
    ]]

    for app_row in applications:
        data.append([
            str(app_row["id"]),
            str(app_row["full_name"]),
            str(app_row["date_of_birth"]),
            str(app_row["phone"]),
            str(app_row["address"]),
            str(app_row["passport_type"]),
            str(app_row["status"])
        ])

    table = Table(
        data,
        repeatRows=1,
        colWidths=[35, 100, 75, 75, 150, 85, 75]
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123b65")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f1f5f9")]),
    ]))

    content.append(table)
    doc.build(content)

    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="passport_application_report.pdf"
    )

@app.route("/admin-logout")
def admin_logout():

    session.pop("admin", None)

    return redirect(url_for("admin_login"))
# Logout
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))
# Uploaded documents
@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


if __name__ == "__main__":

    init_db()

    app.run(debug=True)