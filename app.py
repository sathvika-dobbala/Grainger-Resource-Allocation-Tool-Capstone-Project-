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
@app.route("/api/employees/search", methods=["GET"])
def search_employees():
    """
    Search employees by FIRST name (prefix match, case-insensitive).
    Examples:
      q = 's'   -> Sarah, Sam, Sophia...
      q = 'su'  -> Susan, Summer...
      q = 'li'  -> Liam, Lily...
    Results are department-scoped to the logged-in manager and include projectCount.
    """
    if "manager_id" not in session or "department_id" not in session:
        return jsonify({"employees": [], "error": "Not logged in"}), 401

    q = (request.args.get("q") or "").strip().lower()
    if not q:
        return jsonify({"employees": []})

    db = get_db()
    dept_id = session["department_id"]

    # Pull employees in this manager's department, with count of assigned projects
    rows = db.execute(
        """
        SELECT
            e.empID AS id,
            e.firstname,
            e.lastname,
            e.title,
            COALESCE(COUNT(p.projectID), 0) AS projectCount
        FROM Employees e
        LEFT JOIN ProjectAssignment pa ON pa.empID = e.empID
        LEFT JOIN Projects p ON p.projectID = pa.projectID
        WHERE e.department = ?
        GROUP BY e.empID, e.firstname, e.lastname, e.title
        """,
        (dept_id,),
    ).fetchall()

    employees = []
    for r in rows:
        first = (r["firstname"] or "").strip().lower()
        full_name = f"{r['firstname'] or ''} {r['lastname'] or ''}".strip()
        project_count = int(r["projectCount"] or 0)

        # ✅ Prefix match on first name for ANY length of q
        if first.startswith(q):
            employees.append(
                {
                    "id": r["id"],
                    "name": full_name,
                    "title": r["title"] or "",
                    "skills": [],            # can be filled later if needed
                    "projectCount": project_count,
                }
            )

    return jsonify({"employees": employees})

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


@app.route("/employees/<int:emp_id>/upload-resume", methods=["POST"])
def upload_employee_resume(emp_id):
    """Upload resume and extract skills using AI with proficiency assessment."""
    try:
        if "manager_id" not in session:
            return jsonify({"success": False, "error": "Not logged in"}), 401

        if "resume" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file = request.files["resume"]
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"success": False, "error": "Only PDF files are supported"}), 400

        # Extract text from PDF
        from pypdf import PdfReader
        reader = PdfReader(file.stream)
        text_parts = []
        for i, page in enumerate(reader.pages[:10]):  # Max 10 pages
            try:
                text_parts.append(page.extract_text() or "")
            except Exception:
                pass
        
        resume_text = "\n\n".join(text_parts).strip()
        if not resume_text:
            return jsonify({"success": False, "error": "Could not extract text from PDF"}), 400

        # Get department-specific skills for this employee
        db = get_db()
        emp = db.execute("SELECT department FROM Employees WHERE empID = ?", (emp_id,)).fetchone()
        if not emp:
            return jsonify({"success": False, "error": "Employee not found"}), 404

        dept_id = emp["department"]
        
        # Use existing AI helper to extract skills
        from ai_helper import extract_skills_from_text, assess_skill_proficiency
        extracted_skills = extract_skills_from_text(resume_text, db, dept_id)

        # Get additional skill details with AI-assessed proficiency
        skills_with_details = []
        for skill in extracted_skills:
            skill_row = db.execute("""
                SELECT s.skillID, s.skillName, sc.skillCategoryname
                FROM Skills s
                LEFT JOIN SkillCategories sc ON s.skillCategoryID = sc.skillCategoryID
                WHERE s.skillID = ?
            """, (skill["skillID"],)).fetchone()
            
            if skill_row:
                # 🟢 NEW: Use AI to assess proficiency level (0-10 scale)
                proficiency_level = assess_skill_proficiency(
                    resume_text, 
                    skill_row["skillName"],
                    skill.get("reason", "")
                )
                
                skills_with_details.append({
                    "skillID": skill_row["skillID"],
                    "skillName": skill_row["skillName"],
                    "categoryName": skill_row["skillCategoryname"],
                    "level": proficiency_level,  # AI-assessed level
                    "evidence": skill.get("reason", "Extracted from resume")
                })

        return jsonify({
            "success": True,
            "skills": skills_with_details,
            "message": f"Extracted {len(skills_with_details)} skills from resume with AI-assessed proficiency levels"
        })

    except Exception as e:
        print(f"Resume upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

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
        skills_needed = data.get("skills", [])
        team_size = int(data.get("teamSize", 4))
        priority = data.get("priority", "Critical")  # 🔹 NEW
        department_id = session["department_id"]

        if not skills_needed:
            return jsonify({"error": "No skills provided"}), 400

        result = get_ai_team_recommendations(
            skills_needed,
            department_id=department_id,
            k=team_size,
            priority=priority,        # 🔹 NEW
        )
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
        priority = data.get("priority", "Medium")  # <-- NOW WORKING
        start_date = data.get("startDate")
        end_date = data.get("endDate")
        skills = data.get("skills", [])
        team_members = data.get("teamMembers", [])
        
        if not project_name:
            return jsonify({"success": False, "error": "Project name is required"}), 400
        
        if not team_members:
            return jsonify({"success": False, "error": "At least one team member is required"}), 400
        
        db = get_db()
        
        # Get first member’s teamID
        first_member = db.execute("""
            SELECT teamID FROM Employees WHERE empID = ?
        """, (team_members[0],)).fetchone()
        
        if not first_member or not first_member["teamID"]:
            team_id = 1
        else:
            team_id = first_member["teamID"]
        
        # Ensure unique project name
        existing = db.execute("""
            SELECT projectID FROM Projects WHERE projectName = ?
        """, (project_name,)).fetchone()
        
        if existing:
            return jsonify({"success": False, "error": "Project name already exists"}), 400
        
        # ⭐⭐⭐ FIXED: Now includes managerNotes + correct INSERT columns ⭐⭐⭐
        cursor = db.execute("""
            INSERT INTO Projects (teamID, projectName, status, priority, startDate, endDate)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            team_id,
            project_name,
            status,
            priority,
            start_date,
            end_date
        ))
        
        project_id = cursor.lastrowid
        
        # Insert team members
        for i, emp_id in enumerate(team_members):
            role = "Lead" if i == 0 else "Contributor"
            db.execute("""
                INSERT INTO ProjectAssignment (projectID, empID, role)
                VALUES (?, ?, ?)
            """, (project_id, emp_id, role))
        
        db.commit()
        
        return jsonify({
            "success": True,
            "projectId": project_id,
            "redirectUrl": f"/project-detail.html?projectID={project_id}",
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
# Project Details + Members CRUD
# ============================================================
@app.route("/api/projects/<int:project_id>", methods=["GET"])
def get_project_detail(project_id):
    db = get_db()
    project = db.execute("""
        SELECT
            p.projectID,
            p.projectName,
            p.status,
            p.priority,        
            p.startDate,
            p.endDate,
            t.teamID,
            t.department
        FROM Projects p
        JOIN Teams t ON p.teamID = t.teamID
        WHERE p.projectID = ?
    """, (project_id,)).fetchone()

    if not project:
        return jsonify({"success": False, "error": "Project not found"}), 404

    members = db.execute("""
        SELECT e.empID, e.firstname || ' ' || e.lastname AS fullName, pa.role
        FROM ProjectAssignment pa
        JOIN Employees e ON e.empID = pa.empID
        WHERE pa.projectID = ?
        ORDER BY pa.role = 'Lead' DESC, e.lastname
    """, (project_id,)).fetchall()

    return jsonify({"success": True, "project": dict(project), "members": [dict(m) for m in members]})


@app.route("/api/projects/<int:project_id>/members", methods=["GET"])
def get_project_members(project_id):
    db = get_db()
    members = db.execute("""
        SELECT e.empID, e.firstname || ' ' || e.lastname AS fullName, pa.role
        FROM ProjectAssignment pa
        JOIN Employees e ON e.empID = pa.empID
        WHERE pa.projectID = ?
        ORDER BY pa.role = 'Lead' DESC, e.lastname
    """, (project_id,)).fetchall()
    return jsonify({"success": True, "members": [dict(m) for m in members]})


@app.route("/api/projects/<int:project_id>/members", methods=["POST"])
def add_project_member(project_id):
    data = request.get_json()
    emp_id = data.get("empID")
    role = data.get("role", "Contributor")

    if not emp_id:
        return jsonify({"success": False, "error": "Missing empID"}), 400

    db = get_db()

    # Ensure employee exists
    employee = db.execute(
        "SELECT empID FROM Employees WHERE empID = ?", (emp_id,)
    ).fetchone()

    if not employee:
        return jsonify({"success": False, "error": "Employee not found"}), 404

    try:
        db.execute("""
            INSERT INTO ProjectAssignment (projectID, empID, role)
            VALUES (?, ?, ?)
        """, (project_id, emp_id, role))

        db.commit()
        return jsonify({"success": True, "message": "Member added successfully"})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Employee already assigned"}), 400



@app.route("/api/projects/<int:project_id>/members/<int:emp_id>", methods=["PUT"])
def update_project_member(project_id, emp_id):
    data = request.get_json()
    new_role = data.get("role")

    if not new_role:
        return jsonify({"success": False, "error": "Missing new role"}), 400

    db = get_db()
    db.execute("""
        UPDATE ProjectAssignment
        SET role = ?
        WHERE projectID = ? AND empID = ?
    """, (new_role, project_id, emp_id))
    db.commit()

    return jsonify({"success": True, "message": "Member role updated"})


@app.route("/api/projects/<int:project_id>/members/<int:emp_id>", methods=["DELETE"])
def delete_project_member(project_id, emp_id):
    db = get_db()
    db.execute("""
        DELETE FROM ProjectAssignment
        WHERE projectID = ? AND empID = ?
    """, (project_id, emp_id))
    db.commit()
    return jsonify({"success": True, "message": "Member removed successfully"})


# ============================================================
# FIX: Allow PUT and DELETE using either empID or full name
# ============================================================
@app.route("/api/projects/<int:project_id>/members/<value>", methods=["PUT"])
def update_project_member_by_value(project_id, value):
    data = request.get_json()
    new_role = data.get("role")

    if not new_role:
        return jsonify({"success": False, "error": "Missing new role"}), 400

    db = get_db()

    # Determine if value is empID or name
    if value.isdigit():
        emp_id = int(value)
    else:
        emp = db.execute("""
            SELECT empID FROM Employees
            WHERE firstname || ' ' || lastname LIKE ?
        """, (value + "%",)).fetchone()

        if not emp:
            return jsonify({"success": False, "error": "Employee not found"}), 404

        emp_id = emp["empID"]

    db.execute("""
        UPDATE ProjectAssignment
        SET role = ?
        WHERE projectID = ? AND empID = ?
    """, (new_role, project_id, emp_id))
    db.commit()

    return jsonify({"success": True, "message": "Member updated"})


@app.route("/api/projects/<int:project_id>/members/<value>", methods=["DELETE"])
def delete_project_member_by_value(project_id, value):
    db = get_db()

    # Determine if value is empID or name
    if value.isdigit():
        emp_id = int(value)
    else:
        emp = db.execute("""
            SELECT empID FROM Employees
            WHERE firstname || ' ' || lastname LIKE ?
        """, (value + "%",)).fetchone()

        if not emp:
            return jsonify({"success": False, "error": "Employee not found"}), 404

        emp_id = emp["empID"]

    db.execute("""
        DELETE FROM ProjectAssignment
        WHERE projectID = ? AND empID = ?
    """, (project_id, emp_id))
    db.commit()

    return jsonify({"success": True, "message": "Member removed"})



# Add Project UPDATE Route (PUT)
@app.route("/api/projects/<int:project_id>", methods=["PUT"])
def update_project(project_id):
    data = request.get_json()
    db = get_db()

    db.execute("""
        UPDATE Projects
        SET status = ?, startDate = ?, endDate = ?
        WHERE projectID = ?
    """, (
        data.get("status"),
        data.get("startDate"),
        data.get("endDate"),
        project_id
    ))

    db.commit()

    return jsonify({"success": True, "message": "Project updated"})


# Add Project DELETE Route
@app.route("/api/projects/<int:project_id>", methods=["DELETE"])
def delete_project(project_id):
    db = get_db()
    db.execute("DELETE FROM Projects WHERE projectID = ?", (project_id,))
    db.commit()
    return jsonify({"success": True, "message": "Project deleted"})


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
# Project Skills (GET only for now)
# ============================================================
@app.route("/api/projects/<int:project_id>/skills", methods=["GET"])
def get_project_skills(project_id):
    db = get_db()
    rows = db.execute("""
        SELECT s.skillID, s.skillName
        FROM ProjectSkills ps
        JOIN Skills s ON ps.skillID = s.skillID
        WHERE ps.projectID = ?
    """, (project_id,)).fetchall()

    return jsonify({"skills": [dict(r) for r in rows]})

# ================================================
#   SKILL CATEGORY LIST
# ================================================
@app.route("/api/skill-categories", methods=["GET"])
def get_skill_categories():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT skillCategoryID, skillCategoryName
        FROM SkillCategories
        ORDER BY skillCategoryName ASC
    """)

    rows = cur.fetchall()

    categories = [
        {
            "skillCategoryID": r[0],
            "skillCategoryName": r[1]
        }
        for r in rows
    ]

    return jsonify({"categories": categories})



# ================================================
#   MANAGER SKILL BANK CRUD (UPDATED + FIXED)
# ================================================

from flask import jsonify, request

# GET all skills for one manager

@app.route("/api/manager/<int:managerID>/skills", methods=["GET"])
def get_manager_skills(managerID):
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT 
            s.skillID,
            s.skillName,
            s.skillCategoryID,
            c.skillCategoryName
        FROM Skills s
        LEFT JOIN SkillCategories c 
            ON s.skillCategoryID = c.skillCategoryID
        JOIN ManagerSkills ms 
            ON s.skillID = ms.skillID
        WHERE ms.managerID = ?
        ORDER BY c.skillCategoryName, s.skillName;
    """, (managerID,))

    rows = cur.fetchall()

    skills = [
        {
            "skillID": r[0],
            "skillName": r[1],
            "skillCategoryID": r[2],
            "skillCategoryName": r[3]
        }
        for r in rows
    ]

    return jsonify({"success": True, "skills": skills})



# ADD a new skill for a manager

@app.route("/api/manager/<int:managerID>/skills", methods=["POST"])
def add_manager_skill(managerID):
    data = request.get_json()
    skill_name = data.get("skillName").strip()
    category_id = data.get("skillCategoryID")

    db = get_db()
    cur = db.cursor()

    # Check for case-insensitive duplicates
    cur.execute("""
        SELECT skillID FROM Skills
        WHERE LOWER(skillName) = LOWER(?)
    """, (skill_name,))
    duplicate = cur.fetchone()

    if duplicate:
        return jsonify({"error": "This skill already exists (case-insensitive)."}), 400

    # Insert skill
    cur.execute("""
        INSERT INTO Skills (skillName, skillCategoryID) VALUES (?, ?)
    """, (skill_name, category_id))

    skill_id = cur.lastrowid

    # Link to manager
    cur.execute("""
        INSERT INTO ManagerSkills (managerID, skillID) VALUES (?, ?)
    """, (managerID, skill_id))

    db.commit()
    return jsonify({"message": "Skill added", "skillID": skill_id})




# UPDATE a manager-owned skill

@app.route("/api/manager/<int:managerID>/skills/<int:skillID>", methods=["PUT"])
def update_manager_skill(managerID, skillID):
    data = request.get_json()
    new_name = data.get("skillName").strip()
    new_category = data.get("skillCategoryID")

    db = get_db()
    cur = db.cursor()

    # Check for case-insensitive duplicates (EXCLUDING itself)
    cur.execute("""
        SELECT skillID FROM Skills
        WHERE LOWER(skillName) = LOWER(?) AND skillID != ?
    """, (new_name, skillID))

    duplicate = cur.fetchone()
    if duplicate:
        return jsonify({"error": "A skill with this name already exists (case-insensitive)."}), 400

    # Apply update
    cur.execute("""
        UPDATE Skills 
        SET skillName = ?, skillCategoryID = ?
        WHERE skillID = ?
    """, (new_name, new_category, skillID))

    db.commit()
    return jsonify({"message": "Skill updated"})





# DELETE a manager-owned skill

@app.route("/api/manager/<int:managerID>/skills/<int:skillID>", methods=["DELETE"])
def delete_manager_skill(managerID, skillID):
    db = get_db()
    cur = db.cursor()

    # Remove from ManagerSkills table FIRST
    cur.execute("""
        DELETE FROM ManagerSkills 
        WHERE managerID = ? AND skillID = ?
    """, (managerID, skillID))

    # Remove the skill itself
    cur.execute("DELETE FROM Skills WHERE skillID = ?", (skillID,))

    db.commit()

    return jsonify({"success": True, "message": "Skill deleted"})



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

@app.route("/projects")
def projects_no_extension():
    return send_from_directory(".", "projects.html")

@app.route("/projects-list.html")
def projects_list_page():
    return send_from_directory(".", "projects-list.html")

@app.route("/project-detail.html")
def project_detail_page():
    return send_from_directory(".", "project-detail.html")

@app.route("/skills.html")
def skills_page():
    return send_from_directory(".", "skills.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(".", path)
# ============================================================
# Init DB
# ============================================================
if __name__ == "__main__":
    with app.app_context():
        init_db()
        insert_dummy_data()
    app.run(debug=True)