from flask import Flask, request, jsonify, g, send_from_directory
from schema import init_db, get_db, insert_dummy_data
import sqlite3
import os

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
        SELECT e.empID as id, 
               e.firstname || ' ' || e.lastname as fullName,
               e.firstname, e.lastname, e.title, 
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

# ✅ Improved Add Employee Route (handles validation + better logging)
@app.route("/employees", methods=["POST"])
def add_employee():
    data = request.json
    print("📥 Received new employee data:", data)

    try:
        # Validate required fields
        if not data.get("firstname") or not data.get("lastname"):
            return jsonify({"error": "Missing firstname or lastname"}), 400

        department_value = data.get("department")
        if isinstance(department_value, str) and not department_value.isdigit():
            department_value = None  # avoid invalid text if dropdown not selected

        with get_db() as db:
            cur = db.execute("""
                INSERT INTO Employees (firstname, lastname, title, department, email, phone, photo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("firstname"),
                data.get("lastname"),
                data.get("title"),
                department_value,
                data.get("email"),
                data.get("phone"),
                data.get("photo")
            ))
            db.commit()
            new_id = cur.lastrowid

        print(f"✅ Employee added successfully (ID: {new_id})")
        return jsonify({"empID": new_id, "status": "success"}), 201

    except Exception as e:
        print("❌ Error saving employee:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/employees/<int:id>", methods=["PUT"])
def update_employee(id):
    data = request.json
    print(f"✏️ Updating employee {id}:", data)
    
    try:
        with get_db() as db:
            db.execute("""
                UPDATE Employees
                SET firstname=?, lastname=?, title=?, department=?, email=?, phone=?, photo=?
                WHERE empID=?
            """, (
                data.get("firstname"),
                data.get("lastname"),
                data.get("title"),
                data.get("department"),
                data.get("email"),
                data.get("phone"),
                data.get("photo"),
                id
            ))
            db.commit()
        print(f"✅ Employee {id} updated successfully")
        return jsonify({"status": "updated"})
    except Exception as e:
        print("❌ Error updating employee:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/employees/<int:id>", methods=["DELETE"])
def delete_employee(id):
    print(f"🗑️ Deleting employee {id}")
    try:
        with get_db() as db:
            db.execute("DELETE FROM Employees WHERE empID=?", (id,))
            db.commit()
        print(f"✅ Employee {id} deleted")
        return jsonify({"status": "deleted"})
    except Exception as e:
        print("❌ Error deleting employee:", str(e))
        return jsonify({"error": str(e)}), 500

# -----------------------------
# API Routes - Employee Skills
# -----------------------------
@app.route("/employees/<int:emp_id>/skills", methods=["GET"])
def get_employee_skills(emp_id):
    db = get_db()
    
    employee = db.execute("SELECT * FROM Employees WHERE empID = ?", (emp_id,)).fetchone()
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    
    skills = db.execute("""
        SELECT s.skillID, s.skillName, es.profiencylevel, es.evidence, sc.skillCategoryname
        FROM EmployeeSkills es
        JOIN Skills s ON es.skillID = s.skillID
        LEFT JOIN SkillCategories sc ON s.skillCategoryID = sc.skillCategoryID
        WHERE es.empID = ?
        ORDER BY s.skillName
    """, (emp_id,)).fetchall()
    
    return jsonify({
        "employee": dict(employee),
        "skills": [dict(skill) for skill in skills]
    })

@app.route("/employees/<int:emp_id>/skills", methods=["POST"])
def add_employee_skill(emp_id):
    data = request.json
    db = get_db()
    
    skill_name = data.get("skillName")
    proficiency = data.get("profiencylevel")
    evidence = data.get("evidence", "")
    
    skill = db.execute("SELECT skillID FROM Skills WHERE skillName = ?", (skill_name,)).fetchone()
    if not skill:
        cursor = db.execute("INSERT INTO Skills (skillName) VALUES (?)", (skill_name,))
        db.commit()
        skill_id = cursor.lastrowid
    else:
        skill_id = skill["skillID"]
    
    try:
        db.execute("""
            INSERT INTO EmployeeSkills (empID, skillID, profiencylevel, evidence)
            VALUES (?, ?, ?, ?)
        """, (emp_id, skill_id, proficiency, evidence))
        db.commit()
        return jsonify({"status": "success", "skillID": skill_id}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Skill already exists for this employee"}), 400

@app.route("/employees/<int:emp_id>/skills", methods=["PUT"])
def bulk_update_employee_skills(emp_id):
    data = request.json
    skills = data.get("skills", [])
    db = get_db()
    
    try:
        db.execute("DELETE FROM EmployeeSkills WHERE empID = ?", (emp_id,))
        for skill in skills:
            db.execute("""
                INSERT INTO EmployeeSkills (empID, skillID, profiencylevel, evidence)
                VALUES (?, ?, ?, ?)
            """, (emp_id, skill.get("skillID"), skill.get("profiencylevel"), skill.get("evidence", "")))
        db.commit()
        return jsonify({"status": "success", "message": "Skills updated successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/employees/<int:emp_id>/skills/<int:skill_id>", methods=["PUT"])
def update_employee_skill(emp_id, skill_id):
    data = request.json
    db = get_db()
    
    db.execute("""
        UPDATE EmployeeSkills
        SET profiencylevel = ?, evidence = ?
        WHERE empID = ? AND skillID = ?
    """, (data.get("profiencylevel"), data.get("evidence", ""), emp_id, skill_id))
    db.commit()
    return jsonify({"status": "updated"})

@app.route("/employees/<int:emp_id>/skills/<int:skill_id>", methods=["DELETE"])
def delete_employee_skill(emp_id, skill_id):
    db = get_db()
    db.execute("DELETE FROM EmployeeSkills WHERE empID = ? AND skillID = ?", (emp_id, skill_id))
    db.commit()
    return jsonify({"status": "deleted"})

# -----------------------------
# API Routes - Skills
# -----------------------------
@app.route("/skills", methods=["GET"])
def get_all_skills():
    db = get_db()
    skills = db.execute("""
        SELECT s.skillID, s.skillName, sc.skillCategoryname
        FROM Skills s
        LEFT JOIN SkillCategories sc ON s.skillCategoryID = sc.skillCategoryID
        ORDER BY s.skillName
    """).fetchall()
    return jsonify([dict(skill) for skill in skills])

@app.route("/skills", methods=["POST"])
def add_skill():
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
# API Routes - Skill Categories
# -----------------------------
@app.route("/skill-categories", methods=["GET"])
def get_skill_categories():
    db = get_db()
    categories = db.execute("""
        SELECT skillCategoryID, skillCategoryname
        FROM SkillCategories
        ORDER BY skillCategoryname
    """).fetchall()
    
    return jsonify([dict(cat) for cat in categories])

@app.route("/skill-categories", methods=["POST"])
def add_skill_category():
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
# API Routes - Employee Projects
# -----------------------------
@app.route("/employees/<int:emp_id>/projects", methods=["GET"])
def get_employee_projects(emp_id):
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
    db = get_db()
    
    skill_count = db.execute("SELECT COUNT(*) as count FROM EmployeeSkills WHERE empID = ?", (emp_id,)).fetchone()['count']
    active_projects = db.execute("""
        SELECT COUNT(*) as count 
        FROM ProjectAssignment pa
        JOIN Projects p ON pa.projectID = p.projectID
        WHERE pa.empID = ? AND p.status = 'In Progress'
    """, (emp_id,)).fetchone()['count']
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

# API Routes - Projects & Team Recommendations  
# -----------------------------
from ai_helper import get_ai_team_recommendations

@app.route("/api/projects/generate-teams", methods=["POST"])
def generate_team_recommendations():
    """
    Generate AI-powered team recommendations based on skills needed.
    Expects JSON: { "skills": ["Python", "React", ...], "teamSize": 4 }
    """
    data = request.json
    skills_needed = data.get('skills', [])
    team_size = data.get('teamSize', 4)
    
    if not skills_needed:
        return jsonify({"error": "No skills provided"}), 400
    
    try:
        print(f"🔍 Generating recommendations for skills: {skills_needed}")
        result = get_ai_team_recommendations(skills_needed, k=team_size)
        
        return jsonify({
            "recommendations": result['recommended_team'],
            "top5_skills": result['top5_skills'],
            "ai_provider": result['ai_provider'],
            "success": True
        })
    except Exception as e:
        print(f"❌ Error generating recommendations: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "success": False}), 500

@app.route("/api/projects", methods=["POST"])
def create_project():
    """
    Create a new project with assigned team members.
    Creates a new team in the Teams table specifically for this project.
    """
    data = request.json
    db = get_db()
    
    try:
        team_members = data.get('teamMembers', [])
        
        if not team_members:
            return jsonify({"error": "At least one team member is required", "success": False}), 400
        
        project_name = data.get('projectName')
        
        # Create a new team for this project
        team_name = f"{project_name} Team"
        cursor = db.execute("""
            INSERT INTO Teams (teamName, department)
            VALUES (?, 1)
        """, (team_name,))
        team_id = cursor.lastrowid
        
        # Create the project with the new team
        cursor = db.execute("""
            INSERT INTO Projects (teamID, projectName, status, startDate, endDate)
            VALUES (?, ?, ?, ?, ?)
        """, (
            team_id,
            project_name,
            data.get('status', 'Not Started'),
            data.get('startDate'),
            data.get('endDate')
        ))
        project_id = cursor.lastrowid
        
        # Add project skills
        for skill_name in data.get('skills', []):
            skill = db.execute("SELECT skillID FROM Skills WHERE skillName = ?", (skill_name,)).fetchone()
            if skill:
                db.execute("""
                    INSERT INTO ProjectSkills (projectID, skillID, numpeopleneeded, complexitylevel)
                    VALUES (?, ?, ?, ?)
                """, (project_id, skill['skillID'], 1, 'Medium'))
        
        # Assign team members to the project
        for idx, emp_id in enumerate(team_members):
            role = 'Lead' if idx == 0 else 'Contributor'
            db.execute("""
                INSERT INTO ProjectAssignment (projectID, empID, role)
                VALUES (?, ?, ?)
            """, (project_id, emp_id, role))
        
        db.commit()
        
        return jsonify({
            "success": True,
            "projectId": project_id,
            "teamId": team_id,
            "teamName": team_name,
            "message": f"Project created with new team '{team_name}' ({len(team_members)} members)"
        }), 201
        
    except Exception as e:
        db.rollback()
        print(f"Error creating project: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "success": False}), 500
    
@app.route("/api/employees/search", methods=["GET"])
def search_employees():
    """
    Search employees to manually add to team.
    Query param: ?q=search_term
    """
    search_term = request.args.get('q', '')
    db = get_db()
    
    employees = db.execute("""
        SELECT 
            e.empID as id,
            e.firstname || ' ' || e.lastname as name,
            e.title,
            e.email,
            e.photo,
            d.departmentname as department,
            t.teamName as team
        FROM Employees e
        LEFT JOIN Departments d ON e.department = d.depID
        LEFT JOIN Teams t ON e.teamID = t.teamID
        WHERE e.firstname LIKE ? OR e.lastname LIKE ? OR e.title LIKE ?
        LIMIT 20
    """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%')).fetchall()
    
    results = []
    for emp in employees:
        # Get top skills
        skills = db.execute("""
            SELECT s.skillName
            FROM EmployeeSkills es
            JOIN Skills s ON es.skillID = s.skillID
            WHERE es.empID = ?
            ORDER BY es.profiencylevel DESC
            LIMIT 5
        """, (emp['id'],)).fetchall()
        
        results.append({
            'id': emp['id'],
            'name': emp['name'],
            'title': emp['title'] or 'No title',
            'email': emp['email'],
            'department': emp['department'] or 'No department',
            'team': emp['team'] or 'No team',
            'skills': [s['skillName'] for s in skills],
            'avatar': emp['photo'],
            'matchScore': 0  # Manual additions don't have match scores
        })
    
    return jsonify({"employees": results})


# -----------------------------
# Serve HTML Pages
# -----------------------------
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

# -----------------------------
# Catch-all for Static Files
# -----------------------------
@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(".", path)

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    with app.app_context():
        init_db()
        insert_dummy_data()
    app.run(debug=True)
