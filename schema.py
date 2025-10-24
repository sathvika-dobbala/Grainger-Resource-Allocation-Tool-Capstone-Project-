import sqlite3
from flask import g

DATABASE = "employees.db"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute("PRAGMA foreign_keys = ON")

    # Departments
    db.execute("""
        CREATE TABLE IF NOT EXISTS Departments (
            depID INTEGER PRIMARY KEY AUTOINCREMENT,
            departmentname TEXT NOT NULL
        )
    """)

    # Skill Categories
    db.execute("""
        CREATE TABLE IF NOT EXISTS SkillCategories (
            skillCategoryID INTEGER PRIMARY KEY AUTOINCREMENT,
            skillCategoryname TEXT NOT NULL
        )
    """)

    # Skills
    db.execute("""
        CREATE TABLE IF NOT EXISTS Skills (
            skillID INTEGER PRIMARY KEY AUTOINCREMENT,
            skillName TEXT NOT NULL UNIQUE,
            skillCategoryID INTEGER,
            FOREIGN KEY (skillCategoryID) REFERENCES SkillCategories(skillCategoryID) ON DELETE SET NULL
        )
    """)

    # Teams
    db.execute("""
        CREATE TABLE IF NOT EXISTS Teams (
            teamID INTEGER PRIMARY KEY AUTOINCREMENT,
            teamName TEXT NOT NULL UNIQUE,
            managerID INTEGER,
            department INTEGER NOT NULL,
            FOREIGN KEY (managerID) REFERENCES Managers(managerID),
            FOREIGN KEY (department) REFERENCES Departments(depID) ON DELETE RESTRICT
        )
    """)

    # Managers
    db.execute("""
        CREATE TABLE IF NOT EXISTS Managers (
            managerID INTEGER PRIMARY KEY AUTOINCREMENT,
            teamID INTEGER,
            firstname TEXT,
            lastname TEXT NOT NULL,
            title TEXT,
            department TEXT,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            photo BLOB,
            FOREIGN KEY (teamID) REFERENCES Teams(teamID)
        )
    """)

    # Employees
    db.execute("""
        CREATE TABLE IF NOT EXISTS Employees (
            empID INTEGER PRIMARY KEY AUTOINCREMENT,
            teamID INTEGER,
            firstname TEXT,
            lastname TEXT NOT NULL,
            title TEXT,
            department INTEGER NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            photo BLOB,
            FOREIGN KEY (teamID) REFERENCES Teams(teamID),
            FOREIGN KEY (department) REFERENCES Departments(depID)
        )
    """)

    # EmployeeSkills
    db.execute("""
        CREATE TABLE IF NOT EXISTS EmployeeSkills (
            empID INTEGER NOT NULL,
            skillID INTEGER NOT NULL,
            profiencylevel INTEGER,
            evidence TEXT,
            PRIMARY KEY (empID, skillID),
            FOREIGN KEY (empID) REFERENCES Employees(empID) ON DELETE CASCADE,
            FOREIGN KEY (skillID) REFERENCES Skills(skillID) ON DELETE RESTRICT
        )
    """)

    # Projects
    db.execute("""
        CREATE TABLE IF NOT EXISTS Projects (
            projectID INTEGER PRIMARY KEY AUTOINCREMENT,
            teamID INTEGER NOT NULL,
            projectName TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'Not Started',
            startDate DATE NOT NULL DEFAULT CURRENT_DATE,
            endDate DATE,
            FOREIGN KEY (teamID) REFERENCES Teams(teamID)
        )
    """)

    # ProjectSkills
    db.execute("""
        CREATE TABLE IF NOT EXISTS ProjectSkills (
            projectID INTEGER NOT NULL,
            skillID INTEGER NOT NULL,
            numpeopleneeded INTEGER NOT NULL CHECK (numpeopleneeded > 0),
            complexitylevel TEXT,
            PRIMARY KEY (projectID, skillID),
            FOREIGN KEY (projectID) REFERENCES Projects(projectID) ON DELETE CASCADE,
            FOREIGN KEY (skillID) REFERENCES Skills(skillID) ON DELETE RESTRICT
        )
    """)

    # ProjectAssignment
    db.execute("""
        CREATE TABLE IF NOT EXISTS ProjectAssignment (
            projectID INTEGER NOT NULL,
            empID INTEGER NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY (projectID, empID),
            FOREIGN KEY (projectID) REFERENCES Projects(projectID) ON DELETE CASCADE,
            FOREIGN KEY (empID) REFERENCES Employees(empID) ON DELETE RESTRICT
        )
    """)

    db.commit()
    print("✅ Database schema initialized with all tables.")

def insert_dummy_data():
    db = get_db()

    # Skip if data already exists
    existing = db.execute("SELECT COUNT(*) FROM Skills").fetchone()[0]
    if existing > 0:
        print("⚠️ Dummy data already exists. Skipping insert.")
        return

    # Insert Departments
    db.executemany("INSERT INTO Departments (departmentname) VALUES (?)", [
    ("Engineering",),
    ("Marketing",),
    ("Human Resources",),
    ("Finance",),
    ("Operations",),
    ("IT & Infrastructure",),
    ("Customer Support",),
    ("Research & Development",),
    ("Legal & Compliance",),
    ("Sales",),
    ("Procurement",),
    ("Product Management",),
    ("Design",),
    ("Quality Assurance",),
    ("Corporate Strategy",)
])

# Insert Skill Categories
    db.executemany("INSERT INTO SkillCategories (skillCategoryname) VALUES (?)", [
    ("Programming & Development",),
    ("Design & Creative",),
    ("Communication & Leadership",),
    ("Data & Analytics",),
    ("Cloud & DevOps",),
    ("Project Management",),
    ("Finance & Operations",),
    ("Sales & Marketing",)
])

# Insert Skills (expanded and categorized)
    db.executemany("INSERT INTO Skills (skillName, skillCategoryID) VALUES (?, ?)", [

    # 1️⃣ Programming & Development
    ("Python", 1),
    ("Java", 1),
    ("C++", 1),
    ("C#", 1),
    ("JavaScript", 1),
    ("TypeScript", 1),
    ("SQL", 1),
    ("HTML/CSS", 1),
    ("R", 1),
    ("Go", 1),
    ("React", 1),
    ("Angular", 1),
    ("Vue.js", 1),
    ("Node.js", 1),
    ("Flask", 1),
    ("Django", 1),
    (".NET", 1),
    ("Spring Boot", 1),
    ("API Development", 1),
    ("Version Control (Git)", 1),

    # 2️⃣ Design & Creative
    ("Graphic Design", 2),
    ("UI/UX Design", 2),
    ("Wireframing", 2),
    ("Prototyping", 2),
    ("Adobe Photoshop", 2),
    ("Adobe Illustrator", 2),
    ("Figma", 2),
    ("Canva", 2),


    # # 3️⃣ Communication & Leadership
    ("Business Writing", 3),
    ("Presentation Skills", 3),
    ("Team Collaboration", 3),

    # # 4️⃣ Data & Analytics
    ("Power BI", 4),
    ("Tableau", 4),
    ("Excel (Advanced)", 4),
    ("Data Visualization", 4),
    ("Data Cleaning", 4),
    ("SQL for Analysis", 4),
    ("Pandas", 4),
    ("NumPy", 4),
    ("Machine Learning", 4),
    ("Predictive Modeling", 4),
    ("A/B Testing", 4),
    ("Statistics", 4),
    ("Data Storytelling", 4),

    # # 5️⃣ Cloud & DevOps
    ("AWS", 5),
    ("Azure", 5),
    ("Google Cloud Platform", 5),
    ("CI/CD Pipelines", 5),
    ("Docker", 5),
    ("Kubernetes", 5),
    ("Linux Administration", 5),
    ("Terraform", 5),
    ("Cloud Security", 5),
    ("Load Balancing", 5),

    # # 6️⃣ Project Management
    ("Agile", 6),
    ("Scrum", 6),
    ("Kanban", 6),
    ("Waterfall", 6),
    ("Risk Management", 6),
    ("Budget Tracking", 6),
    ("Jira", 6),
    ("Asana", 6),
    ("Trello", 6),

    # # 7️⃣ Finance & Operations
    ("Financial Analysis", 7),
    ("Budget Forecasting", 7),
    ("Cost Accounting", 7),
    ("Procurement", 7),
    ("Supply Chain Management", 7),
    ("Inventory Planning", 7),
    ("Process Optimization", 7),
    ("ERP Systems", 7),
    ("SAP", 7),
    ("Data-Driven Decision Making", 7),

    # # 8️⃣ Sales & Marketing
    ("Digital Marketing", 8),
    ("Social Media Strategy", 8),
    ("SEO", 8),
    ("Google Ads", 8),
    ("Email Campaigns", 8),
    ("Lead Generation", 8),
    ("Customer Retention", 8),
    ("Sales Forecasting", 8),
    ("Market Research", 8),
    ("Brand Awareness", 8)
])


    # Insert Teams with NULL managerID
    db.executemany("INSERT INTO Teams (teamName, managerID, department) VALUES (?, ?, ?)", [
        ("Alpha", None, 1),
        ("Beta", None, 2)
    ])

    # Get team IDs
    team_ids = db.execute("SELECT teamID FROM Teams ORDER BY teamID").fetchall()
    team1_id = team_ids[0]["teamID"]
    team2_id = team_ids[1]["teamID"]

    # Insert Managers with NULL teamID
    db.executemany("INSERT INTO Managers (teamID, firstname, lastname, title, department, email, phone, photo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
        (None, "Alice", "Smith", "Engineering Manager", "Engineering", "alice@example.com", "1234567890", None),
        (None, "Bob", "Jones", "Marketing Manager", "Marketing", "bob@example.com", "0987654321", None)
    ])

    # Get manager IDs
    manager_ids = db.execute("SELECT managerID FROM Managers ORDER BY managerID").fetchall()
    manager1_id = manager_ids[0]["managerID"]
    manager2_id = manager_ids[1]["managerID"]

    # Update Teams with managerID
    db.execute("UPDATE Teams SET managerID = ? WHERE teamID = ?", (manager1_id, team1_id))
    db.execute("UPDATE Teams SET managerID = ? WHERE teamID = ?", (manager2_id, team2_id))

    # Update Managers with teamID
    db.execute("UPDATE Managers SET teamID = ? WHERE managerID = ?", (team1_id, manager1_id))
    db.execute("UPDATE Managers SET teamID = ? WHERE managerID = ?", (team2_id, manager2_id))

  # Insert Employees (expanded dataset)
    db.executemany("INSERT INTO Employees (teamID, firstname, lastname, title, department, email, phone, photo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
    # Engineering
    # (team1_id, "Charlie", "Brown", "Software Engineer", 1, "charlie@example.com", "1112223333", None),
    # (team1_id, "Emily", "Johnson", "Frontend Developer", 1, "emily.johnson@example.com", "2223334444", None),
    # (team1_id, "Michael", "Lee", "Backend Engineer", 1, "michael.lee@example.com", "3334445555", None),
    # (team1_id, "Sophia", "Wang", "Full Stack Developer", 1, "sophia.wang@example.com", "4445556666", None),
    # (team1_id, "David", "Kim", "DevOps Engineer", 1, "david.kim@example.com", "5556667777", None),

    # Marketing
    # (team2_id, "Dana", "White", "Marketing Specialist", 2, "dana@example.com", "4445556666", None),
    # (team2_id, "Olivia", "Martinez", "Digital Marketing Analyst", 2, "olivia.martinez@example.com", "8889990000", None),
    # (team2_id, "Lucas", "Hernandez", "SEO Strategist", 2, "lucas.hernandez@example.com", "7778889999", None),
    # (team2_id, "Ella", "Nguyen", "Content Manager", 2, "ella.nguyen@example.com", "6665554444", None),

    # Human Resources
    # (team2_id, "Grace", "Li", "HR Manager", 3, "grace.li@example.com", "9998887777", None),
    # (team2_id, "Henry", "Clark", "Recruiter", 3, "henry.clark@example.com", "1012023030", None),
    # (team2_id, "Isabella", "Adams", "Training Specialist", 3, "isabella.adams@example.com", "3034045050", None),

    # Finance
    # (team1_id, "Jack", "Taylor", "Financial Analyst", 4, "jack.taylor@example.com", "4045056060", None),
    # (team1_id, "Lily", "Evans", "Accountant", 4, "lily.evans@example.com", "5056067070", None),
    # (team1_id, "Noah", "Davis", "Budget Coordinator", 4, "noah.davis@example.com", "6067078080", None),

    # IT & Operations
    # (team1_id, "Ryan", "Green", "IT Support Specialist", 6, "ryan.green@example.com", "7078089090", None),
    # (team1_id, "Mia", "Thompson", "System Administrator", 6, "mia.thompson@example.com", "8089090101", None),
    # (team1_id, "Benjamin", "Carter", "Network Engineer", 6, "benjamin.carter@example.com", "9090101112", None),

    # Operations / Logistics
    (team2_id, "Ava", "Mitchell", "Operations Coordinator", 5, "ava.mitchell@example.com", "1213141516", None),
    (team2_id, "Ethan", "Rivera", "Supply Chain Analyst", 5, "ethan.rivera@example.com", "1615141312", None)
])


    # Insert Employee Skills
    db.executemany("INSERT INTO EmployeeSkills (empID, skillID, profiencylevel, evidence) VALUES (?, ?, ?, ?)", [
        (1, 1, 5, "Completed Python Bootcamp"),
        (2, 2, 4, "Designed marketing materials")
    ])

    # Insert Projects
    db.executemany("INSERT INTO Projects (teamID, projectName, status) VALUES (?, ?, ?)", [
        (team1_id, "Internal Tool Development", "In Progress"),
        (team2_id, "Product Launch Campaign", "Not Started")
    ])

    # Insert Project Skills
    db.executemany("INSERT INTO ProjectSkills (projectID, skillID, numpeopleneeded, complexitylevel) VALUES (?, ?, ?, ?)", [
        (1, 1, 2, "High"),
        (2, 2, 1, "Medium")
    ])

    # Insert Project Assignments
    db.executemany("INSERT INTO ProjectAssignment (projectID, empID, role) VALUES (?, ?, ?)", [
        (1, 1, "Developer"),
        (2, 2, "Designer")
    ])

    db.commit()
    print("✅ Dummy data inserted successfully.")