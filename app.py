from flask import Flask, request, jsonify, g, send_from_directory
from schema import init_db, get_db, insert_dummy_data
import sqlite3
import PyPDF2
import io
import os
from ai_helper import get_ai_team_recommendations

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "employees.db")


# -----------------------------
# App context
# -----------------------------
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


# -----------------------------
# Departments
# -----------------------------
@app.route("/departments", methods=["GET"])
def get_departments():
    db = get_db()
    departments = db.execute("SELECT * FROM Departments ORDER BY departmentname").fetchall()
    return jsonify([dict(d) for d in departments])


# -----------------------------
# Employees (List + Detail)
# -----------------------------
@app.route("/employees", methods=["GET"])
def get_employees():
    db = get_db()
    rows = db.execute("""
        SELECT e.empID AS id,
               e.firstname || ' ' || e.lastname AS fullName,
               e.firstname, e.lastname, e.title,
               e.department, d.departmentname,
               e.email, e.phone, e.photo
        FROM Employees e
        LEFT JOIN Departments d ON e.department = d.depID
        ORDER BY e.empID
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/employees/<int:emp_id>", methods=["GET"])
def get_employee(emp_id):
    db = get_db()
    emp = db.execute("""
        SELECT e.empID AS empID,
               e.firstname,
               e.lastname,
               e.title,
               e.department,
               d.departmentname,
               e.email,
               e.phone,
               e.photo
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

    # Validate required fields
    if not data:
        return jsonify({"error": "Missing employee data"}), 400

    db.execute("""
        UPDATE Employees
        SET firstname = ?, lastname = ?, title = ?, department = ?, email = ?, phone = ?, photo = ?
        WHERE empID = ?
    """, (
        data.get("firstname", ""),
        data.get("lastname", ""),
        data.get("title", ""),
        data.get("department", None),
        data.get("email", ""),
        data.get("phone", ""),
        data.get("photo", ""),
        emp_id
    ))

    db.commit()
    return jsonify({"message": "Employee updated successfully."})

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
        data.get("firstname", ""),
        data.get("lastname", ""),
        data.get("title", ""),
        data.get("department", None),
        data.get("email", ""),
        data.get("phone", ""),
        data.get("photo", "")
    ))

    db.commit()

    new_id = cursor.lastrowid
    return jsonify({"message": "Employee added successfully.", "id": new_id}), 201

#employee CSV Import
import csv
from io import TextIOWrapper

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
            row.get("firstname", ""),
            row.get("lastname", ""),
            row.get("title", ""),
            row.get("department", None),
            row.get("email", ""),
            row.get("phone", ""),
            row.get("photo", "")
        ))
        count += 1

    db.commit()
    return jsonify({"message": f"Imported {count} employees."}), 201


# -----------------------------
# Employee Skills
# -----------------------------
@app.route("/employees/<int:emp_id>/skills", methods=["GET"])
def get_employee_skills(emp_id):
    db = get_db()
    skills = db.execute("""
        SELECT s.skillID, s.skillName, sc.skillCategoryname,
               es.profiencylevel, es.evidence
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

# -----------------------------
# Delete Employee 
@app.route("/employees/<int:emp_id>", methods=["DELETE"])
def delete_employee(emp_id):
    db = get_db()
    emp = db.execute("SELECT * FROM Employees WHERE empID = ?", (emp_id,)).fetchone()
    if not emp:
        return jsonify({"error": "Employee not found"}), 404

    db.execute("DELETE FROM Employees WHERE empID = ?", (emp_id,))
    db.commit()
    return jsonify({"message": "Employee deleted successfully"}), 200

# -----------------------------
# Skills (with live search)
# -----------------------------
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


# -----------------------------
# Employee Projects
# -----------------------------
@app.route("/employees/<int:emp_id>/projects", methods=["GET"])
def get_employee_projects(emp_id):
    db = get_db()
    rows = db.execute("""
        SELECT p.projectID, p.projectName, p.status,
               p.startDate, p.endDate, pa.role
        FROM ProjectAssignment pa
        JOIN Projects p ON pa.projectID = p.projectID
        WHERE pa.empID = ?
        ORDER BY p.startDate DESC
    """, (emp_id,)).fetchall()

    return jsonify([dict(r) for r in rows])


# -----------------------------
# AI-based Project Recommendation (already working)
# -----------------------------
@app.route("/api/projects/generate-teams", methods=["POST"])
def generate_team_recommendations():
    data = request.json
    skills_needed = data.get('skills', [])
    team_size = data.get('teamSize', 4)

    if not skills_needed:
        return jsonify({"error": "No skills provided"}), 400

    result = get_ai_team_recommendations(skills_needed, k=team_size)
    return jsonify({
        "recommendations": result['recommended_team'],
        "top5_skills": result['top5_skills'],
        "ai_provider": result['ai_provider'],
        "success": True
    })

@app.route("/api/parse-resume", methods=["POST"])
def parse_resume():
    """
    Parse resume and extract skills using AI.
    """
    if 'resume' not in request.files:
        return jsonify({"error": "No file uploaded", "success": False}), 400
    
    file = request.files['resume']
    
    try:
        # Read file content
        if file.filename.endswith('.pdf'):
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        elif file.filename.endswith('.txt'):
            text = file.read().decode('utf-8')
        else:
            return jsonify({"error": "Unsupported file type. Use PDF or TXT", "success": False}), 400
        
        # Use AI to extract skills
        from ai_helper import call_openai, call_anthropic, call_gemini
        import json
        
        prompt = f"""Analyze this resume and extract all technical skills.

Resume text:
{text[:3000]}

Return ONLY valid JSON in this format:
{{
  "skills": ["Python", "JavaScript", "React", "SQL", "AWS"]
}}

Rules:
- Extract 5-20 technical skills
- Only include real skills (programming languages, frameworks, tools, technologies)
- Return ONLY the JSON, no other text
"""
        
        # Call AI
        if os.getenv("OPENAI_API_KEY"):
            result = call_openai(prompt)
        elif os.getenv("ANTHROPIC_API_KEY"):
            result = call_anthropic(prompt)
        elif os.getenv("GOOGLE_API_KEY"):
            result = call_gemini(prompt)
        else:
            return jsonify({"error": "No AI API key configured", "success": False}), 500
        
        # Parse response
        result = result.strip()
        if result.startswith("```"):
            lines = result.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            result = "\n".join(lines)
        
        data = json.loads(result)
        
        return jsonify({
            "success": True,
            "skills": data.get("skills", [])
        })
        
    except Exception as e:
        print(f"Error parsing resume: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "success": False}), 500


@app.route("/api/employees/<int:emp_id>/skills", methods=["POST"])
def add_employee_skill(emp_id):
    """
    Add a single skill to an employee.
    """
    data = request.json
    db = get_db()
    
    try:
        skill_name = data.get('skillName')
        proficiency = data.get('proficiencyLevel', 5)
        
        # Find or create skill
        skill = db.execute("SELECT skillID FROM Skills WHERE skillName = ?", (skill_name,)).fetchone()
        
        if not skill:
            # Create new skill
            cursor = db.execute("INSERT INTO Skills (skillName, categoryID) VALUES (?, 1)", (skill_name,))
            skill_id = cursor.lastrowid
        else:
            skill_id = skill['skillID']
        
        # Check if employee already has this skill
        existing = db.execute("""
            SELECT * FROM EmployeeSkills WHERE empID = ? AND skillID = ?
        """, (emp_id, skill_id)).fetchone()
        
        if existing:
            # Update proficiency
            db.execute("""
                UPDATE EmployeeSkills 
                SET profiencylevel = ?
                WHERE empID = ? AND skillID = ?
            """, (proficiency, emp_id, skill_id))
        else:
            # Add new skill
            db.execute("""
                INSERT INTO EmployeeSkills (empID, skillID, profiencylevel)
                VALUES (?, ?, ?)
            """, (emp_id, skill_id, proficiency))
        
        db.commit()
        
        return jsonify({
            "success": True,
            "message": f"Skill '{skill_name}' added successfully"
        }), 201
        
    except Exception as e:
        db.rollback()
        print(f"Error adding skill: {e}")
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

@app.route("/access-denied.html")
def access_denied_page():
    return send_from_directory(".", "access-denied.html")

# -----------------------------
# Static Files
# -----------------------------
@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(".", path)


# -----------------------------
# Initialize DB + Run
# -----------------------------
if __name__ == "__main__":
    with app.app_context():
        init_db()
        insert_dummy_data()
    app.run(debug=True)
