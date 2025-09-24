from flask import Flask, request, jsonify, g, send_from_directory
import sqlite3
import os

app = Flask(__name__, static_folder=".", static_url_path="")

# Always point to the project folder, not random working dirs
DATABASE = os.path.join(os.path.dirname(__file__), "employees.db")

# -----------------------------
# Database Helpers
# -----------------------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullName TEXT NOT NULL,
                title TEXT,
                department TEXT,
                email TEXT,
                phone TEXT,
                photo TEXT
            )
        """)
        db.commit()
        print("✅ Database initialized at", DATABASE)

# -----------------------------
# API Routes
# -----------------------------
@app.route("/employees", methods=["GET"])
def get_employees():
    db = get_db()
    employees = db.execute("SELECT * FROM employees").fetchall()
    return jsonify([dict(e) for e in employees])

@app.route("/employees/<int:id>", methods=["GET"])
def get_employee(id):
    db = get_db()
    emp = db.execute("SELECT * FROM employees WHERE id=?", (id,)).fetchone()
    if emp:
        return jsonify(dict(emp))
    return jsonify({"error": "Employee not found"}), 404

@app.route("/employees", methods=["POST"])
def add_employee():
    data = request.json
    print("📥 Adding employee:", data)  # debug log
    with get_db() as db:
        cur = db.execute("""
            INSERT INTO employees (fullName, title, department, email, phone, photo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (data.get("fullName"), data.get("title"), data.get("department"),
              data.get("email"), data.get("phone"), data.get("photo")))
        db.commit()
        new_id = cur.lastrowid
    print(f"✅ Employee {new_id} inserted into DB")
    return jsonify({"id": new_id}), 201

@app.route("/employees/<int:id>", methods=["PUT"])
def update_employee(id):
    data = request.json
    print(f"✏️ Updating employee {id}:", data)
    with get_db() as db:
        db.execute("""
            UPDATE employees
            SET fullName=?, title=?, department=?, email=?, phone=?, photo=?
            WHERE id=?
        """, (data.get("fullName"), data.get("title"), data.get("department"),
              data.get("email"), data.get("phone"), data.get("photo"), id))
        db.commit()
    return jsonify({"status": "updated"})

@app.route("/employees/<int:id>", methods=["DELETE"])
def delete_employee(id):
    print(f"🗑️ Deleting employee {id}")
    with get_db() as db:
        db.execute("DELETE FROM employees WHERE id=?", (id,))
        db.commit()
    return jsonify({"status": "deleted"})

# -----------------------------
# Serve HTML & JS
# -----------------------------
@app.route("/")
def index():
    return send_from_directory(".", "manager-portal.html")

@app.route("/employee.html")
def employee_page():
    return send_from_directory(".", "employee.html")

@app.route("/manager-portal.html")
def portal_page():
    return send_from_directory(".", "manager-portal.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(".", path)

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
