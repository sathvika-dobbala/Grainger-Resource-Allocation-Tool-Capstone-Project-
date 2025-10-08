from flask import Flask, request, jsonify, g, send_from_directory
from schema import init_db, get_db, insert_dummy_data
import sqlite3
import os  # ← Make sure this line exists

app = Flask(__name__)

DATABASE = os.path.join(os.path.dirname(__file__), "employees.db")

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# -----------------------------
# API Routes - Departments
# -----------------------------
@app.route("/departments", methods=["GET"])
def get_departments():
    db = get_db()
    departments = db.execute("SELECT * FROM Departments ORDER BY departmentname").fetchall()
    return jsonify([dict(d) for d in departments])

# -----------------------------
# API Routes - Employees
# -----------------------------
@app.route("/employees", methods=["GET"])
def get_employees():
    db = get_db()
    employees = db.execute("""
        SELECT e.empID as id, e.firstname, e.lastname, e.title, 
               e.department, d.departmentname, e.email, e.phone, e.photo
        FROM Employees e
        LEFT JOIN Departments d ON e.department = d.depID
    """).fetchall()
    return jsonify([dict(e) for e in employees])

@app.route("/employees/<int:id>", methods=["GET"])
def get_employee(id):
    db = get_db()
    emp = db.execute("""
    SELECT e.empID as id, e.firstname, e.lastname, 
           e.firstname || ' ' || e.lastname as fullName,
           e.title, e.department, d.departmentname, e.email, e.phone, e.photo
    FROM Employees e
    LEFT JOIN Departments d ON e.department = d.depID
    WHERE e.empID=?
""", (id,)).fetchone()
    if emp:
        return jsonify(dict(emp))
    return jsonify({"error": "Employee not found"}), 404

@app.route("/employees", methods=["POST"])
def add_employee():
    data = request.json
    print("📥 Adding employee:", data)
    
    with get_db() as db:
        cur = db.execute("""
            INSERT INTO Employees (firstname, lastname, title, department, email, phone, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (data.get("firstname"), data.get("lastname"), data.get("title"), 
              data.get("department"), data.get("email"), data.get("phone"), data.get("photo")))
        db.commit()
        new_id = cur.lastrowid
    
    print(f"✅ Employee {new_id} inserted into DB")
    return jsonify({"empID": new_id}), 201

@app.route("/employees/<int:id>", methods=["PUT"])
def update_employee(id):
    data = request.json
    print(f"✏️ Updating employee {id}:", data)
    
    with get_db() as db:
        db.execute("""
            UPDATE Employees
            SET firstname=?, lastname=?, title=?, department=?, email=?, phone=?, photo=?
            WHERE empID=?
        """, (data.get("firstname"), data.get("lastname"), data.get("title"), 
              data.get("department"), data.get("email"), data.get("phone"), 
              data.get("photo"), id))
        db.commit()
    
    return jsonify({"status": "updated"})

@app.route("/employees/<int:id>", methods=["DELETE"])
def delete_employee(id):
    print(f"🗑️ Deleting employee {id}")
    with get_db() as db:
        db.execute("DELETE FROM Employees WHERE empID=?", (id,))
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

# Add these routes to your app.py file

# -----------------------------
# Employee Skills API Routes
# -----------------------------

@app.route("/employees/<int:emp_id>/skills", methods=["GET"])
def get_employee_skills(emp_id):
    """Get all skills for a specific employee with proficiency levels"""
    db = get_db()
    skills = db.execute("""
        SELECT 
            es.empID,
            es.skillID,
            s.skillName,
            sc.skillCategoryname as categoryName,
            es.profiencylevel as proficiencyLevel,
            es.evidence
        FROM EmployeeSkills es
        JOIN Skills s ON es.skillID = s.skillID
        LEFT JOIN SkillCategories sc ON s.skillCategoryID = sc.skillCategoryID
        WHERE es.empID = ?
        ORDER BY s.skillName
    """, (emp_id,)).fetchall()
    
    return jsonify([dict(skill) for skill in skills])


@app.route("/employees/<int:emp_id>/skills", methods=["PUT"])
def update_employee_skills(emp_id):
    """Update all skills for an employee"""
    data = request.json
    skills = data.get('skills', [])
    
    with get_db() as db:
        # Delete existing skills for this employee
        db.execute("DELETE FROM EmployeeSkills WHERE empID = ?", (emp_id,))
        
        # Insert new/updated skills
        for skill in skills:
            db.execute("""
                INSERT INTO EmployeeSkills (empID, skillID, profiencylevel, evidence)
                VALUES (?, ?, ?, ?)
            """, (
                emp_id,
                skill.get('skillID'),
                skill.get('proficiencyLevel', 1),
                skill.get('evidence', '')
            ))
        
        db.commit()
    
    return jsonify({"status": "success", "message": "Skills updated"})


@app.route("/skills", methods=["GET"])
def get_all_skills():
    """Get all available skills in the system"""
    db = get_db()
    skills = db.execute("""
        SELECT 
            s.skillID,
            s.skillName,
            sc.skillCategoryname as categoryName
        FROM Skills s
        LEFT JOIN SkillCategories sc ON s.skillCategoryID = sc.skillCategoryID
        ORDER BY s.skillName
    """).fetchall()
    
    return jsonify([dict(skill) for skill in skills])


@app.route("/skills", methods=["POST"])
def add_skill():
    """Add a new skill to the system"""
    data = request.json
    skill_name = data.get('skillName')
    category_id = data.get('skillCategoryID')
    
    with get_db() as db:
        cur = db.execute("""
            INSERT INTO Skills (skillName, skillCategoryID)
            VALUES (?, ?)
        """, (skill_name, category_id))
        db.commit()
        new_id = cur.lastrowid
    
    return jsonify({"skillID": new_id, "status": "success"}), 201


# -----------------------------
# Employee Projects API Routes
# -----------------------------

@app.route("/employees/<int:emp_id>/projects", methods=["GET"])
def get_employee_projects(emp_id):
    """Get all projects for a specific employee"""
    db = get_db()
    projects = db.execute("""
        SELECT 
            p.projectID,
            p.projectName,
            p.status,
            p.startDate,
            p.endDate,
            pa.role,
            t.teamName
        FROM ProjectAssignment pa
        JOIN Projects p ON pa.projectID = p.projectID
        JOIN Teams t ON p.teamID = t.teamID
        WHERE pa.empID = ?
        ORDER BY p.startDate DESC
    """, (emp_id,)).fetchall()
    
    return jsonify([dict(proj) for proj in projects])


@app.route("/employees/<int:emp_id>/stats", methods=["GET"])
def get_employee_stats(emp_id):
    """Get statistics for an employee"""
    db = get_db()
    
    # Count skills
    skill_count = db.execute("""
        SELECT COUNT(*) as count FROM EmployeeSkills WHERE empID = ?
    """, (emp_id,)).fetchone()['count']
    
    # Count active projects
    active_projects = db.execute("""
        SELECT COUNT(*) as count 
        FROM ProjectAssignment pa
        JOIN Projects p ON pa.projectID = p.projectID
        WHERE pa.empID = ? AND p.status = 'In Progress'
    """, (emp_id,)).fetchone()['count']
    
    # Average proficiency
    avg_proficiency = db.execute("""
        SELECT AVG(profiencylevel) as avg 
        FROM EmployeeSkills 
        WHERE empID = ?
    """, (emp_id,)).fetchone()['avg'] or 0
    
    return jsonify({
        'skillCount': skill_count,
        'activeProjects': active_projects,
        'avgProficiency': round(avg_proficiency, 1)
    })


# -----------------------------
# Skill Categories API Routes
# -----------------------------

@app.route("/skill-categories", methods=["GET"])
def get_skill_categories():
    """Get all skill categories"""
    db = get_db()
    categories = db.execute("""
        SELECT skillCategoryID, skillCategoryname
        FROM SkillCategories
        ORDER BY skillCategoryname
    """).fetchall()
    
    return jsonify([dict(cat) for cat in categories])


@app.route("/skill-categories", methods=["POST"])
def add_skill_category():
    """Add a new skill category"""
    data = request.json
    category_name = data.get('skillCategoryname')
    
    with get_db() as db:
        cur = db.execute("""
            INSERT INTO SkillCategories (skillCategoryname)
            VALUES (?)
        """, (category_name,))
        db.commit()
        new_id = cur.lastrowid
    
    return jsonify({"skillCategoryID": new_id, "status": "success"}), 201


# -----------------------------
# Route to serve the dashboard page
# -----------------------------

@app.route("/employee-dashboard.html")
def employee_dashboard():
    return send_from_directory(".", "employee-dashboard.html")

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)