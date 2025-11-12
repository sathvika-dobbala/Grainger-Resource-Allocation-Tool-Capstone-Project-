import sqlite3
import random
from flask import g

DATABASE = "employees.db"

# --------------------------------------
# Connection Helper
# --------------------------------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


# --------------------------------------
# Initialize Tables
# --------------------------------------
def init_db():
    db = get_db()
    db.execute("PRAGMA foreign_keys = ON")

    # -----------------------------
    # Departments
    # -----------------------------
    db.execute("""
        CREATE TABLE IF NOT EXISTS Departments (
            depID INTEGER PRIMARY KEY AUTOINCREMENT,
            departmentname TEXT NOT NULL UNIQUE
        )
    """)

    # -----------------------------
    # Managers (for login)
    # -----------------------------
    db.execute("""
        CREATE TABLE IF NOT EXISTS Managers (
            managerID INTEGER PRIMARY KEY AUTOINCREMENT,
            firstname TEXT NOT NULL,
            lastname TEXT NOT NULL,
            title TEXT,
            department INTEGER NOT NULL,
            phone TEXT,
            email TEXT UNIQUE,
            password TEXT NOT NULL,
            FOREIGN KEY (department) REFERENCES Departments(depID)
        )
    """)

    # -----------------------------
    # Teams (per manager)
    # -----------------------------
    db.execute("""
        CREATE TABLE IF NOT EXISTS Teams (
            teamID INTEGER PRIMARY KEY AUTOINCREMENT,
            teamName TEXT NOT NULL UNIQUE,
            managerID INTEGER NOT NULL,
            department INTEGER NOT NULL,
            FOREIGN KEY (managerID) REFERENCES Managers(managerID),
            FOREIGN KEY (department) REFERENCES Departments(depID)
        )
    """)

    # -----------------------------
    # Employees (belong to department/team)
    # -----------------------------
    # db.execute("""
    #     CREATE TABLE IF NOT EXISTS Employees (
    #         empID INTEGER PRIMARY KEY AUTOINCREMENT,
    #         teamID INTEGER NOT NULL,
    #         firstname TEXT NOT NULL,
    #         lastname TEXT NOT NULL,
    #         title TEXT,
    #         email TEXT UNIQUE,
    #         phone TEXT,
    #         department INTEGER NOT NULL,
    #         FOREIGN KEY (teamID) REFERENCES Teams(teamID),
    #         FOREIGN KEY (department) REFERENCES Departments(depID)
    #     )
    # """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS Employees (
        empID INTEGER PRIMARY KEY AUTOINCREMENT,
        teamID INTEGER,
        firstname TEXT NOT NULL,
        lastname TEXT NOT NULL,
        title TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        department INTEGER NOT NULL,
        photo TEXT,  -- 🟢 new column for employee profile photo
        FOREIGN KEY (teamID) REFERENCES Teams(teamID),
        FOREIGN KEY (department) REFERENCES Departments(depID)
    );
""")

    # -----------------------------
    # Skill Categories / Skills
    # -----------------------------
    db.execute("""
        CREATE TABLE IF NOT EXISTS SkillCategories (
            skillCategoryID INTEGER PRIMARY KEY AUTOINCREMENT,
            skillCategoryname TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS Skills (
            skillID INTEGER PRIMARY KEY AUTOINCREMENT,
            skillName TEXT NOT NULL UNIQUE,
            skillCategoryID INTEGER,
            FOREIGN KEY (skillCategoryID) REFERENCES SkillCategories(skillCategoryID)
        )
    """)

    # -----------------------------
    # ManagerSkills / EmployeeSkills
    # -----------------------------
    db.execute("""
        CREATE TABLE IF NOT EXISTS ManagerSkills (
            managerID INTEGER NOT NULL,
            skillID INTEGER NOT NULL,
            PRIMARY KEY (managerID, skillID),
            FOREIGN KEY (managerID) REFERENCES Managers(managerID) ON DELETE CASCADE,
            FOREIGN KEY (skillID) REFERENCES Skills(skillID) ON DELETE CASCADE
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS EmployeeSkills (
            empID INTEGER NOT NULL,
            skillID INTEGER NOT NULL,
            profiencylevel INTEGER CHECK (profiencylevel BETWEEN 0 AND 10),
            evidence TEXT,
            PRIMARY KEY (empID, skillID),
            FOREIGN KEY (empID) REFERENCES Employees(empID) ON DELETE CASCADE,
            FOREIGN KEY (skillID) REFERENCES Skills(skillID) ON DELETE CASCADE
        )
    """)

    # -----------------------------
    # Projects / Skills / Assignments
    # -----------------------------
    db.execute("""
        CREATE TABLE IF NOT EXISTS Projects (
            projectID INTEGER PRIMARY KEY AUTOINCREMENT,
            teamID INTEGER NOT NULL,
            projectName TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'Not Started',
            startDate DATE DEFAULT CURRENT_DATE,
            endDate DATE,
            FOREIGN KEY (teamID) REFERENCES Teams(teamID)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS ProjectSkills (
            projectID INTEGER NOT NULL,
            skillID INTEGER NOT NULL,
            numpeopleneeded INTEGER NOT NULL CHECK (numpeopleneeded > 0),
            complexitylevel TEXT,
            PRIMARY KEY (projectID, skillID),
            FOREIGN KEY (projectID) REFERENCES Projects(projectID) ON DELETE CASCADE,
            FOREIGN KEY (skillID) REFERENCES Skills(skillID) ON DELETE CASCADE
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS ProjectAssignment (
            projectID INTEGER NOT NULL,
            empID INTEGER NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY (projectID, empID),
            FOREIGN KEY (projectID) REFERENCES Projects(projectID) ON DELETE CASCADE,
            FOREIGN KEY (empID) REFERENCES Employees(empID) ON DELETE CASCADE
        )
    """)

# initiali
    db.commit()
    print("✅ Database schema initialized successfully.")


# --------------------------------------
# Dummy Data Generator (Realistic)
# --------------------------------------
def insert_dummy_data():
    db = get_db()

    if db.execute("SELECT COUNT(*) FROM Managers").fetchone()[0] > 0:
        print("⚠️ Dummy data already exists. Skipping.")
        return

    # -----------------------------
    # Departments
    # -----------------------------
    departments = [
        ("Engineering",),
        ("Marketing",),
        ("Finance",),
        ("Human Resources",),
        ("IT & Infrastructure",)
    ]
    db.executemany("INSERT INTO Departments (departmentname) VALUES (?)", departments)

    # -----------------------------
    # Managers
    # -----------------------------
    manager_data = [
        ("Alice", "Smith", "Engineering Manager", 1, "alice@company.com", "password123"),
        ("Bob", "Jones", "Marketing Manager", 2, "bob@company.com", "password123"),
        ("Carol", "Nguyen", "Finance Manager", 3, "carol@company.com", "password123"),
        ("Daniel", "Brown", "HR Manager", 4, "daniel@company.com", "password123"),
        ("Emily", "Davis", "IT Manager", 5, "emily@company.com", "password123")
    ]
    db.executemany("""
        INSERT INTO Managers (firstname, lastname, title, department, email, password)
        VALUES (?, ?, ?, ?, ?, ?)
    """, manager_data)

    # -----------------------------
    # Teams
    # -----------------------------
    db.executemany("""
        INSERT INTO Teams (teamName, managerID, department)
        VALUES (?, ?, ?)
    """, [
        ("Alpha", 1, 1),
        ("Beta", 2, 2),
        ("Gamma", 3, 3),
        ("Delta", 4, 4),
        ("Epsilon", 5, 5)
    ])

    # -----------------------------
    # Skill Categories / Skills
    # -----------------------------
    categories = [
        ("Programming & Development",),
        ("Design & Creative",),
        ("Finance & Accounting",),
        ("HR & Recruitment",),
        ("IT & Infrastructure",)
    ]
    db.executemany("INSERT INTO SkillCategories (skillCategoryname) VALUES (?)", categories)

    skills_by_dept = {
        1: ["Python", "JavaScript", "SQL", "API Development", "Flask", "React", "Git", "Docker", "Testing", "Agile"],
        2: ["SEO", "Social Media Strategy", "Content Marketing", "Google Ads", "Email Campaigns", "Copywriting", "Graphic Design", "Branding", "Analytics"],
        3: ["Financial Analysis", "Budget Forecasting", "Excel", "Cost Accounting", "ERP Systems", "Data Modeling", "Reporting", "Accounting Principles"],
        4: ["Recruitment", "Employee Relations", "Training", "HR Policies", "Compensation", "Performance Management", "Conflict Resolution"],
        5: ["Network Security", "Cloud Administration", "Linux", "Troubleshooting", "System Monitoring", "Scripting", "Database Management", "Active Directory"]
    }

    for dept_id, skills in skills_by_dept.items():
        for skill in skills:
            db.execute("INSERT INTO Skills (skillName, skillCategoryID) VALUES (?, ?)", (skill, dept_id))

    # -----------------------------
    # Manager → Skills
    # -----------------------------
    for manager_id, dept_id in enumerate(skills_by_dept.keys(), start=1):
        skill_ids = db.execute("SELECT skillID FROM Skills WHERE skillCategoryID = ?", (dept_id,)).fetchall()
        db.executemany("INSERT INTO ManagerSkills (managerID, skillID) VALUES (?, ?)",
                       [(manager_id, s["skillID"]) for s in skill_ids])

    # -----------------------------
    # Realistic Employees (15 per dept) + UNIQUE emails
    # -----------------------------
    employee_data = {
        1: [  # Engineering
            ("Liam", "Johnson", "Software Engineer"), ("Olivia", "Miller", "Backend Developer"),
            ("Noah", "Davis", "Frontend Engineer"), ("Emma", "Wilson", "QA Tester"),
            ("Ava", "Garcia", "DevOps Engineer"), ("Sophia", "Martinez", "Data Engineer"),
            ("Jackson", "Lopez", "Software Developer"), ("Mia", "Hernandez", "Automation Tester"),
            ("Lucas", "Hall", "Full Stack Developer"), ("Isabella", "Allen", "Cloud Engineer"),
            ("Ethan", "Young", "Software Engineer"), ("Charlotte", "King", "Systems Analyst"),
            ("James", "Wright", "API Specialist"), ("Amelia", "Scott", "Release Engineer"),
            ("Benjamin", "Green", "Junior Developer")
        ],
        2: [  # Marketing
            ("Grace", "Baker", "SEO Specialist"), ("Henry", "Adams", "Brand Strategist"),
            ("Ella", "Carter", "Marketing Analyst"), ("Lily", "Turner", "Content Writer"),
            ("Samuel", "Collins", "Social Media Manager"), ("Victoria", "Perez", "Graphic Designer"),
            ("Daniel", "Campbell", "Copywriter"), ("Aria", "Stewart", "Campaign Specialist"),
            ("Matthew", "Patterson", "Email Marketing Manager"), ("Scarlett", "Murphy", "Marketing Coordinator"),
            ("William", "Gray", "Market Research Analyst"), ("Zoe", "Ramirez", "Creative Director"),
            ("Nathan", "Cook", "Digital Strategist"), ("Harper", "Bell", "Ad Operations Manager"),
            ("Andrew", "Price", "Communications Associate")
        ],
        3: [  # Finance
            ("Jacob", "Mitchell", "Financial Analyst"), ("Emily", "Hughes", "Accountant"),
            ("Alexander", "Ward", "Auditor"), ("Sofia", "Cox", "Budget Specialist"),
            ("Michael", "Richardson", "Treasury Analyst"), ("Chloe", "Howard", "Risk Analyst"),
            ("Evelyn", "Ross", "Data Modeler"), ("Sebastian", "Barnes", "Tax Analyst"),
            ("Aiden", "Foster", "Finance Associate"), ("Hannah", "Powell", "Accounts Payable Clerk"),
            ("Jack", "Long", "Controller"), ("Layla", "Reed", "Financial Planner"),
            ("David", "Cook", "Payroll Coordinator"), ("Isla", "Morgan", "Billing Analyst"),
            ("Owen", "Bailey", "Compliance Specialist")
        ],
        4: [  # HR
            ("Samantha", "Rivera", "HR Specialist"), ("Logan", "Brooks", "Recruiter"),
            ("Leah", "Edwards", "Onboarding Coordinator"), ("Ryan", "Sanders", "HR Generalist"),
            ("Nora", "Fisher", "Compensation Analyst"), ("Caleb", "Henderson", "Employee Relations"),
            ("Avery", "Coleman", "Learning & Development"), ("Isaac", "Perry", "Talent Acquisition"),
            ("Abigail", "Peterson", "Benefits Coordinator"), ("Wyatt", "Evans", "Performance Analyst"),
            ("Madison", "Simmons", "HR Assistant"), ("Elijah", "Butler", "Training Facilitator"),
            ("Penelope", "Foster", "HRIS Specialist"), ("Gabriel", "Gonzalez", "Workforce Planner"),
            ("Victoria", "James", "Recruitment Specialist")
        ],
        5: [  # IT
            ("Lucas", "Thompson", "Network Engineer"), ("Mila", "Martinez", "IT Support Specialist"),
            ("Oliver", "Moore", "Cloud Administrator"), ("Ella", "Clark", "Systems Engineer"),
            ("Leo", "Walker", "Security Analyst"), ("Sofia", "Lewis", "Database Administrator"),
            ("Ethan", "Young", "Infrastructure Engineer"), ("Layla", "Hill", "System Admin"),
            ("Henry", "Allen", "IT Technician"), ("Isabella", "Adams", "Helpdesk Specialist"),
            ("Liam", "Bennett", "Cloud Engineer"), ("Ava", "Perez", "IT Coordinator"),
            ("Noah", "Brooks", "Monitoring Specialist"), ("Charlotte", "Price", "Operations Analyst"),
            ("James", "Ward", "Hardware Specialist")
        ]
    }

    # helper to ensure email uniqueness
    def _unique_email(db, fname, lname, domain="company.com"):
        base = f"{fname.lower()}.{lname.lower()}@{domain}"
        email = base
        n = 2
        while db.execute(
            "SELECT 1 FROM Employees WHERE email = ? UNION SELECT 1 FROM Managers WHERE email = ? LIMIT 1",
            (email, email)
        ).fetchone():
            email = f"{fname.lower()}.{lname.lower()}.{n}@{domain}"
            n += 1
        return email

    for dept_id, employees in employee_data.items():
        team_id = dept_id
        records = []
        for (fname, lname, title) in employees:
            email = _unique_email(db, fname, lname)
            records.append((team_id, fname, lname, title, email, dept_id))

        db.executemany("""
            INSERT INTO Employees (teamID, firstname, lastname, title, email, department)
            VALUES (?, ?, ?, ?, ?, ?)
        """, records)

    # -----------------------------
    # Employee → Skills (0–10 scale)
    # -----------------------------
    for dept_id in range(1, 6):
        emp_rows = db.execute("SELECT empID FROM Employees WHERE department = ?", (dept_id,)).fetchall()
        skill_rows = db.execute("SELECT skillID FROM Skills WHERE skillCategoryID = ?", (dept_id,)).fetchall()
        for emp in emp_rows:
            for skill in skill_rows:
                prof = random.randint(0, 10)
                evidence = None if prof == 0 else "Auto-assigned skill rating"
                db.execute("""
                    INSERT INTO EmployeeSkills (empID, skillID, profiencylevel, evidence)
                    VALUES (?, ?, ?, ?)
                """, (emp["empID"], skill["skillID"], prof, evidence))

    db.commit()
    print("✅ Dummy data inserted successfully with realistic names and UNIQUE emails.")


# --------------------------------------
# Optional Reset Helper
# --------------------------------------
def reset_database():
    db = get_db()
    tables = ["Departments", "Managers", "Teams", "Employees", "SkillCategories",
              "Skills", "ManagerSkills", "EmployeeSkills", "Projects", "ProjectSkills", "ProjectAssignment"]
    for t in tables:
        db.execute(f"DROP TABLE IF EXISTS {t}")
    db.commit()
    print("🧹 Database cleared. Run init_db() then insert_dummy_data().")



    



