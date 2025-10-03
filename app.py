from flask import Flask, render_template, request, redirect, url_for
from schema import get_db, init_db, insert_dummy_data  # import db helpers

app = Flask(__name__)

# Initialize DB + dummy data at startup
with app.app_context():
    init_db()
    insert_dummy_data()


# ---------------------------
# Home – Employee Directory
# ---------------------------
@app.route("/")
def home():
    db = get_db()
    employees = db.execute("SELECT empID, firstname, lastname FROM Employees").fetchall()
    return render_template("index.html", employees=employees)


# ---------------------------
# Employee Skills (CRUD)
# ---------------------------
@app.route("/employee/<int:emp_id>", methods=["GET", "POST"])
def employee_skills(emp_id):
    db = get_db()

    if request.method == "POST":
        # Form values
        skill_name = request.form["skillName"].strip()
        level = request.form["profiencylevel"].strip()
        evidence = request.form["evidence"].strip()

        # Ensure level is int
        try:
            level = int(level)
        except ValueError:
            level = 0

        # Check if skill already exists
        skill = db.execute("SELECT skillID FROM Skills WHERE skillName = ?", (skill_name,)).fetchone()
        if skill:
            skill_id = skill["skillID"]
        else:
            db.execute("INSERT INTO Skills (skillName, skillCategoryID) VALUES (?, ?)", (skill_name, None))
            skill_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Check if employee already has this skill
        existing = db.execute(
            "SELECT * FROM EmployeeSkills WHERE empID = ? AND skillID = ?",
            (emp_id, skill_id)
        ).fetchone()

        if existing:
            # Update
            db.execute("""
                UPDATE EmployeeSkills
                SET profiencylevel = ?, evidence = ?
                WHERE empID = ? AND skillID = ?
            """, (level, evidence, emp_id, skill_id))
        else:
            # Create
            db.execute("""
                INSERT INTO EmployeeSkills (empID, skillID, profiencylevel, evidence)
                VALUES (?, ?, ?, ?)
            """, (emp_id, skill_id, level, evidence))

        db.commit()
        return redirect(url_for("employee_skills", emp_id=emp_id))

    # GET → fetch employee info + skills
    emp = db.execute("SELECT firstname, lastname FROM Employees WHERE empID = ?", (emp_id,)).fetchone()
    skills = db.execute("""
        SELECT s.skillID, s.skillName, es.profiencylevel, es.evidence
        FROM EmployeeSkills es
        JOIN Skills s ON es.skillID = s.skillID
        WHERE es.empID = ?
    """, (emp_id,)).fetchall()

    return render_template("employee_skills.html", emp=emp, skills=skills, emp_id=emp_id)


# ---------------------------
# Delete a Skill for Employee
# ---------------------------
@app.route("/employee/<int:emp_id>/delete/<int:skill_id>", methods=["POST"])
def delete_skill(emp_id, skill_id):
    db = get_db()
    db.execute("DELETE FROM EmployeeSkills WHERE empID = ? AND skillID = ?", (emp_id, skill_id))
    db.commit()
    print(f"Deleted skill {skill_id} for employee {emp_id}")  # debug
    return redirect(url_for("employee_skills", emp_id=emp_id))

# edit
@app.route("/employee/<int:emp_id>/edit/<int:skill_id>", methods=["POST"])
def edit_skill(emp_id, skill_id):
    db = get_db()
    level = request.form["profiencylevel"].strip()
    evidence = request.form["evidence"].strip()

    db.execute("""
        UPDATE EmployeeSkills
        SET profiencylevel = ?, evidence = ?
        WHERE empID = ? AND skillID = ?
    """, (level, evidence, emp_id, skill_id))
    db.commit()

    return redirect(url_for("employee_skills", emp_id=emp_id))

# ---------------------------
# Run App
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
