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
        temperature=0.4
    )
    return resp.choices[0].message.content.strip()

# ==============================================================
# ✅ Skill Extraction (department scoped)
# ==============================================================
def _build_skill_extraction_prompt(prd_text: str, dept_skills: Dict[str, int]) -> str:
    skill_list = "\n".join([f"- {name} (ID={sid})" for name, sid in dept_skills.items()])
    return f"""
You are an assistant extracting required skills from a project PRD.

Your task:
- Read the PRD carefully.
- Choose the skills from the catalog below that best match the tools, technologies, and responsibilities described in the PRD.
- Only use skills that make sense for this specific project.

Department skill catalog (allowed skills only):
{skill_list}

Project requirements (PRD, truncated to 6000 characters):
\"\"\"{prd_text[:6000]}\"\"\"

Return ONLY strict JSON with this shape.

IMPORTANT:
- The JSON structure below is ONLY AN EXAMPLE OF THE FORMAT.
- Do NOT reuse the example skillIDs or skillNames.
- Your output must use real skillIDs and skillNames from the catalog above that fit the PRD.

{{
  "skills": [
    {{"skillID": <id-from-catalog>, "skillName": "<exact skillName from catalog>", "reason": "<1 short sentence explaining why it is needed>"}}
  ]
}}

Rules:
- Pick 5–10 relevant skills.
- Only use skillIDs and skillNames that appear in the catalog above.
- Match the skills to the PRD content. For example:
  - If the PRD focuses on UX, UI, Figma, prototyping, or research, prioritize design-related skills from the catalog.
  - If the PRD focuses on backend APIs or data pipelines, prioritize development-related skills from the catalog.
- Reasons must be concise (1 sentence).
- Output strictly valid JSON (no markdown, no commentary).
"""

def extract_skills_from_text(prd_text: str, conn, department_id: int) -> List[Dict]:
    """
    Extract skills from THIS manager's skill bank first.
    If the manager has no ManagerSkills, fall back to all skills for the department.
    """
    manager_id = session.get("manager_id")

    rows = []
    if manager_id:
        # 1) Try manager-specific skill bank (whatever categories they chose)
        cur = conn.execute("""
            SELECT s.skillID, s.skillName
            FROM Skills s
            JOIN ManagerSkills ms ON ms.skillID = s.skillID
            WHERE ms.managerID = ?
            ORDER BY s.skillName
        """, (manager_id,))
        rows = cur.fetchall()

    # 2) Fallback to department-wide skills if manager has no skills yet
    if not rows:
        cur = conn.execute(
            "SELECT skillID, skillName FROM Skills WHERE skillCategoryID = ? ORDER BY skillName",
            (department_id,)
        )
        rows = cur.fetchall()

    dept_skills = {row["skillName"]: row["skillID"] for row in rows}
    if not dept_skills:
        raise RuntimeError("No skills found for this manager or department.")

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

def assess_skill_proficiency(resume_text: str, skill_name: str, context: str) -> int:
    """
    Use AI to assess proficiency level (0-10) for a specific skill based on resume.
    
    Returns:
        int: Proficiency level from 0-10
    """
    prompt = f"""
You are analyzing a resume to assess proficiency level for a specific skill.

Skill to assess: {skill_name}
Context from resume: {context}

Resume excerpt (first 3000 chars):
\"\"\"{resume_text[:3000]}\"\"\"

Assess the proficiency level on a 0-10 scale:
- 0: No evidence
- 1-2: Novice/Beginner (mentioned, learning, courses)
- 3-4: Developing/Intermediate (some projects, 1-2 years experience)
- 5-6: Advanced/Proficient (multiple projects, 2-4 years, solid experience)
- 7-8: Highly Skilled/Expert (extensive experience, 4+ years, leadership)
- 9-10: Master/Guru (recognized expert, publications, teaching, 7+ years)

Consider:
- Years of experience with the skill
- Complexity of projects using the skill
- Leadership/mentoring in the skill
- Certifications or formal training
- Depth of description

Return ONLY a JSON object:
{{
  "level": <integer 0-10>,
  "reasoning": "<brief 1-sentence explanation>"
}}
"""
    
    try:
        raw = call_openai(prompt)
        if raw.startswith("```"):
            raw = "\n".join([l for l in raw.splitlines() if not l.strip().startswith("```")])
        data = json.loads(raw)
        level = int(data.get("level", 3))
        # Clamp to 0-10 range
        return max(0, min(10, level))
    except Exception as e:
        print(f"Error assessing proficiency for {skill_name}: {e}")
        # Fallback to middle value
        return 5

# ==============================================================
# ✅ Team Recommendation (department scoped)
# ==============================================================

def get_ai_team_recommendations(
    skills_needed: List[str],
    department_id: int,
    k: int = 5,
    priority: str = "Critical",
    manager_notes: Optional[str] = None
) -> Dict:
    """
    Recommend employees from the same department that best match provided skills.

    Priority behavior:
      - Critical: just take the best k people by matchScore.
      - High: ~75% highly qualified, ~25% lower-qualified.
      - Medium: ~50% highly qualified, ~50% lower-qualified.
      - Low: 1–2 highly qualified, rest lower-qualified.

    For the "lower-qualified" pool, we EXCLUDE people whose score is low
    mainly because they're already overloaded (activeProjectCount >= 3).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # 1️⃣ Build the skill catalog from the MANAGER'S skill bank first
        from flask import session
        manager_id = session.get("manager_id")

        if manager_id:
            skill_rows = conn.execute("""
                SELECT s.skillID, s.skillName
                FROM Skills s
                JOIN ManagerSkills ms ON ms.skillID = s.skillID
                WHERE ms.managerID = ?
                ORDER BY s.skillName
            """, (manager_id,)).fetchall()
        else:
            skill_rows = []

        # Fallback: if manager has no skill bank yet, use department skills
        if not skill_rows:
            skill_rows = conn.execute("""
                SELECT skillID, skillName
                FROM Skills
                WHERE skillCategoryID = ?
                ORDER BY skillName
            """, (department_id,)).fetchall()

        if not skill_rows:
            raise RuntimeError("No skills found for this manager/department.")

        # name -> id and id -> name maps
        skill_map = {r["skillName"]: r["skillID"] for r in skill_rows}
        skill_map_lower = {r["skillName"].strip().lower(): r["skillID"] for r in skill_rows}
        id_to_name = {r["skillID"]: r["skillName"] for r in skill_rows}

        # 2️⃣ Map PRD-selected skills directly to IDs (no extra AI step)
        selected_ids: List[int] = []
        for raw_name in skills_needed:
            if not raw_name:
                continue
            name = str(raw_name).strip()
            sid = skill_map.get(name)
            if not sid:
                sid = skill_map_lower.get(name.lower())
            if sid and sid not in selected_ids:
                selected_ids.append(sid)

        # If we couldn't map any PRD skills to catalog skills, return no recs
        if not selected_ids:
            return {
                "top5_skills": [],
                "recommended_team": [],
                "department_id": department_id,
                "ai_provider": "openai",
            }

        # Limit to at most 5 "core" skills (or keep all if you prefer)
        core_ids = selected_ids[:5]

        # Keep "top5_skills" shape similar to before
        top5 = [
            {"skillID": sid, "skillName": id_to_name.get(sid, "")}
            for sid in core_ids
        ]
        top_ids = core_ids  # used for scoring below

        # 3️⃣ Get employees from this department
        employees = conn.execute("""
            SELECT empID, firstname, lastname, title, email
            FROM Employees
            WHERE department = ?
        """, (department_id,)).fetchall()

        candidates = []
        for emp in employees:
            # All skills for this employee
            emp_skill_rows = conn.execute("""
                SELECT s.skillID, s.skillName, es.profiencylevel
                FROM EmployeeSkills es
                JOIN Skills s ON es.skillID = s.skillID
                WHERE es.empID = ?
            """, (emp["empID"],)).fetchall()

            # 📌 How many projects are they currently on?
            project_row = conn.execute("""
                SELECT COUNT(p.projectID) AS cnt
                FROM ProjectAssignment pa
                JOIN Projects p ON p.projectID = pa.projectID
                WHERE pa.empID = ?
            """, (emp["empID"],)).fetchone()
            active_projects = project_row["cnt"] if project_row else 0

            # -----------------------------------------
            # 🔢 Per-skill scoring against PRD skills
            # -----------------------------------------
            total_required = len(top_ids)  # all PRD-selected skills for this project

            skill_score_sum = 0.0
            matched_names: List[str] = []
            matched_profs: List[float] = []

            # For each required PRD skill, see if this employee has it
            for req_id in top_ids:
                match = next(
                    (s for s in emp_skill_rows if s["skillID"] == req_id),
                    None
                )
                if match:
                    prof = match["profiencylevel"] or 0
                    # proficiency 0–10 → normalize to 0–1 and add to total
                    skill_score_sum += (prof / 10.0)
                    matched_names.append(match["skillName"])
                    matched_profs.append(prof)
                else:
                    # missing skill adds 0 for this required skill
                    skill_score_sum += 0.0

            # Base score: average normalized proficiency across ALL required skills
            # (missing skills count as 0)
            if total_required > 0:
                base_score = round((skill_score_sum / total_required) * 100.0, 2)
            else:
                base_score = 0.0

            # Coverage = how many of the PRD skills they actually have
            coverage = (
                len(matched_names) / total_required
                if total_required > 0 else 0.0
            )

            # Average proficiency across only the matched skills (0–10 scale)
            avg_prof = (
                sum(matched_profs) / len(matched_profs)
                if matched_profs else 0.0
            )

            # 🧮 Workload penalty based on active projects (unchanged)
            if active_projects <= 0:
                multiplier = 1.0
            elif active_projects == 1:
                multiplier = 0.9
            elif active_projects == 2:
                multiplier = 0.75
            else:
                multiplier = 0.5

            penalized_score = base_score * multiplier

            candidates.append({
                "id": emp["empID"],
                "name": f"{emp['firstname']} {emp['lastname']}",
                "title": emp["title"] or "N/A",
                "email": emp["email"],
                "matchScore": round(penalized_score, 1),       # what UI shows
                "baseMatchScore": base_score,                  # raw skill fit (0–100)
                "loadPenaltyMultiplier": round(multiplier, 2),
                "activeProjectCount": int(active_projects),
                "atCapacity": active_projects >= 3,
                "coveragePercent": round(coverage * 100.0, 1), # % of PRD skills matched
                "avgProficiency": round(avg_prof, 2),          # 0–10 across matched skills
                "skillsMatched": matched_names,                # names of matched PRD skills
            })

        # 4️⃣ Rank candidates by penalized score
        candidates_sorted = sorted(candidates, key=lambda x: x["matchScore"], reverse=True)

        if not candidates_sorted:
            return {
                "top5_skills": top5,
                "recommended_team": [],
                "department_id": department_id,
                "ai_provider": "openai",
            }

        n = min(k, len(candidates_sorted))
        priority_key = (priority or "Critical").strip().lower()

        # 🧠 Priority mixing logic (unchanged)
        if priority_key == "critical":
            # Just take the best n people
            chosen = candidates_sorted[:n]
        else:
            if priority_key == "high":
                high_count = max(1, round(n * 0.75))
            elif priority_key == "medium":
                high_count = max(1, round(n * 0.5))
            elif priority_key == "low":
                high_count = min(2, n)
            else:
                # Fallback: behave like critical
                high_count = n

            low_count = max(0, n - high_count)

            # Top = high matches (can include overloaded folks)
            high_selected = candidates_sorted[:high_count]

            # Remaining pool, excluding the ones we already picked
            remaining = [c for c in candidates_sorted if c not in high_selected]

            # Build the "low-qualified" pool EXCLUDING overloaded people
            low_pool = [
                c for c in reversed(remaining)
                if not c["atCapacity"]
            ]

            low_selected = low_pool[:low_count]

            # If we still don't have enough, backfill with any remaining non-overloaded folks.
            if len(low_selected) < low_count:
                needed = low_count - len(low_selected)
                backup = [
                    c for c in reversed(remaining)
                    if c not in low_selected and not c["atCapacity"]
                ][:needed]
                low_selected.extend(backup)

            chosen = high_selected + low_selected

        return {
            "top5_skills": top5,
            "recommended_team": chosen,
            "department_id": department_id,
            "ai_provider": "openai",
        }
    finally:
        conn.close()



