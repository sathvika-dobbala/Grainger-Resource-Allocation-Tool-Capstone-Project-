# ai_helper.py
import os
import json
import sqlite3
from typing import List, Dict, Optional
from dotenv import load_dotenv
from flask import session

load_dotenv()

# -----------------------------
# Import existing AI functions from your previous module
# -----------------------------
import importlib.util
ai_pdf_path = os.path.join(os.path.dirname(__file__), 'AI Use Case 3.0', 'ai_pdf_app.py')
spec = importlib.util.spec_from_file_location("ai_pdf_app", ai_pdf_path)
ai_pdf_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_pdf_app)

_conn = ai_pdf_app._conn
call_anthropic = ai_pdf_app.call_anthropic
call_gemini = ai_pdf_app.call_gemini

DB_PATH = os.getenv("EMPLOYEE_DB_PATH", "employees.db")

# ==============================================================
# ✅ OpenAI API wrapper
# ==============================================================
def call_openai(prompt_text: str) -> str:
    """Call OpenAI (v1.x) and return strict JSON string."""
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Respond in strict JSON only. No commentary."},
            {"role": "user", "content": prompt_text}
        ],
        temperature=0.2
    )
    return resp.choices[0].message.content.strip()

# ==============================================================
# ✅ Skill Extraction (department scoped)
# ==============================================================
def _build_skill_extraction_prompt(prd_text: str, dept_skills: Dict[str, int]) -> str:
    skill_list = "\n".join([f"- {name} (ID={sid})" for name, sid in dept_skills.items()])
    return f"""
You are an assistant extracting required skills from a project PRD.
Use ONLY the following department-specific skills:

{skill_list}

PRD (truncated to 6000 characters):
\"\"\"{prd_text[:6000]}\"\"\"

Return ONLY strict JSON:
{{
  "skills": [
    {{"skillID": 1, "skillName": "Python", "reason": "Used for backend logic"}},
    {{"skillID": 2, "skillName": "Docker", "reason": "For containerized deployments"}}
  ]
}}

Rules:
- Pick 5–10 relevant skills.
- Only use skillIDs listed above.
- Reasons must be concise (1 sentence).
- Output strictly valid JSON (no commentary).
"""

def extract_skills_from_text(prd_text: str, conn, department_id: int) -> List[Dict]:
    """Extract skills only from the manager's department skill set."""
    cur = conn.execute(
        "SELECT skillID, skillName FROM Skills WHERE skillCategoryID = ? ORDER BY skillName",
        (department_id,)
    )
    dept_skills = {row["skillName"]: row["skillID"] for row in cur.fetchall()}
    if not dept_skills:
        raise RuntimeError("No skills found for this department.")
    prompt = _build_skill_extraction_prompt(prd_text, dept_skills)
    raw = call_openai(prompt)
    if raw.startswith("```"):
        raw = "\n".join([l for l in raw.splitlines() if not l.strip().startswith("```")])
    data = json.loads(raw)
    out = []
    for it in data.get("skills", []):
        out.append({
            "skillID": int(it["skillID"]),
            "skillName": str(it["skillName"]).strip(),
            "reason": str(it.get("reason", "")).strip()
        })
    seen = set()
    dedup = []
    for s in out:
        if s["skillID"] not in seen:
            seen.add(s["skillID"])
            dedup.append(s)
    return dedup[:10]

# ==============================================================
# ✅ Team Recommendation (department scoped)
# ==============================================================
def get_ai_team_recommendations(skills_needed: List[str], department_id: int, k: int = 5) -> Dict:
    """
    Recommend employees from the same department that best match provided skills.
    Uses weighted scoring: coverage (60%) + avg proficiency (40%).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # 1️⃣ Retrieve department skills
        skill_rows = conn.execute(
            "SELECT skillID, skillName FROM Skills WHERE skillCategoryID = ?",
            (department_id,)
        ).fetchall()
        skill_map = {r["skillName"]: r["skillID"] for r in skill_rows}
        if not skill_map:
            raise RuntimeError("No skills found for this department.")

        # 2️⃣ Ask AI for the top 5 most critical skills
        skill_list = "\n".join([f"- {n} (ID={sid})" for n, sid in skill_map.items()])
        skill_text = ", ".join(skills_needed)
        prompt = f"""
You are assisting in team planning. Given the required skills for a project:
{skill_text}

From this department's skill catalog:
{skill_list}

Select the 5 most critical skills and explain briefly why.

Return JSON only:
{{
  "top5": [
    {{"skillID": 1, "skillName": "Python", "reason": "Core backend logic"}},
    {{"skillID": 2, "skillName": "SQL", "reason": "Database access"}}
  ]
}}
"""
        raw = call_openai(prompt)
        if raw.startswith("```"):
            raw = "\n".join([l for l in raw.splitlines() if not l.strip().startswith("```")])
        parsed = json.loads(raw)
        top5 = parsed.get("top5", [])
        top_ids = [s["skillID"] for s in top5]

        # 3️⃣ Get employees from this department
        employees = conn.execute("""
            SELECT empID, firstname, lastname, title, email
            FROM Employees
            WHERE department = ?
        """, (department_id,)).fetchall()

        candidates = []
        for emp in employees:
            skill_rows = conn.execute("""
                SELECT s.skillID, s.skillName, es.profiencylevel
                FROM EmployeeSkills es
                JOIN Skills s ON es.skillID = s.skillID
                WHERE es.empID = ?
            """, (emp["empID"],)).fetchall()

            # Calculate match
            matching = [s for s in skill_rows if s["skillID"] in top_ids]
            coverage = len(matching) / len(top_ids) if top_ids else 0
            avg_prof = (
                sum(s["profiencylevel"] for s in matching) / len(matching)
                if matching else 0
            )
            score = min(100, (coverage * 60) + ((avg_prof / 10) * 40))

            candidates.append({
                "id": emp["empID"],
                "name": f"{emp['firstname']} {emp['lastname']}",
                "title": emp["title"] or "N/A",
                "email": emp["email"],
                "matchScore": round(score, 1),
                "coveragePercent": round(coverage * 100, 1),
                "avgProficiency": round(avg_prof, 2),
                "skillsMatched": [s["skillName"] for s in matching]
            })

        # 4️⃣ Rank and return
        top_team = sorted(candidates, key=lambda x: x["matchScore"], reverse=True)[:k]
        return {
            "top5_skills": top5,
            "recommended_team": top_team,
            "department_id": department_id,
            "ai_provider": "openai"
        }
    finally:
        conn.close()

