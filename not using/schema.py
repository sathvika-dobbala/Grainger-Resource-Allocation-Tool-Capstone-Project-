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
        ("Human Resources",)
    ])

    # Insert Skill Categories
    db.executemany("INSERT INTO SkillCategories (skillCategoryname) VALUES (?)", [
        ("Programming",),
        ("Design",),
        ("Communication",)
    ])

    # Insert Skills
    db.executemany("INSERT INTO Skills (skillName, skillCategoryID) VALUES (?, ?)", [
        ("Python", 1),
        ("Graphic Design", 2),
        ("Public Speaking", 3)
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

    # Insert Employees
    db.executemany("INSERT INTO Employees (teamID, firstname, lastname, title, department, email, phone, photo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
        (team1_id, "Charlie", "Brown", "Software Engineer", 1, "charlie@example.com", "1112223333", None),
        (team2_id, "Dana", "White", "Marketing Specialist", 2, "dana@example.com", "4445556666", None)
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