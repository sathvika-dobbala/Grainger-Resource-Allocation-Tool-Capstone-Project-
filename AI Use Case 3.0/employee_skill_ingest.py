# employee_skill_ingest.py
import os
import sys
import json
import re
import sqlite3
import textwrap
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

from dotenv import load_dotenv

# Optional PDF support
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

load_dotenv()

DB_PATH = os.getenv("EMPLOYEE_DB_PATH", "employees.db")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
STRICT_JSON_NOTE = "Respond in strict JSON only. No code fences, no extra text."
EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)

# =========================
# Edit Skills Definitions (NEW)
# =========================
def _prompt_int(prompt: str, lo: int, hi: int, default: Optional[int] = None) -> int:
    while True:
        s = input(f"{prompt} [{lo}-{hi}" + (f", default {default}" if default is not None else "") + "]: ").strip()
        if not s and default is not None:
            return default
        if s.isdigit():
            v = int(s)
            if lo <= v <= hi:
                return v
        print(f"Enter an integer between {lo} and {hi}.")

def list_employee_skills_rows(conn, emp_id: int) -> List[sqlite3.Row]:
    return conn.execute("""
        SELECT s.skillID,
               s.skillName,
               COALESCE(es.profiencylevel, 0) AS lvl,
               COALESCE(es.evidence, '') AS evidence
          FROM Skills s
          LEFT JOIN EmployeeSkills es
                 ON es.skillID = s.skillID AND es.empID = ?
         ORDER BY s.skillName COLLATE NOCASE
    """, (emp_id,)).fetchall()

def print_employee_skill_table(conn, emp_id: int) -> None:
    rows = conn.execute("""
        SELECT s.skillID, s.skillName, es.profiencylevel AS lvl, es.evidence
          FROM EmployeeSkills es
          JOIN Skills s ON s.skillID = es.skillID
         WHERE es.empID=?
         ORDER BY lvl DESC, s.skillName
    """, (emp_id,)).fetchall()
    if not rows:
        print("   (no skills on record)")
        return
    print("\nCurrent skills on record:")
    for r in rows:
        ev = f" — {r['evidence']}" if r['evidence'] else ""
        print(f"   [{r['skillID']}] {r['skillName']} (lvl {int(r['lvl'])}){ev}")

def search_skills(conn, query: str) -> List[sqlite3.Row]:
    q = f"%{query.lower()}%"
    return conn.execute("""
        SELECT skillID, skillName
          FROM Skills
         WHERE LOWER(skillName) LIKE ?
         ORDER BY skillName COLLATE NOCASE
    """, (q,)).fetchall()

def skill_exists(conn, skill_id: int) -> bool:
    r = conn.execute("SELECT 1 FROM Skills WHERE skillID=?", (skill_id,)).fetchone()
    return bool(r)

def set_employee_skill_exact(
    conn,
    emp_id: int,
    skill_id: int,
    level: int,
    evidence: Optional[str],
    evidence_mode: str = "replace",  # "replace" | "append"
) -> None:
    """
    Manually set EXACT level (1..5) and evidence for an employee's skill.
    Unlike auto-ingest, this CAN downlevel.
    evidence_mode:
      - replace: overwrite evidence with provided text (can be empty)
      - append:  append provided text to existing evidence (dedupe-ish)
    """
    level = max(1, min(5, int(level)))

    exists = conn.execute("""
        SELECT profiencylevel, evidence
          FROM EmployeeSkills
         WHERE empID=? AND skillID=?
    """, (emp_id, skill_id)).fetchone()

    if exists:
        if evidence_mode == "append" and evidence:
            # Basic dedupe/append
            curr = exists["evidence"] or ""
            parts = [p.strip() for p in (curr.split(" | ") if curr else []) if p.strip()]
            if evidence not in parts:
                parts.append(evidence)
            new_ev = " | ".join(parts) if parts else None
            conn.execute("""
                UPDATE EmployeeSkills
                   SET profiencylevel=?,
                       evidence=?
                 WHERE empID=? AND skillID=?
            """, (level, new_ev, emp_id, skill_id))
        else:
            # replace (or no evidence provided)
            conn.execute("""
                UPDATE EmployeeSkills
                   SET profiencylevel=?,
                       evidence=COALESCE(?, '')
                 WHERE empID=? AND skillID=?
            """, (level, evidence, emp_id, skill_id))
    else:
        conn.execute("""
            INSERT INTO EmployeeSkills(empID, skillID, profiencylevel, evidence)
            VALUES(?,?,?,?)
        """, (emp_id, skill_id, level, evidence or None))
    conn.commit()

def manual_skill_editor(conn, emp_id: int) -> None:
    """
    Console loop:
      1) list current skills
      2) edit existing skill (by skillID)
      3) add new skill to employee (by skillID)
      4) search catalog by name (to find skillIDs)
      5) quit
    """
    print_employee_skill_table(conn, emp_id)
    while True:
        print("\nManual Skill Editor:")
        print("1) List employee skills")
        print("2) Edit existing skill (level/evidence)")
        print("3) Add new skill to employee (by skillID)")
        print("4) Search skills (by name)")
        print("5) Quit editor")
        choice = input("> ").strip()

        if choice == "1":
            print_employee_skill_table(conn, emp_id)

        elif choice == "2":
            sid_raw = input("Enter skillID to edit: ").strip()
            if not sid_raw.isdigit():
                print("Please enter a numeric skillID."); continue
            sid = int(sid_raw)
            if not skill_exists(conn, sid):
                print("That skillID is not in the Skills catalog."); continue

            # Show current state if any
            cur = conn.execute("""
                SELECT s.skillName, es.profiencylevel AS lvl, es.evidence
                  FROM Skills s
             LEFT JOIN EmployeeSkills es ON es.skillID=s.skillID AND es.empID=?
                 WHERE s.skillID=?;
            """, (emp_id, sid)).fetchone()
            name = cur["skillName"]
            curr_lvl = int(cur["lvl"]) if cur["lvl"] is not None else 0
            curr_ev  = cur["evidence"] or ""
            print(f"Editing [{sid}] {name} (current level={curr_lvl or '—'}, current evidence='{curr_ev}')")

            new_lvl = _prompt_int("New level", 1, 5, default=max(1, curr_lvl or 3))
            ev_mode = input("Evidence mode: (r)eplace or (a)ppend? [r/a]: ").strip().lower() or "r"
            ev_text = input("Enter evidence text (leave blank to keep current if replace): ").strip()
            mode = "append" if ev_mode == "a" else "replace"
            set_employee_skill_exact(conn, emp_id, sid, new_lvl, ev_text if ev_text or mode=="replace" else None, mode)
            print("✅ Saved.")
            print_employee_skill_table(conn, emp_id)

        elif choice == "3":
            sid_raw = input("Enter skillID to add: ").strip()
            if not sid_raw.isdigit():
                print("Please enter a numeric skillID."); continue
            sid = int(sid_raw)
            if not skill_exists(conn, sid):
                print("That skillID is not in the Skills catalog."); continue

            new_lvl = _prompt_int("Set level", 1, 5, default=3)
            ev_text = input("Enter evidence text (optional): ").strip()
            set_employee_skill_exact(conn, emp_id, sid, new_lvl, ev_text or None, "replace")
            print("✅ Added/updated.")
            print_employee_skill_table(conn, emp_id)

        elif choice == "4":
            q = input("Search skills by name (substring): ").strip()
            if not q:
                continue
            results = search_skills(conn, q)
            if not results:
                print("No matches.")
            else:
                print("\nCatalog matches:")
                for r in results:
                    print(f"  [{r['skillID']}] {r['skillName']}")

        elif choice == "5":
            print("Exiting editor.")
            break
        else:
            print("Pick 1–5.")

# =========================
# PDF utilities (robust picker + extraction)
# =========================
def choose_pdf_file() -> str:
    """
    Opens a GUI file dialog to pick a PDF in the foreground.
    Falls back to console input if GUI isn't available or is canceled.
    """
    print("Opening file dialog for resume PDF...")
    try:
        from tkinter import Tk, filedialog
        root = Tk()
        try:
            root.attributes("-topmost", True)  # bring to front
            root.withdraw()
            path = filedialog.askopenfilename(
                title="Select resume PDF",
                filetypes=[("PDF files", "*.pdf")]
            )
        finally:
            root.destroy()
        if path:
            return path
        else:
            print("No file selected in the dialog.")
    except Exception as e:
        print(f"(GUI picker failed: {e})")

    # Fallback: manual path or paste
    while True:
        path = input("Enter full path to a .pdf file (or press Enter to paste resume text instead): ").strip().strip('"')
        if not path:
            return ""  # caller will handle text-paste mode
        if os.path.isfile(path) and path.lower().endswith(".pdf"):
            return path
        print("That wasn't a valid .pdf path. Try again.")

def extract_text_from_pdf(path: str) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf not installed. Install it with: python -m pip install pypdf")
    reader = PdfReader(path)
    parts: List[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n\n".join(parts).strip()

def read_resume_text_with_picker() -> str:
    """
    Try GUI picker; if a PDF is chosen, extract text.
    If canceled or empty, allow text paste.
    """
    pdf_path = choose_pdf_file()
    if pdf_path:
        txt = extract_text_from_pdf(pdf_path)
        if txt:
            return txt
        print("⚠️ Couldn’t extract text from that PDF (likely scanned).")
    # Paste fallback
    print("\nPaste resume text below. End with an empty line:")
    lines = []
    while True:
        line = sys.stdin.readline()
        if not line or line.strip() == "":
            break
        lines.append(line.rstrip("\n"))
    return "\n".join(lines).strip()

# =========================
# SQLite helpers
# =========================
def _conn(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

@dataclass
class SkillRow:
    skillID: int
    skillName: str
    skillCategoryID: Optional[int]

def load_skills(conn) -> List[SkillRow]:
    rows = conn.execute("""
        SELECT skillID, skillName, skillCategoryID
        FROM Skills
        ORDER BY skillName COLLATE NOCASE
    """).fetchall()
    return [SkillRow(r["skillID"], r["skillName"], r["skillCategoryID"]) for r in rows]

def list_departments(conn) -> List[sqlite3.Row]:
    return conn.execute("SELECT depID, departmentname FROM Departments ORDER BY departmentname").fetchall()

def list_teams(conn) -> List[sqlite3.Row]:
    return conn.execute("""
        SELECT t.teamID, t.teamName, d.depID AS depID, d.departmentname
        FROM Teams t
        JOIN Departments d ON d.depID = t.department
        ORDER BY t.teamName
    """).fetchall()

def team_belongs_to_department(teams: List[sqlite3.Row], team_id: int, dep_id: int) -> bool:
    for t in teams:
        if t["teamID"] == team_id:
            return t["depID"] == dep_id
    return False

def find_employee_by_email(conn, email: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM Employees WHERE email = ?", (email,)).fetchone()

# =========================
# Validation helpers
# =========================
def normalize_phone(raw: str) -> str:
    return "".join(ch for ch in raw if ch.isdigit())

def valid_phone(digits: str) -> bool:
    return 10 <= len(digits) <= 15

def assert_required(label: str, value: str):
    if not value or not value.strip():
        raise RuntimeError(f"{label} is required.")

def assert_email(s: str):
    if not EMAIL_RE.match(s or ""):
        raise RuntimeError("Email appears invalid.")

def assert_unique_email_on_create(conn, email: str):
    if find_employee_by_email(conn, email):
        raise RuntimeError("An employee with this email already exists.")

def validate_employee_payload(conn, firstname: str, lastname: str, title: str,
                              dep_id: int, team_id: int, email: str, phone_raw: str,
                              is_create: bool):
    assert_required("First name", firstname)
    assert_required("Last name", lastname)
    assert_required("Title", title)
    assert_required("Email", email)
    assert_required("Phone", phone_raw)

    assert_email(email)
    if is_create:
        assert_unique_email_on_create(conn, email)

    phone_digits = normalize_phone(phone_raw)
    if not valid_phone(phone_digits):
        raise RuntimeError("Phone must contain 10–15 digits (numbers only).")

    # Department and Team existence + relationship
    deps = list_departments(conn)
    dep_ids = {d["depID"] for d in deps}
    if dep_id not in dep_ids:
        raise RuntimeError("Selected Department does not exist.")

    teams = list_teams(conn)
    team_ids = {t["teamID"] for t in teams}
    if team_id not in team_ids:
        raise RuntimeError("Selected Team does not exist.")
    if not team_belongs_to_department(teams, team_id, dep_id):
        raise RuntimeError("Selected Team does not belong to the chosen Department.")

    return firstname.strip(), lastname.strip(), title.strip(), dep_id, team_id, email.strip().lower(), phone_digits

def upsert_employee(conn, firstname: str, lastname: str, title: str,
                    dep_id: int, team_id: int, email: str, phone_digits: str,
                    is_create: bool) -> int:
    existing = find_employee_by_email(conn, email)
    if existing and is_create:
        raise RuntimeError("An employee with this email already exists.")

    if existing:
        conn.execute("""
            UPDATE Employees
               SET firstname=?, lastname=?, title=?, department=?, teamID=?, phone=?
             WHERE empID=?
        """, (firstname, lastname, title, dep_id, team_id, phone_digits, existing["empID"]))
        conn.commit()
        print(f"✏️ Updated employee {firstname} {lastname} ({email}) [empID={existing['empID']}]")
        return existing["empID"]

    cur = conn.execute("""
        INSERT INTO Employees(firstname, lastname, title, department, teamID, email, phone)
        VALUES (?,?,?,?,?,?,?)
    """, (firstname, lastname, title, dep_id, team_id, email, phone_digits))
    conn.commit()
    emp_id = cur.lastrowid
    print(f"➕ Created employee {firstname} {lastname} ({email}) [empID={emp_id}]")
    return emp_id

def get_existing_skill_levels(conn, emp_id: int) -> Dict[int, int]:
    rows = conn.execute("""
        SELECT skillID, COALESCE(profiencylevel,0) AS lvl
        FROM EmployeeSkills WHERE empID=?
    """, (emp_id,)).fetchall()
    return {r["skillID"]: r["lvl"] for r in rows}

# =========================
# De-dup + upsert skills (with summary)
# =========================
def _dedupe_skill_updates(updates: List[Dict]) -> List[Dict]:
    """
    Combines multiple rows for the same skillID:
    - level: keep the MAX level
    - evidence: merge short phrases (deduped, comma-separated)
    Returns a list with unique skillID.
    """
    bucket: Dict[int, Dict] = {}
    for row in updates or []:
        try:
            sid = int(row["skillID"])
        except Exception:
            continue
        lvl = int(row.get("level", 0))
        lvl = 1 if lvl < 1 else (5 if lvl > 5 else lvl)
        evidence = (row.get("evidence") or "").strip()
        if sid not in bucket:
            bucket[sid] = {"skillID": sid, "level": lvl, "evidence_set": set()}
        bucket[sid]["level"] = max(bucket[sid]["level"], lvl)
        if evidence:
            bucket[sid]["evidence_set"].add(evidence)
    out: List[Dict] = []
    for sid, v in bucket.items():
        ev = ", ".join(sorted(v["evidence_set"])) if v["evidence_set"] else None
        out.append({"skillID": sid, "level": v["level"], "evidence": ev})
    return out

def upsert_employee_skills(conn, emp_id: int, updates: List[Dict]) -> Dict[str, int]:
    """
    Apply skill updates for an employee (auto-ingest / AI path).
    - De-duplicates by skillID (max level wins; merges evidence)
    - Never downgrades existing levels
    Returns: {"inserted": X, "updated": Y, "skipped": Z}
    """
    deduped = _dedupe_skill_updates(updates)
    existing = get_existing_skill_levels(conn, emp_id)

    inserted = updated = skipped = 0
    for row in deduped:
        sid = int(row["skillID"])
        lvl = int(row.get("level", 0))
        lvl = 1 if lvl < 1 else (5 if lvl > 5 else lvl)

        prev = int(existing.get(sid, 0))
        new_lvl = max(prev, lvl)  # never downgrade
        evidence = (row.get("evidence") or "").strip() or None

        if prev == 0:
            conn.execute("""
                INSERT INTO EmployeeSkills(empID, skillID, profiencylevel, evidence)
                VALUES(?,?,?,?)
            """, (emp_id, sid, new_lvl, evidence))
            inserted += 1
        else:
            if new_lvl > prev or evidence:
                conn.execute("""
                    UPDATE EmployeeSkills
                       SET profiencylevel=?,
                           evidence=COALESCE(?, evidence)
                     WHERE empID=? AND skillID=?
                """, (new_lvl, evidence, emp_id, sid))
                updated += 1
            else:
                skipped += 1

    conn.commit()
    return {"inserted": inserted, "updated": updated, "skipped": skipped}

def print_employee_skills(conn, emp_id: int):
    rows = conn.execute("""
        SELECT s.skillName, es.profiencylevel AS lvl, es.evidence
          FROM EmployeeSkills es
          JOIN Skills s ON s.skillID = es.skillID
         WHERE es.empID=?
         ORDER BY lvl DESC, s.skillName
    """, (emp_id,)).fetchall()
    if not rows:
        print("   (no skills on record)")
        return
    for r in rows:
        ev = f" — {r['evidence']}" if r['evidence'] else ""
        print(f"   {r['skillName']} (lvl {r['lvl']}){ev}")

# =========================
# Delete helpers
# =========================
def _assignment_counts(conn, emp_id: int) -> dict:
    """
    Returns {"total": int, "active": int} for an employee's project assignments.
    'Active' = status in ('Not Started','In Progress') and endDate is null or future.
    """
    total = conn.execute("""
        SELECT COUNT(*) AS c
        FROM ProjectAssignment
        WHERE empID=?
    """, (emp_id,)).fetchone()["c"]

    active = conn.execute("""
        SELECT COUNT(*) AS c
        FROM ProjectAssignment pa
        JOIN Projects p ON p.projectID = pa.projectID
        WHERE pa.empID=?
          AND p.status IN ('Not Started','In Progress')
          AND (p.endDate IS NULL OR date(p.endDate) >= date('now'))
    """, (emp_id,)).fetchone()["c"]

    return {"total": total, "active": active}

def delete_employee(conn, email: str, force: bool=False) -> None:
    """
    Deletes an employee by email.
    - Safe mode: refuses if they have any project assignments.
    - Force mode: removes their ProjectAssignment rows first, then deletes the employee.
      (EmployeeSkills rows are removed via ON DELETE CASCADE.)
    """
    row = find_employee_by_email(conn, email)
    if not row:
        raise RuntimeError("Employee not found.")

    emp_id = row["empID"]
    counts = _assignment_counts(conn, emp_id)

    if counts["total"] > 0 and not force:
        raise RuntimeError(
            f"Cannot delete: employee has {counts['total']} project assignment(s) "
            f"({counts['active']} active). Use force delete to remove assignments first."
        )

    if force and counts["total"] > 0:
        conn.execute("DELETE FROM ProjectAssignment WHERE empID=?", (emp_id,))
        conn.commit()

    conn.execute("DELETE FROM Employees WHERE empID=?", (emp_id,))
    conn.commit()
    print(f"🗑️ Deleted employee {row['firstname']} {row['lastname']} ({email}) [empID={emp_id}]")

# =========================
# OpenAI (legacy)
# =========================
def call_openai_json(prompt_text: str) -> str:
    import openai
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set.")
    openai.api_key = api_key

    resp = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": f"You are precise and structured. {STRICT_JSON_NOTE}"},
            {"role": "user", "content": prompt_text},
        ],
        temperature=0.1,
    )
    return resp["choices"][0]["message"]["content"].strip()

def clamp(s: str, max_chars=100_000) -> str:
    return s if len(s) <= max_chars else (s[:max_chars] + "\n[TRUNCATED]")

# =========================
# Prompts + parsing
# =========================
def build_resume_prompt(resume_text: str, allowed_skills: List[SkillRow]) -> str:
    catalog = "\n".join(f"{s.skillID} | {s.skillName}" for s in allowed_skills)
    return textwrap.dedent(f"""
    You will extract skills from a candidate resume and map them ONLY to the allowed skills catalog (ID|Name).
    Output strict JSON with this schema:
    {{
      "skills": [
        {{"skillID": <int>, "skillName": "<exact from catalog>", "level": <int 1-5>, "evidence": "<short phrase>"}}
      ]
    }}

    Rules:
    - Use ONLY skills that appear in the catalog (exact names, correct IDs).
    - Choose a realistic level 1-5 based on resume evidence (1=basic, 5=expert).
    - Avoid duplicates; if evidence implies same skill multiple times, keep one with the strongest level.
    - Keep "evidence" short (few words) referencing resume content (e.g., "3 yrs Python at ACME").

    --- ALLOWED SKILLS (ID | Name) ---
    {catalog}

    --- RESUME TEXT START ---
    {clamp(resume_text, 60_000)}
    --- RESUME TEXT END ---
    """).strip()

def build_certs_prompt(certs_text: str, allowed_skills: List[SkillRow]) -> str:
    catalog = "\n".join(f"{s.skillID} | {s.skillName}" for s in allowed_skills)
    return textwrap.dedent(f"""
    You will analyze provided certifications/badges and map them to the allowed skill catalog (ID|Name).
    Certifications may add NEW relevant skills or BOOST levels of existing skills.
    Output strict JSON with this schema:
    {{
      "skills": [
        {{"skillID": <int>, "skillName": "<exact from catalog>", "level": <int 1-5>, "evidence": "<short phrase like 'AWS CCP'>"}}
      ]
    }}

    Rules:
    - Map ONLY to skills in the catalog (exact name, correct ID).
    - If a certification implies deeper proficiency, choose a higher level (up to 5).
    - Keep "evidence" short and tied to the certification.

    --- ALLOWED SKILLS (ID | Name) ---
    {catalog}

    --- CERTIFICATIONS TEXT START ---
    {clamp(certs_text, 8_000)}
    --- CERTIFICATIONS TEXT END ---
    """).strip()

def parse_skills_json(raw: str) -> List[Dict]:
    raw = raw.strip()
    first = raw.find("{"); last = raw.rfind("}")
    if 0 <= first <= last:
        raw = raw[first:last+1]
    data = json.loads(raw)
    if not isinstance(data, dict) or "skills" not in data or not isinstance(data["skills"], list):
        raise ValueError("Unexpected JSON; expected object with 'skills' list.")
    out = []
    for item in data["skills"]:
        out.append({
            "skillID": int(item["skillID"]),
            "skillName": str(item["skillName"]).strip(),
            "level": int(item.get("level", 0)),
            "evidence": str(item.get("evidence", "")).strip()
        })
    return out

# =========================
# UI helpers
# =========================
def prompt_mode() -> str:
    print("\nChoose mode:")
    print("1) Add NEW employee")
    print("2) EDIT existing employee")
    print("3) DELETE employee")
    while True:
        c = input("> ").strip()
        if c in ("1","2","3"):
            return c

def prompt_new_employee(conn) -> Tuple[str,str,str,int,int,str,str]:
    print("\nEnter basic info for the new employee (required fields *):")
    firstname = input("First name *: ").strip()
    lastname  = input("Last name *: ").strip()
    title     = input("Title (e.g., Data Analyst) *: ").strip()
    email     = input("Email * (unique): ").strip()
    phone     = input("Phone * (digits or formatted): ").strip()

    deps = list_departments(conn)
    if not deps:
        raise RuntimeError("No Departments found. Seed your DB first.")
    print("\nPick Department:")
    for i,d in enumerate(deps,1):
        print(f"{i}) {d['departmentname']} (depID={d['depID']})")
    dep_idx = int(input("> ").strip())
    dep_id = deps[dep_idx-1]["depID"]

    teams = list_teams(conn)
    if not teams:
        raise RuntimeError("No Teams found. Seed your DB first.")
    print("\nPick Team:")
    for i,t in enumerate(teams,1):
        print(f"{i}) {t['teamName']} — {t['departmentname']} (teamID={t['teamID']})")
    team_idx = int(input("> ").strip())
    team_id = teams[team_idx-1]["teamID"]

    return firstname, lastname, title, dep_id, team_id, email, phone

def prompt_existing_employee_email() -> str:
    email = input("\nEnter the employee's email: ").strip()
    if not email:
        raise RuntimeError("Email required.")
    return email

# =========================
# Main flows
# =========================
def handle_add_new(conn):
    # Validate and create
    firstname, lastname, title, dep_id, team_id, email, phone_raw = prompt_new_employee(conn)
    firstname, lastname, title, dep_id, team_id, email, phone_digits = validate_employee_payload(
        conn, firstname, lastname, title, dep_id, team_id, email, phone_raw, is_create=True
    )
    emp_id = upsert_employee(conn, firstname, lastname, title, dep_id, team_id, email, phone_digits, is_create=True)

    # Always open a file dialog (with fallback) for the resume
    print("\nResume is REQUIRED for new employees.")
    resume_text = read_resume_text_with_picker()
    if not resume_text:
        raise RuntimeError("No resume content provided.")

    allowed = load_skills(conn)
    if not allowed:
        raise RuntimeError("Skills table is empty. Seed it first.")

    prompt = build_resume_prompt(resume_text, allowed)
    print("\nAnalyzing resume with ChatGPT...")
    raw = call_openai_json(prompt)
    parsed = parse_skills_json(raw)
    summary = upsert_employee_skills(conn, emp_id, parsed)
    print(f"✅ Skills applied for empID={emp_id} — inserted: {summary['inserted']}, "
          f"updated: {summary['updated']}, skipped: {summary['skipped']}")
    print_employee_skill_table(conn, emp_id)

    # Optional certifications
    ans = input("\nAdd certifications now? (y/n): ").strip().lower()
    if ans == "y":
        print("\nType certifications, licenses, or badges (free text). End with an empty line:")
        lines = []
        while True:
            line = sys.stdin.readline()
            if not line or line.strip() == "":
                break
            lines.append(line.rstrip("\n"))
        cert_txt = "\n".join(lines).strip()
        if cert_txt:
            cprompt = build_certs_prompt(cert_txt, allowed)
            print("\nAnalyzing certifications with ChatGPT...")
            craw = call_openai_json(cprompt)
            cparsed = parse_skills_json(craw)
            csummary = upsert_employee_skills(conn, emp_id, cparsed)
            print(f"🏅 Cert updates for empID={emp_id} — inserted: {csummary['inserted']}, "
                  f"updated: {csummary['updated']}, skipped: {csummary['skipped']}")
            print_employee_skill_table(conn, emp_id)

def handle_edit_existing(conn):
    email = prompt_existing_employee_email()
    row = find_employee_by_email(conn, email)
    if not row:
        raise RuntimeError("Employee not found. Check the email and try again.")
    emp_id = row["empID"]
    print(f"Editing employee: {row['firstname']} {row['lastname']} (empID={emp_id})")

    # Optional: update core fields
    if input("Update basic info (name/title/department/team/phone)? (y/n): ").strip().lower() == "y":
        def prompt_prefill(label, current):
            v = input(f"{label} [{current}]: ").strip()
            return v if v else current

        firstname = prompt_prefill("First name", row["firstname"] or "")
        lastname  = prompt_prefill("Last name", row["lastname"] or "")
        title     = prompt_prefill("Title", row["title"] or "")

        deps = list_departments(conn)
        print("\nPick Department:")
        dep_id_current = int(row["department"])
        for i,d in enumerate(deps,1):
            cur = " (current)" if d["depID"] == dep_id_current else ""
            print(f"{i}) {d['departmentname']} (depID={d['depID']}){cur}")
        dep_idx = int(input("> ").strip())
        dep_id = deps[dep_idx-1]["depID"]

        teams = list_teams(conn)
        print("\nPick Team:")
        team_id_current = int(row["teamID"]) if row["teamID"] is not None else None
        for i,t in enumerate(teams,1):
            cur = " (current)" if t["teamID"] == team_id_current else ""
            print(f"{i}) {t['teamName']} — {t['departmentname']} (teamID={t['teamID']}){cur}")
        team_idx = int(input("> ").strip())
        team_id = teams[team_idx-1]["teamID"]

        phone_raw = prompt_prefill("Phone", row["phone"] or "")

        firstname, lastname, title, dep_id, team_id, email_norm, phone_digits = validate_employee_payload(
            conn, firstname, lastname, title, dep_id, team_id, email, phone_raw, is_create=False
        )
        upsert_employee(conn, firstname, lastname, title, dep_id, team_id, email_norm, phone_digits, is_create=False)
    else:
        print("Skipping core info update.")

    # Optional resume on edit (via picker + fallback)
    if input("Provide a resume to analyze? (y/n): ").strip().lower() == "y":
        resume_text = read_resume_text_with_picker()
        if not resume_text:
            print("No resume content; skipping.")
        else:
            allowed = load_skills(conn)
            if not allowed:
                raise RuntimeError("Skills table is empty. Seed it first.")
            prompt = build_resume_prompt(resume_text, allowed)
            print("\nAnalyzing resume with ChatGPT...")
            raw = call_openai_json(prompt)
            parsed = parse_skills_json(raw)
            summary = upsert_employee_skills(conn, emp_id, parsed)
            print(f"✅ Skills applied for empID={emp_id} — inserted: {summary['inserted']}, "
                  f"updated: {summary['updated']}, skipped: {summary['skipped']}")
            print_employee_skill_table(conn, emp_id)
    else:
        print("Skipping resume analysis.")

    # Optional certifications
    ans = input("\nAdd certifications now? (y/n): ").strip().lower()
    if ans == "y":
        print("\nType certifications, licenses, or badges (free text). End with an empty line:")
        lines = []
        while True:
            line = sys.stdin.readline()
            if not line or line.strip() == "":
                break
            lines.append(line.rstrip("\n"))
        cert_txt = "\n".join(lines).strip()
        if cert_txt:
            allowed = load_skills(conn)
            cprompt = build_certs_prompt(cert_txt, allowed)
            print("\nAnalyzing certifications with ChatGPT...")
            craw = call_openai_json(cprompt)
            cparsed = parse_skills_json(craw)
            csummary = upsert_employee_skills(conn, emp_id, cparsed)
            print(f"🏅 Cert updates for empID={emp_id} — inserted: {csummary['inserted']}, "
                  f"updated: {csummary['updated']}, skipped: {csummary['skipped']}")
            print_employee_skill_table(conn, emp_id)

    # ---- NEW: Manual skill editor ----
    if input("\nOpen manual skill editor now? (y/n): ").strip().lower() == "y":
        manual_skill_editor(conn, emp_id)

# =========================
# Delete flow
# =========================
def handle_delete(conn):
    email = prompt_existing_employee_email()
    row = find_employee_by_email(conn, email)
    if not row:
        raise RuntimeError("Employee not found.")

    emp_id = row["empID"]
    counts = _assignment_counts(conn, emp_id)
    print(f"\nAbout to delete: {row['firstname']} {row['lastname']} ({email}) [empID={emp_id}]")
    print(f"Assignments: total={counts['total']}, active={counts['active']}")

    if counts["total"] > 0:
        ans = input("They have project assignments. Force delete (remove assignments first)? (y/n): ").strip().lower()
        if ans != "y":
            print("Aborted.")
            return
        confirm = input("Type DELETE to confirm force delete: ").strip()
        if confirm != "DELETE":
            print("Aborted.")
            return
        delete_employee(conn, email, force=True)
    else:
        confirm = input("Type DELETE to confirm: ").strip()
        if confirm != "DELETE":
            print("Aborted.")
            return
        delete_employee(conn, email, force=False)

# =========================
# Main
# =========================
def main():
    print("\n=== Employee Skill Ingest (Resume/Certs → Skills) — with picker, dedupe, summaries, delete ===")
    conn = _conn(DB_PATH)
    try:
        mode = prompt_mode()
        if mode == "1":
            handle_add_new(conn)
        elif mode == "2":
            handle_edit_existing(conn)
        else:
            handle_delete(conn)
        print("\nDone.")
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
