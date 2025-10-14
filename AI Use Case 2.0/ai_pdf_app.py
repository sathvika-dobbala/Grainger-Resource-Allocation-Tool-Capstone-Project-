# .\.venv\Scripts\python.exe ai_pdf_app.py


# ai_pdf_app.py
import os
import sys
import json
import textwrap
import sqlite3
import random
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Iterable, Set

from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()  # load .env

DB_PATH = os.getenv("EMPLOYEE_DB_PATH", "employees.db")

# =========================
# Workload-aware config
# =========================
# Which project statuses count as "active" (affect availability)
ACTIVE_STATUSES = {"Not Started", "In Progress"}
# Hard cap before a person is excluded from suggestions
MAX_ACTIVE_ASSIGNMENTS = int(os.getenv("MAX_ACTIVE_ASSIGNMENTS", "3"))
# Linear penalty applied per active assignment (subtracted from skill score)
PENALTY_PER_ACTIVE = int(os.getenv("PENALTY_PER_ACTIVE", "10"))

# =========================
# PDF utilities
# =========================
def choose_pdf_file() -> str:
    try:
        from tkinter import Tk, filedialog
        root = Tk(); root.withdraw()
        path = filedialog.askopenfilename(title="Select case PDF", filetypes=[("PDF files","*.pdf")])
        root.destroy()
        if not path:
            raise RuntimeError("No file selected.")
        return path
    except Exception:
        path = input("Enter full path to a .pdf file: ").strip().strip('"')
        if not (path and os.path.isfile(path) and path.lower().endswith(".pdf")):
            raise RuntimeError(f"Invalid PDF path: {path}")
        return path

def extract_text_from_pdf(path: str) -> str:
    reader = PdfReader(path)
    parts: List[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n\n".join(parts).strip()

def clamp_text(s: str, max_chars: int = 120_000) -> str:
    if len(s) <= max_chars:
        return s
    half = max_chars // 2
    return s[:half] + "\n\n[...TRUNCATED MIDDLE...]\n\n" + s[-half:]


# =========================
# SQLite (schema + helpers)
# =========================
def _conn(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(db_path: str = DB_PATH) -> None:
    """
    Creates ALL tables you provided (Departments, SkillCategories, Skills, Teams, Managers,
    Employees, EmployeeSkills, Projects, ProjectSkills, ProjectAssignment).
    """
    conn = _conn(db_path)
    try:
        # Departments
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Departments (
                depID INTEGER PRIMARY KEY AUTOINCREMENT,
                departmentname TEXT NOT NULL
            )
        """)

        # Skill Categories
        conn.execute("""
            CREATE TABLE IF NOT EXISTS SkillCategories (
                skillCategoryID INTEGER PRIMARY KEY AUTOINCREMENT,
                skillCategoryname TEXT NOT NULL
            )
        """)

        # Skills
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Skills (
                skillID INTEGER PRIMARY KEY AUTOINCREMENT,
                skillName TEXT NOT NULL UNIQUE,
                skillCategoryID INTEGER,
                FOREIGN KEY (skillCategoryID) REFERENCES SkillCategories(skillCategoryID) ON DELETE SET NULL
            )
        """)

        # Teams
        conn.execute("""
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
        conn.execute("""
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
        conn.execute("""
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
        conn.execute("""
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
        conn.execute("""
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
        conn.execute("""
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ProjectAssignment (
                projectID INTEGER NOT NULL,
                empID INTEGER NOT NULL,
                role TEXT NOT NULL,
                PRIMARY KEY (projectID, empID),
                FOREIGN KEY (projectID) REFERENCES Projects(projectID) ON DELETE CASCADE,
                FOREIGN KEY (empID) REFERENCES Employees(empID) ON DELETE RESTRICT
            )
        """)

        conn.commit()
        print("✅ Database schema initialized.")
    finally:
        conn.close()

def seed_skills_if_empty(db_path: str = DB_PATH) -> None:
    """
    Optional: seed a few SkillCategories and Skills so you can test the app
    even if the DB starts empty. Replace with your real taxonomy anytime.
    """
    conn = _conn(db_path)
    try:
        cur = conn.execute("SELECT COUNT(*) AS c FROM Skills")
        if cur.fetchone()["c"] > 0:
            return  # already populated

        # Ensure categories
        conn.execute("INSERT INTO SkillCategories(skillCategoryname) VALUES (?)", ("Technical",))
        conn.execute("INSERT INTO SkillCategories(skillCategoryname) VALUES (?)", ("Analytics",))
        conn.execute("INSERT INTO SkillCategories(skillCategoryname) VALUES (?)", ("Project/Process",))
        conn.execute("INSERT INTO SkillCategories(skillCategoryname) VALUES (?)", ("Communication",))

        cat_lookup = dict(
            (row["skillCategoryname"], row["skillCategoryID"])
            for row in conn.execute("SELECT skillCategoryID, skillCategoryname FROM SkillCategories")
        )

        samples = [
            ("Python", cat_lookup.get("Technical")),
            ("SQL", cat_lookup.get("Technical")),
            ("Data Analysis", cat_lookup.get("Analytics")),
            ("Requirements Gathering", cat_lookup.get("Project/Process")),
            ("Project Management", cat_lookup.get("Project/Process")),
            ("Risk Assessment", cat_lookup.get("Project/Process")),
            ("Process Mapping", cat_lookup.get("Project/Process")),
            ("Stakeholder Communication", cat_lookup.get("Communication")),
            ("Technical Writing", cat_lookup.get("Communication")),
            ("Presentation Skills", cat_lookup.get("Communication")),
        ]
        for name, cid in samples:
            conn.execute("INSERT OR IGNORE INTO Skills(skillName, skillCategoryID) VALUES (?, ?)", (name, cid))

        conn.commit()
        print("✅ Seeded Skills with example values.")
    finally:
        conn.close()

# ===== NEW: Org + Employee dummy data seeding =====
def _get_or_create_department(conn, name: str) -> int:
    row = conn.execute("SELECT depID FROM Departments WHERE departmentname=?", (name,)).fetchone()
    if row: return row["depID"]
    cur = conn.execute("INSERT INTO Departments(departmentname) VALUES (?)", (name,))
    return cur.lastrowid

def _get_skill_id_map(conn) -> Dict[str, int]:
    return {r["skillName"]: r["skillID"] for r in conn.execute("SELECT skillID, skillName FROM Skills")}

def seed_org_if_empty(db_path: str = DB_PATH) -> None:
    """
    Seeds Departments, Teams, Managers, Employees, EmployeeSkills with realistic dummy data
    that references the Skills table. Safe to call multiple times.
    """
    random.seed(42)  # reproducible

    conn = _conn(db_path)
    try:
        # Departments
        dep_names = ["Engineering", "Analytics", "Operations", "PMO", "Security"]
        dep_ids = {name: _get_or_create_department(conn, name) for name in dep_names}

        # Managers (ensure at least 4)
        mgr_count = conn.execute("SELECT COUNT(*) AS c FROM Managers").fetchone()["c"]
        if mgr_count < 4:
            managers = [
                ("Ava", "Johnson", "Director of Data", "Analytics", "ava.johnson@example.com", "555-1111"),
                ("Liam", "Carter", "Director of Engineering", "Engineering", "liam.carter@example.com", "555-2222"),
                ("Maya", "Singh", "PMO Lead", "PMO", "maya.singh@example.com", "555-3333"),
                ("Noah", "Bennett", "Security Lead", "Security", "noah.bennett@example.com", "555-4444"),
            ]
            for fn, ln, title, dept_txt, email, phone in managers:
                conn.execute("""
                    INSERT OR IGNORE INTO Managers(firstname, lastname, title, department, email, phone)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (fn, ln, title, dept_txt, email, phone))

        # Teams
        team_count = conn.execute("SELECT COUNT(*) AS c FROM Teams").fetchone()["c"]
        if team_count < 4:
            # temporarily create teams with NULL manager; we will backfill after insert
            team_defs = [
                ("Data Science", dep_ids["Analytics"]),
                ("Platform Engineering", dep_ids["Engineering"]),
                ("Project Management Office", dep_ids["PMO"]),
                ("Risk & Compliance", dep_ids["Security"]),
            ]
            for team_name, dep_id in team_defs:
                conn.execute(
                    "INSERT OR IGNORE INTO Teams(teamName, department) VALUES (?, ?)",
                    (team_name, dep_id)
                )

            # Assign managers to teams
            team_rows = conn.execute("SELECT teamID, teamName FROM Teams").fetchall()
            mgr_rows = conn.execute("SELECT managerID, email FROM Managers ORDER BY managerID").fetchall()
            for i, t in enumerate(team_rows):
                mgr_id = mgr_rows[i % len(mgr_rows)]["managerID"]
                conn.execute("UPDATE Teams SET managerID=? WHERE teamID=?", (mgr_id, t["teamID"]))
                conn.execute("UPDATE Managers SET teamID=? WHERE managerID=?", (t["teamID"], mgr_id))

        # Employees
        emp_count = conn.execute("SELECT COUNT(*) AS c FROM Employees").fetchone()["c"]
        if emp_count < 16:
            # team lookups
            teams = {r["teamName"]: r["teamID"] for r in conn.execute("SELECT teamID, teamName FROM Teams")}
            employees = [
                # fn, ln, title, dep, team, email
                ("Ethan", "Wright", "Data Analyst", "Analytics", "Data Science", "ethan.wright@example.com"),
                ("Sofia", "Martinez", "Data Scientist", "Analytics", "Data Science", "sofia.martinez@example.com"),
                ("Oliver", "Nguyen", "ML Engineer", "Engineering", "Platform Engineering", "oliver.nguyen@example.com"),
                ("Amelia", "Patel", "Backend Engineer", "Engineering", "Platform Engineering", "amelia.patel@example.com"),
                ("Lucas", "Kim", "Security Analyst", "Security", "Risk & Compliance", "lucas.kim@example.com"),
                ("Emma", "Diaz", "Risk Analyst", "Security", "Risk & Compliance", "emma.diaz@example.com"),
                ("William", "Harris", "Project Manager", "PMO", "Project Management Office", "william.harris@example.com"),
                ("Mia", "Lopez", "Business Analyst", "PMO", "Project Management Office", "mia.lopez@example.com"),
                ("Henry", "Zhao", "Data Engineer", "Engineering", "Platform Engineering", "henry.zhao@example.com"),
                ("Avery", "Thompson", "Technical Writer", "PMO", "Project Management Office", "avery.thompson@example.com"),
                ("James", "Beck", "Senior Analyst", "Analytics", "Data Science", "james.beck@example.com"),
                ("Chloe", "Rossi", "Presentation Specialist", "PMO", "Project Management Office", "chloe.rossi@example.com"),
                ("Noel", "Ibrahim", "SQL Developer", "Engineering", "Platform Engineering", "noel.ibrahim@example.com"),
                ("Bianca", "Kaur", "Process Analyst", "Operations", "Project Management Office", "bianca.kaur@example.com"),
                ("Zane", "Ford", "Requirements Lead", "PMO", "Project Management Office", "zane.ford@example.com"),
                ("Priya", "Natarajan", "Risk Consultant", "Security", "Risk & Compliance", "priya.natarajan@example.com"),
            ]
            for fn, ln, title, dep_name, team_name, email in employees:
                conn.execute("""
                    INSERT OR IGNORE INTO Employees(firstname, lastname, title, department, teamID, email, phone)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (fn, ln, title, dep_ids[dep_name], teams[team_name], email, "555-0000"))

        # EmployeeSkills (tie to Skills)
        skill_map = _get_skill_id_map(conn)
        # Simple skill sets per role archetype
        role_skills = {
            "Data Analyst": ["Python", "SQL", "Data Analysis", "Presentation Skills"],
            "Data Scientist": ["Python", "SQL", "Data Analysis", "Stakeholder Communication"],
            "ML Engineer": ["Python", "SQL", "Technical Writing"],
            "Backend Engineer": ["Python", "SQL", "Technical Writing"],
            "Data Engineer": ["Python", "SQL", "Process Mapping"],
            "SQL Developer": ["SQL", "Technical Writing"],
            "Project Manager": ["Project Management", "Stakeholder Communication", "Requirements Gathering", "Presentation Skills"],
            "Business Analyst": ["Requirements Gathering", "Process Mapping", "Stakeholder Communication"],
            "Technical Writer": ["Technical Writing", "Presentation Skills"],
            "Presentation Specialist": ["Presentation Skills", "Stakeholder Communication"],
            "Process Analyst": ["Process Mapping", "Data Analysis", "Stakeholder Communication"],
            "Requirements Lead": ["Requirements Gathering", "Stakeholder Communication", "Project Management"],
            "Security Analyst": ["Risk Assessment", "Process Mapping", "Technical Writing"],
            "Risk Analyst": ["Risk Assessment", "Data Analysis", "Presentation Skills"],
            "Risk Consultant": ["Risk Assessment", "Stakeholder Communication", "Project Management"],
            "Senior Analyst": ["Data Analysis", "Presentation Skills", "Stakeholder Communication"],
        }
        # populate prof levels 2-5 (slight randomness)
        emp_rows = conn.execute("SELECT empID, title FROM Employees").fetchall()
        for emp in emp_rows:
            skills_for_role = role_skills.get(emp["title"], [])
            for s in skills_for_role:
                sid = skill_map.get(s)
                if not sid:
                    continue
                prof = random.choice([3, 4, 5, 4, 3])  # bias to 3-4
                conn.execute("""
                    INSERT OR IGNORE INTO EmployeeSkills(empID, skillID, profiencylevel, evidence)
                    VALUES (?, ?, ?, ?)
                """, (emp["empID"], sid, prof, f"{s} portfolio / prior project"))

        conn.commit()
        print("✅ Seeded organization: departments, teams, managers, employees, and employee skills.")
    finally:
        conn.close()

@dataclass
class SkillRow:
    skillID: int
    skillName: str
    skillCategoryID: Optional[int]

def load_allowed_skills(db_path: str = DB_PATH) -> List[SkillRow]:
    conn = _conn(db_path)
    try:
        cur = conn.execute("""
            SELECT skillID, skillName, skillCategoryID
            FROM Skills
            ORDER BY skillName COLLATE NOCASE
        """)
        rows = cur.fetchall()
        return [SkillRow(r["skillID"], r["skillName"], r["skillCategoryID"]) for r in rows]
    finally:
        conn.close()


# =========================
# Prompt + parsing
# =========================
def build_constrained_prompt(pdf_text: str, skills: List[SkillRow]) -> str:
    catalog_lines = [f"{s.skillID} | {s.skillName}" for s in skills]
    catalog = "\n".join(catalog_lines)

    return textwrap.dedent(f"""
    You are a business consultant AI.

    Below is the full content of a case project assigned to a team.
    You are given a catalog of allowed skills (with IDs). You MUST select the Top 5 skills
    only from the allowed catalog — do not invent new skills or variations.

    Return STRICT JSON (no code fences, no extra text) with this schema:
    {{
      "top5": [
        {{"skillID": <int>, "skillName": "<exact from catalog>", "reason": "<1-2 sentences tied to the case>"}}
      ]
    }}

    Rules:
    - Use only skills from the catalog (exact skillName and correct skillID).
    - Tie each reason to concrete needs implied by the case text.
    - If two skills are redundant, pick the one that best covers the need.

    --- ALLOWED SKILLS (ID | Name) ---
    {catalog}

    --- CASE PROJECT PDF TEXT START ---
    {pdf_text}
    --- CASE PROJECT PDF TEXT END ---
    """).strip()

def parse_top5_json(raw: str) -> List[dict]:
    raw = raw.strip()
    first = raw.find("{")
    last = raw.rfind("}")
    if 0 <= first <= last:
        raw = raw[first:last+1]
    data = json.loads(raw)
    if not isinstance(data, dict) or "top5" not in data or not isinstance(data["top5"], list):
        raise ValueError("Unexpected JSON shape; expected object with 'top5' list.")
    out = []
    for entry in data["top5"][:5]:
        out.append({
            "skillID": int(entry["skillID"]),
            "skillName": str(entry["skillName"]).strip(),
            "reason": str(entry.get("reason", "")).strip(),
        })
    return out


# =========================
# AI calls (same interfaces)
# =========================
def call_openai(prompt_text: str) -> str:
    """
    Uses OpenAI LEGACY SDK (openai==0.28.1) with ChatCompletion.
    """
    import openai  # legacy SDK
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    openai.api_key = api_key

    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")  # pick one you have

    resp = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are concise, accurate, and structured. Respond in strict JSON only."},
            {"role": "user", "content": prompt_text},
        ],
        temperature=0.2,
    )
    return resp["choices"][0]["message"]["content"].strip()

def call_anthropic(prompt_text: str) -> str:
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=1200,
        temperature=0.2,
        system="You are concise, accurate, and structured. Respond in strict JSON only.",
        messages=[{"role": "user", "content": prompt_text}],
    )
    out = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            out.append(block.text)
    return "\n".join(out).strip()

def call_gemini(prompt_text: str) -> str:
    import google.generativeai as genai
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")
    model = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-1.5-pro")
    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(model)
    resp = gen_model.generate_content(prompt_text)
    return (getattr(resp, "text", "") or "").strip()


# =========================
# Recommendation + persistence
# =========================
def _weights_for_top5(top5: List[dict]) -> Dict[int, int]:
    """
    Assigns descending weights 5..1 by rank position of the AI's top5.
    """
    w = {}
    for i, row in enumerate(top5):
        sid = int(row["skillID"])
        w[sid] = 5 - i if i < 5 else 1
    return w

def _employee_skill_profile(conn) -> Dict[int, Dict[int, int]]:
    """
    Returns {empID: {skillID: prof_level}}
    """
    prof: Dict[int, Dict[int, int]] = {}
    for r in conn.execute("SELECT empID, skillID, profiencylevel FROM EmployeeSkills"):
        prof.setdefault(r["empID"], {})[r["skillID"]] = r["profiencylevel"] or 0
    return prof

def _employee_meta(conn) -> Dict[int, dict]:
    """
    Returns basic metadata to display.
    """
    meta = {}
    for r in conn.execute("""
        SELECT e.empID, e.firstname, e.lastname, e.title, e.email, t.teamName, d.departmentname
        FROM Employees e
        JOIN Teams t ON e.teamID = t.teamID
        JOIN Departments d ON e.department = d.depID
    """):
        meta[r["empID"]] = dict(
            empID=r["empID"],
            name=f'{r["firstname"] or ""} {r["lastname"]}'.strip(),
            title=r["title"] or "",
            email=r["email"],
            team=r["teamName"],
            department=r["departmentname"],
        )
    return meta

# ===== Workload helpers =====
def _active_assignment_counts(conn) -> Dict[int, int]:
    """
    Returns {empID: active_assignment_count} where "active" means:
      - Project.status in ACTIVE_STATUSES
      - AND (endDate IS NULL OR endDate >= today)
    """
    if not ACTIVE_STATUSES:
        return {}
    q = """
        SELECT pa.empID, COUNT(*) AS c
        FROM ProjectAssignment pa
        JOIN Projects p ON p.projectID = pa.projectID
        WHERE p.status IN ({placeholders})
          AND (p.endDate IS NULL OR DATE(p.endDate) >= DATE('now'))
        GROUP BY pa.empID
    """.format(placeholders=",".join("?" * len(ACTIVE_STATUSES)))
    rows = conn.execute(q, tuple(ACTIVE_STATUSES)).fetchall()
    return {r["empID"]: r["c"] for r in rows}

def _is_overallocated(active_counts: Dict[int,int], emp_id: int) -> bool:
    return active_counts.get(emp_id, 0) >= MAX_ACTIVE_ASSIGNMENTS

def _validate_team_allocation(conn, team_emp_ids: Iterable[int]) -> None:
    """
    Raises if any selected employee already meets or exceeds MAX_ACTIVE_ASSIGNMENTS on active projects.
    """
    active_counts = _active_assignment_counts(conn)
    over = [eid for eid in team_emp_ids if _is_overallocated(active_counts, eid)]
    if over:
        raise RuntimeError(
            "One or more selected employees are already at the max active assignments: "
            + ", ".join(str(e) for e in over)
        )

def score_employees_for_skills(db_path: str, top5: List[dict]) -> List[Tuple[int, float]]:
    """
    Scores each employee against the required skills AND accounts for workload.
    Base Score = sum over required skills of (weight_by_rank * prof_level).
    Availability Penalty = PENALTY_PER_ACTIVE * active_assignment_count.
    Final Score = max(0, Base - Availability Penalty).
    """
    conn = _conn(db_path)
    try:
        weights = _weights_for_top5(top5)  # skillID -> 5..1
        profiles = _employee_skill_profile(conn)
        active_counts = _active_assignment_counts(conn)

        scores: List[Tuple[int, float]] = []
        for emp_id, skill_map in profiles.items():
            base = 0.0
            for sid, w in weights.items():
                base += w * skill_map.get(sid, 0)

            penalty = PENALTY_PER_ACTIVE * active_counts.get(emp_id, 0)
            final = base - penalty
            if final < 0:
                final = 0.0

            scores.append((emp_id, final))

        # sort by score desc, tie-breaker by empID asc
        scores.sort(key=lambda x: (-x[1], x[0]))
        return scores
    finally:
        conn.close()

def suggest_team(db_path: str, top5: List[dict], k: int = 4, exclude: Set[int] = None) -> List[int]:
    """
    Returns up to k employee IDs as a suggested team, excluding any in `exclude`.
    Skips employees who already meet/exceed MAX_ACTIVE_ASSIGNMENTS on active projects.
    """
    exclude = exclude or set()
    conn = _conn(db_path)
    try:
        active_counts = _active_assignment_counts(conn)
    finally:
        conn.close()

    ranked = score_employees_for_skills(db_path, top5)
    picked: List[int] = []
    for emp_id, _score in ranked:
        if emp_id in exclude:
            continue
        if _is_overallocated(active_counts, emp_id):
            continue
        picked.append(emp_id)
        if len(picked) >= k:
            break
    return picked

def print_team_preview(db_path: str, emp_ids: Iterable[int]) -> None:
    conn = _conn(db_path)
    try:
        meta = _employee_meta(conn)
        skill_names = {r["skillID"]: r["skillName"] for r in conn.execute("SELECT skillID, skillName FROM Skills")}
        active_counts = _active_assignment_counts(conn)

        print("\n=== Suggested Team ===")
        for i, eid in enumerate(emp_ids, 1):
            m = meta.get(eid)
            if not m:
                continue
            active = active_counts.get(eid, 0)
            print(f"{i}. {m['name']} — {m['title']} | {m['team']} ({m['department']}) | {m['email']} | Active assignments: {active}")
            skills = conn.execute("""
                SELECT es.skillID, es.profiencylevel
                FROM EmployeeSkills es
                WHERE es.empID=?
                ORDER BY es.profiencylevel DESC
                LIMIT 5
            """, (eid,)).fetchall()
            if skills:
                readable = ", ".join(f"{skill_names[s['skillID']]} (lvl {s['profiencylevel']})" for s in skills)
                print(f"   Skills: {readable}")
    finally:
        conn.close()

def _ensure_project(conn, project_name: str, team_id: int) -> int:
    existing = conn.execute("SELECT projectID FROM Projects WHERE projectName=?", (project_name,)).fetchone()
    if existing:
        return existing["projectID"]
    cur = conn.execute("""
        INSERT INTO Projects(teamID, projectName, status)
        VALUES (?, ?, 'Not Started')
    """, (team_id, project_name))
    return cur.lastrowid

def persist_project_with_team(db_path: str, project_name: str, team_emp_ids: List[int], top5: List[dict]) -> int:
    """
    Creates/ensures a Project, writes ProjectSkills and ProjectAssignment.
    Uses the first employee's team as the owning team (simple default).
    Validates that no employee exceeds MAX_ACTIVE_ASSIGNMENTS on active projects.
    """
    if not team_emp_ids:
        raise RuntimeError("No employees provided to save into project.")

    conn = _conn(db_path)
    try:
        # Allocation guard
        _validate_team_allocation(conn, team_emp_ids)

        # Find owning team from first employee
        first = conn.execute("SELECT teamID FROM Employees WHERE empID=?", (team_emp_ids[0],)).fetchone()
        if not first:
            raise RuntimeError("Could not find team for first employee.")
        team_id = first["teamID"]

        project_id = _ensure_project(conn, project_name, team_id)

        # ProjectSkills from Top5 (default numpeopleneeded=1; complexity from rank)
        rank_complexity = ["Critical", "High", "Medium", "Medium", "Low"]
        for i, s in enumerate(top5[:5]):
            sid = int(s["skillID"])
            conn.execute("""
                INSERT OR REPLACE INTO ProjectSkills(projectID, skillID, numpeopleneeded, complexitylevel)
                VALUES (?, ?, ?, ?)
            """, (project_id, sid, 1, rank_complexity[i] if i < len(rank_complexity) else "Low"))

        # Assign employees (role = "Contributor" with #1 as "Lead")
        for j, eid in enumerate(team_emp_ids):
            role = "Lead" if j == 0 else "Contributor"
            conn.execute("""
                INSERT OR REPLACE INTO ProjectAssignment(projectID, empID, role)
                VALUES (?, ?, ?)
            """, (project_id, eid, role))

        conn.commit()
        print(f"💾 Saved project '{project_name}' with {len(team_emp_ids)} assignments (projectID={project_id}).")
        return project_id
    finally:
        conn.close()


# =========================
# Main
# =========================
def main():
    print("\n=== AI PDF → Top 5 Skills (Constrained to Skills table, workload-aware) ===")

    # 1) Create all tables if they don't exist
    init_db(DB_PATH)

    # 2) Seed Skills if empty + seed org/people if empty
    seed_skills_if_empty(DB_PATH)
    seed_org_if_empty(DB_PATH)

    # 3) Pick PDF and extract
    try:
        pdf_path = choose_pdf_file()
    except Exception as e:
        print("File selection error:", e)
        sys.exit(1)

    print("Extracting text...")
    pdf_text = extract_text_from_pdf(pdf_path)
    if not pdf_text:
        print("Warning: PDF extraction returned empty content.")

    # 4) Load allowed skills (must exist)
    skills = load_allowed_skills(DB_PATH)
    if not skills:
        print("Error: No skills found in the database. Add rows to Skills and try again.")
        sys.exit(1)

    # 5) Build constrained prompt
    prompt = build_constrained_prompt(clamp_text(pdf_text), skills)

    # 6) Provider choice
    print("\nChoose AI provider:")
    print("1) OpenAI (legacy ChatCompletion)")
    print("2) Anthropic (Claude)")
    print("3) Google (Gemini)")
    choice = input("> ").strip()

    print("\nGetting response from AI...\n")
    try:
        if choice == "1":
            result = call_openai(prompt)
        elif choice == "2":
            result = call_anthropic(prompt)
        elif choice == "3":
            result = call_gemini(prompt)
        else:
            print("Invalid choice."); return

        print("=== Parsed Top 5 ===")
        try:
            parsed = parse_top5_json(result)
            for i, row in enumerate(parsed, 1):
                print(f"{i}. [{row['skillID']}] {row['skillName']} — {row['reason']}")
        except Exception as pe:
            print("(Could not parse JSON; showing raw output)")
            print(result or "[No content returned]")
            print("Parse error:", pe)
            return

        # 7) Recommend team of 4 from employee skills (workload-aware)
        rejected: Set[int] = set()
        attempt = 1
        while True:
            team = suggest_team(DB_PATH, parsed, k=4, exclude=rejected)
            if not team:
                print("No more candidate teams available based on current constraints.")
                break

            print_team_preview(DB_PATH, team)
            ans = input("\nAccept this team? (y/n): ").strip().lower()
            if ans == "y":
                # 8) Persist project with team (with overallocation validation)
                default_name = os.path.splitext(os.path.basename(pdf_path))[0]
                proj_name = input(f"Enter a project name [{default_name}]: ").strip() or default_name
                persist_project_with_team(DB_PATH, proj_name, team, parsed)
                print("✅ Done.")
                break
            else:
                print("Okay — generating a new set (excluding the previous suggestion).")
                rejected.update(team)
                attempt += 1

    except Exception as e:
        print("Error:", e)

# ===== Simple cleanup helper PLEASE REMOVE THIS AFTER WE GET REAL DATA SO WE CAN SAVE PROJECTS=====
def delete_project_data(db_path: str = DB_PATH):
    conn = _conn(db_path)
    try:
        conn.execute("DELETE FROM ProjectAssignment")
        conn.execute("DELETE FROM ProjectSkills")
        conn.execute("DELETE FROM Projects")
        conn.commit()
        print("🧹 All project-related data (Projects, Assignments, and ProjectSkills) has been deleted.")
    finally:
        conn.close()

if __name__ == "__main__":
    # Comment this out once you start saving real projects
    delete_project_data()
    main()
