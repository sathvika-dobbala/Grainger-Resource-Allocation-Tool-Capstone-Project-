from flask import Flask, request, jsonify, g, send_from_directory, session
from schema import init_db, get_db, insert_dummy_data
from pypdf import PdfReader
from ai_helper import extract_skills_from_text, get_ai_team_recommendations
import sqlite3
import os
import csv
from io import TextIOWrapper

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "employees.db")

# ðŸŸ¢ Secret key for Flask sessions
app.secret_key = "super_secret_demo_key"

# ============================================================
# App Context + DB Handling
# ============================================================
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# ============================================================
# ðŸŸ¢ LOGIN / LOGOUT / SESSION CHECK
# ============================================================
@app.route("/api/login", methods=["POST"])
def login():
    """Simple login for manager demo."""
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "error": "Missing credentials"}), 400

    db = get_db()
    manager = db.execute("""
        SELECT m.managerID, m.firstname, m.lastname, m.email, m.password, 
               d.depID, d.departmentname
        FROM Managers m
        JOIN Departments d ON m.department = d.depID
        WHERE m.email = ?
    """, (email,)).fetchone()

    if not manager:
        return jsonify({"success": False, "error": "Manager not found"}), 404

    if manager["password"] != password:
        return jsonify({"success": False, "error": "Invalid password"}), 401

    # âœ… Store session info
    session["manager_id"] = manager["managerID"]
    session["manager_name"] = f"{manager['firstname']} {manager['lastname']}"
    session["manager_email"] = manager["email"]
    session["department_id"] = manager["depID"]
    session["department_name"] = manager["departmentname"]

    return jsonify({
        "success": True,
        "manager_id": session["manager_id"],
        "manager_name": session["manager_name"],
        "manager_email": session["manager_email"],
        "department_id": session["department_id"],
        "department_name": session["department_name"]
    })


@app.route("/api/me", methods=["GET"])
def get_current_manager():
    """Return current session info for logged-in manager."""
    if "manager_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    return jsonify({
        "success": True,
        "manager_id": session["manager_id"],
        "manager_name": session["manager_name"],
        "manager_email": session["manager_email"],
        "department_id": session["department_id"],
        "department_name": session["department_name"]
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    """Logout current manager."""
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})

# ============================================================
# Departments
# ============================================================
@app.route("/departments", methods=["GET"])
def get_departments():
    db = get_db()
    departments = db.execute("SELECT * FROM Departments ORDER BY departmentname").fetchall()
    return jsonify([dict(d) for d in departments])

# ============================================================
# Employees
# ============================================================
@app.route("/employees", methods=["GET"])
def get_employees():
    db = get_db()
    dept_filter = ""
    params = ()
    if "department_id" in session:
        dept_filter = "WHERE e.department = ?"
        params = (session["department_id"],)

    rows = db.execute(f"""
        SELECT e.empID AS id,
               e.firstname || ' ' || e.lastname AS fullName,
               e.firstname, e.lastname, e.title,
               e.department, d.departmentname,
               e.email, e.phone, e.photo
        FROM Employees e
        LEFT JOIN Departments d ON e.department = d.depID
        {dept_filter}
        ORDER BY e.empID
    """, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/employees/<int:emp_id>", methods=["GET"])
def get_employee(emp_id):
    db = get_db()
    emp = db.execute("""
        SELECT e.empID AS empID, e.firstname, e.lastname, e.title,
               e.department, d.departmentname, e.email, e.phone, e.photo
        FROM Employees e
        LEFT JOIN Departments d ON e.department = d.depID
        WHERE e.empID = ?
    """, (emp_id,)).fetchone()
    if not emp:
        return jsonify({"error": "Employee not found"}), 404
    return jsonify(dict(emp))

@app.route("/employees/<int:emp_id>", methods=["PUT"])
def update_employee(emp_id):
    data = request.get_json()
    db = get_db()

    if not data:
        return jsonify({"error": "Missing employee data"}), 400

    current_emp = db.execute(
        "SELECT department FROM Employees WHERE empID = ?", (emp_id,)
    ).fetchone()

    if not current_emp:
        return jsonify({"error": "Employee not found"}), 404

    old_dept = int(current_emp["department"]) if current_emp["department"] else None
    new_dept = int(data.get("department")) if data.get("department") else None
    manager_dept = int(session.get("department_id", 0))

    # ✅ Perform update no matter what
    db.execute("""
        UPDATE Employees
        SET firstname = ?, lastname = ?, title = ?, department = ?, email = ?, phone = ?, photo = ?
        WHERE empID = ?
    """, (
        data.get("firstname", ""), data.get("lastname", ""), data.get("title", ""),
        new_dept, data.get("email", ""), data.get("phone", ""), data.get("photo", ""), emp_id
    ))
    db.commit()

    # ✅ If manager moved employee to another department, tell frontend to redirect
    if new_dept != manager_dept:
        return jsonify({
            "message": "Employee updated successfully, but you no longer have access.",
            "redirect_denied": True
        }), 200

    return jsonify({"message": "Employee updated successfully.", "redirect_denied": False})



# @app.route("/employees/<int:emp_id>", methods=["PUT"])
# def update_employee(emp_id):
#     data = request.get_json()
#     db = get_db()
#     if not data:
#         return jsonify({"error": "Missing employee data"}), 400

#     db.execute("""
#         UPDATE Employees
#         SET firstname = ?, lastname = ?, title = ?, department = ?, email = ?, phone = ?, photo = ?
#         WHERE empID = ?
#     """, (
#         data.get("firstname", ""), data.get("lastname", ""), data.get("title", ""),
#         data.get("department", None), data.get("email", ""), data.get("phone", ""),
#         data.get("photo", ""), emp_id
#     ))
#     db.commit()
#     return jsonify({"message": "Employee updated successfully."})


@app.route("/employees", methods=["POST"])
def add_employee():
    data = request.get_json()
    db = get_db()
    if not data:
        return jsonify({"error": "Missing employee data"}), 400

    cursor = db.execute("""
        INSERT INTO Employees (firstname, lastname, title, department, email, phone, photo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("firstname", ""), data.get("lastname", ""), data.get("title", ""),
        data.get("department", None), data.get("email", ""), data.get("phone", ""), data.get("photo", "")
    ))
    db.commit()
    return jsonify({"message": "Employee added successfully.", "id": cursor.lastrowid}), 201


@app.route("/import-csv", methods=["POST"])
def import_csv():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    db = get_db()
    reader = csv.DictReader(TextIOWrapper(file, encoding="utf-8"))
    count = 0
    for row in reader:
        db.execute("""
            INSERT INTO Employees (firstname, lastname, title, department, email, phone, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("firstname", ""), row.get("lastname", ""), row.get("title", ""),
            row.get("department", None), row.get("email", ""), row.get("phone", ""), row.get("photo", "")
        ))
        count += 1
    db.commit()
    return jsonify({"message": f"Imported {count} employees."}), 201

# ============================================================
# Employee Skills
# ============================================================
@app.route("/employees/<int:emp_id>/skills", methods=["GET"])
def get_employee_skills(emp_id):
    db = get_db()
    skills = db.execute("""
        SELECT s.skillID, s.skillName, sc.skillCategoryname, es.profiencylevel, es.evidence
        FROM EmployeeSkills es
        JOIN Skills s ON es.skillID = s.skillID
        LEFT JOIN SkillCategories sc ON s.skillCategoryID = sc.skillCategoryID
        WHERE es.empID = ?
        ORDER BY s.skillName
    """, (emp_id,)).fetchall()
    return jsonify({"skills": [dict(row) for row in skills]})


@app.route("/employees/<int:emp_id>/skills", methods=["PUT"])
def update_employee_skills(emp_id):
    data = request.get_json()
    new_skills = data.get("skills", [])
    db = get_db()
    db.execute("DELETE FROM EmployeeSkills WHERE empID = ?", (emp_id,))
    for s in new_skills:
        db.execute("""
            INSERT INTO EmployeeSkills (empID, skillID, profiencylevel, evidence)
            VALUES (?, ?, ?, ?)
        """, (emp_id, s.get("skillID"), s.get("profiencylevel", 1), s.get("evidence", "")))
    db.commit()
    return jsonify({"message": "Employee skills updated successfully."})

# ============================================================
# ðŸŸ¢ AI: Extract Skills (Department Scoped)
# ============================================================
@app.route("/api/projects/extract-skills", methods=["POST"])
def extract_skills_api():
    try:
        if "manager_id" not in session or "department_id" not in session:
            return jsonify({"success": False, "error": "Not logged in"}), 403

        if "prd" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file = request.files["prd"]
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"success": False, "error": "Only PDF supported"}), 400

        reader = PdfReader(file.stream)
        pages = min(len(reader.pages), 8)
        text = []
        for i in range(pages):
            try:
                text.append(reader.pages[i].extract_text() or "")
            except Exception:
                pass
        prd_text = "\n\n".join(text).strip()
        if not prd_text:
            return jsonify({"success": False, "error": "Could not extract text"}), 400

        conn = get_db()
        dept_id = session["department_id"]
        skills = extract_skills_from_text(prd_text, conn, dept_id)
        return jsonify({"success": True, "skills": skills, "department_id": dept_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# ðŸŸ¢ AI: Generate Team (Department Scoped)
# ============================================================
@app.route("/api/projects/generate-teams", methods=["POST"])
def generate_team_recommendations():
    try:
        if "manager_id" not in session or "department_id" not in session:
            return jsonify({"error": "Not logged in"}), 403

        data = request.get_json(silent=True) or {}
        skills_needed = data.get('skills', [])
        team_size = int(data.get('teamSize', 4))
        department_id = session["department_id"]

        if not skills_needed:
            return jsonify({"error": "No skills provided"}), 400

        result = get_ai_team_recommendations(skills_needed, department_id=department_id, k=team_size)
        return jsonify({
            "success": True,
            "department_id": department_id,
            "top5_skills": result["top5_skills"],
            "recommendations": result["recommended_team"],
            "ai_provider": result.get("ai_provider", "openai")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# Create Project
# ============================================================
@app.route("/api/projects", methods=["POST"])
def create_project():
    """Create a new project with team members and skills."""
    try:
        if "manager_id" not in session:
            return jsonify({"success": False, "error": "Not logged in"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        project_name = data.get("projectName")
        status = data.get("status", "Not Started")
        start_date = data.get("startDate")
        end_date = data.get("endDate")
        manager_notes = data.get("managerNotes", "")
        skills = data.get("skills", [])
        team_members = data.get("teamMembers", [])
        
        if not project_name:
            return jsonify({"success": False, "error": "Project name is required"}), 400
        
        if not team_members:
            return jsonify({"success": False, "error": "At least one team member is required"}), 400
        
        db = get_db()
        
        # Get the first team member's team ID (simplified approach)
        # In a real app, you might want to create a new team or use manager's team
        first_member = db.execute("""
            SELECT teamID FROM Employees WHERE empID = ?
        """, (team_members[0],)).fetchone()
        
        if not first_member or not first_member["teamID"]:
            # If no team exists, use team ID 1 as default (or create a new team)
            team_id = 1
        else:
            team_id = first_member["teamID"]
        
        # Check if project name already exists
        existing = db.execute("""
            SELECT projectID FROM Projects WHERE projectName = ?
        """, (project_name,)).fetchone()
        
        if existing:
            return jsonify({"success": False, "error": "Project name already exists"}), 400
        
        # Insert the project
        cursor = db.execute("""
            INSERT INTO Projects (teamID, projectName, status, startDate, endDate)
            VALUES (?, ?, ?, ?, ?)
        """, (team_id, project_name, status, start_date, end_date))
        
        project_id = cursor.lastrowid
        
        # Add skills to project (if we have skill IDs)
        # For now, we'll skip skill insertion since skills are passed as names, not IDs
        # You could add logic here to look up skill IDs from names if needed
        
        # Assign team members to project
        for i, emp_id in enumerate(team_members):
            # First person is the lead, others are contributors
            role = "Lead" if i == 0 else "Contributor"
            db.execute("""
                INSERT INTO ProjectAssignment (projectID, empID, role)
                VALUES (?, ?, ?)
            """, (project_id, emp_id, role))
        
        db.commit()
        
        return jsonify({
            "success": True,
            "projectId": project_id,
            "message": f"Project '{project_name}' created successfully"
        })
        
    except sqlite3.IntegrityError as e:
        return jsonify({"success": False, "error": f"Database error: {str(e)}"}), 400
    except Exception as e:
        import traceback
        print(f"Error in create_project: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500

# ============================================================
# List Projects (department-scoped)
# ============================================================
@app.route("/api/projects", methods=["GET"])
def list_projects():
    if "manager_id" not in session or "department_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    db = get_db()
    dept_id = session["department_id"]

    rows = db.execute("""
        SELECT 
            p.projectID,
            p.projectName,
            p.status,
            p.startDate,
            p.endDate,
            COUNT(pa.empID) AS teamSize
        FROM Projects p
        JOIN Teams t ON p.teamID = t.teamID
        LEFT JOIN ProjectAssignment pa ON pa.projectID = p.projectID
        WHERE t.department = ?
        GROUP BY p.projectID
        ORDER BY COALESCE(p.startDate, date('now')) DESC, p.projectID DESC
    """, (dept_id,)).fetchall()

    projects = [dict(r) for r in rows]

    # (Optional) include member names
    for proj in projects:
        members = db.execute("""
            SELECT e.empID, e.firstname || ' ' || e.lastname AS fullName, pa.role
            FROM ProjectAssignment pa
            JOIN Employees e ON e.empID = pa.empID
            WHERE pa.projectID = ?
            ORDER BY pa.role = 'Lead' DESC, e.lastname
        """, (proj["projectID"],)).fetchall()
        proj["members"] = [dict(m) for m in members]

    return jsonify({"success": True, "projects": projects})

# ============================================================
# Other Routes
# ============================================================
@app.route("/employees/<int:emp_id>", methods=["DELETE"])
def delete_employee(emp_id):
    db = get_db()
    emp = db.execute("SELECT * FROM Employees WHERE empID = ?", (emp_id,)).fetchone()
    if not emp:
        return jsonify({"error": "Employee not found"}), 404
    db.execute("DELETE FROM Employees WHERE empID = ?", (emp_id,))
    db.commit()
    return jsonify({"message": "Employee deleted successfully"}), 200


@app.route("/skills", methods=["GET"])
def get_all_skills():
    db = get_db()
    q = request.args.get("q", "").lower()
    rows = db.execute("""
        SELECT s.skillID, s.skillName, sc.skillCategoryname
        FROM Skills s
        LEFT JOIN SkillCategories sc ON s.skillCategoryID = sc.skillCategoryID
        ORDER BY s.skillName
    """).fetchall()
    skills = [dict(r) for r in rows]
    if q:
        skills = [s for s in skills if q in s["skillName"].lower()]
    return jsonify(skills)


@app.route("/employees/<int:emp_id>/projects", methods=["GET"])
def get_employee_projects(emp_id):
    db = get_db()
    rows = db.execute("""
        SELECT p.projectID, p.projectName, p.status, p.startDate, p.endDate, pa.role
        FROM ProjectAssignment pa
        JOIN Projects p ON pa.projectID = p.projectID
        WHERE pa.empID = ?
        ORDER BY p.startDate DESC
    """, (emp_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

# ============================================================
# Serve Pages
# ============================================================
@app.route("/")
def index():
    return send_from_directory(".", "login.html")

@app.route("/login.html")
def login_page():
    return send_from_directory(".", "login.html")

@app.route("/employee.html")
def employee_page():
    return send_from_directory(".", "employee.html")

@app.route("/manager-portal.html")
def portal_page():
    return send_from_directory(".", "manager-portal.html")

@app.route("/employee-skills.html")
def employee_skills_page():
    return send_from_directory(".", "employee-skills.html")

@app.route("/employee-dashboard.html")
def employee_dashboard():
    return send_from_directory(".", "employee-dashboard.html")

@app.route("/access-denied.html")
def access_denied_page():
    return send_from_directory(".", "access-denied.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(".", path)

@app.route("/projects-list.html")
def projects_list_page():
    return send_from_directory(".", "projects-list.html")

# ============================================================
# Init DB
# ============================================================
if __name__ == "__main__":
    with app.app_context():
        init_db()
        insert_dummy_data()
    app.run(debug=True)