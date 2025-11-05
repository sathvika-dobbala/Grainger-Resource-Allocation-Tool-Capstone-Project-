# ai_helper.py
import os
import sys
import json
import sqlite3
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

# -----------------------------
# Import AI logic from AI Use Case 3.0
# -----------------------------
import importlib.util

ai_pdf_path = os.path.join(os.path.dirname(__file__), 'AI Use Case 3.0', 'ai_pdf_app.py')
spec = importlib.util.spec_from_file_location("ai_pdf_app", ai_pdf_path)
ai_pdf_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_pdf_app)

# Re-exported helpers from ai_pdf_app
suggest_team = ai_pdf_app.suggest_team
_conn = ai_pdf_app._conn
_get_skill_id_map = ai_pdf_app._get_skill_id_map
call_openai = ai_pdf_app.call_openai
call_anthropic = ai_pdf_app.call_anthropic
call_gemini = ai_pdf_app.call_gemini

load_dotenv()
DB_PATH = os.getenv("EMPLOYEE_DB_PATH", "employees.db")


# -----------------------------
# Prompt building
# -----------------------------
def build_prompt_for_skills(skills_text: str, skill_id_map: Dict[str, int]) -> str:
    """
    Build a prompt for the AI to identify top 5 skills from the provided skills list.
    """
    skill_list = "\n".join([f"- {name} (ID={sid})" for name, sid in skill_id_map.items()])
    prompt = f"""You are a project management assistant. Given a list of skills needed for a project, 
identify the top 5 most important skills from the available skills database.

Skills needed: {skills_text}

Available skills in database:
{skill_list}

Return ONLY valid JSON in this exact format:
{{
  "top5": [
    {{"skillID": 1, "skillName": "Python", "reason": "Essential for backend development"}},
    {{"skillID": 2, "skillName": "SQL", "reason": "Required for database management"}},
    ...
  ]
}}

Rules:
- Return exactly 5 skills
- Only use skillIDs from the list above
- Keep reasons brief (one sentence)
- Return ONLY the JSON, no other text
"""
    return prompt


def parse_top5_json(raw: str) -> List[dict]:
    """Parse the AI response into top5 skills (strict JSON, but tolerate code fences)."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    data = json.loads(raw)
    out = []
    for entry in data["top5"][:5]:
        out.append({
            "skillID": int(entry["skillID"]),
            "skillName": str(entry["skillName"]).strip(),
            "reason": str(entry.get("reason", "")).strip(),
        })
    return out


# -----------------------------
# Main entry: AI team recommendations
# -----------------------------
def get_ai_team_recommendations(skills_needed: List[str], k: int = 4, ai_provider: Optional[str] = None) -> Dict:
    """
    Use AI to analyze skills and recommend a team.

    Args:
        skills_needed: List of skill names needed for the project
        k: Number of team members to recommend (default 4)
        ai_provider: 'openai', 'anthropic', or 'gemini' (auto-detect from env if None)

    Returns:
        Dict with 'top5_skills', 'recommended_team', and 'ai_provider'
    """
    conn = _conn(DB_PATH)

    try:
        # 1) Skill ID map from DB
        skill_id_map = _get_skill_id_map(conn)

        # 2) Build AI prompt
        skills_text = ", ".join(skills_needed)
        prompt = build_prompt_for_skills(skills_text, skill_id_map)

        # 3) Choose provider (env fallbacks)
        if ai_provider is None:
            if os.getenv("OPENAI_API_KEY"):
                ai_provider = "openai"
            elif os.getenv("ANTHROPIC_API_KEY"):
                ai_provider = "anthropic"
            elif os.getenv("GOOGLE_API_KEY"):
                ai_provider = "gemini"
            else:
                raise RuntimeError("No AI API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY")

        print(f"🤖 Using {ai_provider.upper()} for recommendations...")

        # 4) Call AI
        if ai_provider == "openai":
            result = call_openai(prompt)
        elif ai_provider == "anthropic":
            result = call_anthropic(prompt)
        elif ai_provider == "gemini":
            result = call_gemini(prompt)
        else:
            raise ValueError(f"Unknown AI provider: {ai_provider}")

        # 5) Parse AI response
        try:
            top5_skills = parse_top5_json(result)
        except Exception as e:
            print(f"Failed to parse AI response: {e}")
            print(f"Raw response: {result}")
            raise RuntimeError(f"AI returned invalid JSON: {e}")

        # 6) Get suggested employees by ID
        team_emp_ids = suggest_team(DB_PATH, top5_skills, k=k, exclude=set())

        # 7) Hydrate employees and compute match score + breakdown
        team_members = []
        for rank, emp_id in enumerate(team_emp_ids):
            emp = conn.execute("""
                SELECT 
                    e.empID,
                    e.firstname,
                    e.lastname,
                    e.title,
                    e.email,
                    e.photo,
                    d.departmentname,
                    t.teamName
                FROM Employees e
                LEFT JOIN Departments d ON e.department = d.depID
                LEFT JOIN Teams t ON e.teamID = t.teamID
                WHERE e.empID = ?
            """, (emp_id,)).fetchone()

            if not emp:
                continue

            # Employee skills with proficiency
            emp_skills = conn.execute("""
                SELECT s.skillID, s.skillName, es.profiencylevel
                FROM EmployeeSkills es
                JOIN Skills s ON es.skillID = s.skillID
                WHERE es.empID = ?
                ORDER BY es.profiencylevel DESC
            """, (emp_id,)).fetchall()

            # --- Scoring (0–10 proficiency scale) ---
            top5_skill_ids = [skill['skillID'] for skill in top5_skills]
            emp_skill_ids = [skill['skillID'] for skill in emp_skills]

            # Coverage / base score (0–60)
            matching_skills = sum(1 for sid in top5_skill_ids if sid in emp_skill_ids)
            base_score = (matching_skills / len(top5_skills)) * 60 if top5_skills else 0

            # Proficiency bonus (0–30), normalize 0–10 → 0–30
            if matching_skills > 0:
                matching_proficiencies = [
                    skill['profiencylevel'] for skill in emp_skills
                    if skill['skillID'] in top5_skill_ids
                ]
                avg_proficiency = sum(matching_proficiencies) / len(matching_proficiencies)
                proficiency_bonus = (avg_proficiency / 10) * 30  # 0–10 scale → 0–30
            else:
                avg_proficiency = 0
                proficiency_bonus = 0

            # Rank bonus (0–10), decays by 2 per rank
            rank_bonus = max(0, 10 - (rank * 2))

            # Final (0–100)
            match_score = int(base_score + proficiency_bonus + rank_bonus)
            match_score = min(100, max(0, match_score))

            # --- Structured breakdown + quick explanation for UI ---
            matched_skill_list = [
                {
                    "skillID": s['skillID'],
                    "skillName": s['skillName'],
                    "proficiency": s['profiencylevel']  # expected to be 0–10
                }
                for s in emp_skills if s['skillID'] in top5_skill_ids
            ]

            match_breakdown = {
                "matchingSkills": matching_skills,
                "totalTopSkills": len(top5_skills),
                "coveragePercent": round((base_score / 60) * 100, 1) if top5_skills else 0.0,
                "baseScore": round(base_score, 1),                 # out of 60
                "avgProficiency": round(avg_proficiency, 2),       # 0–10
                "proficiencyBonus": round(proficiency_bonus, 1),   # out of 30
                "rank": rank,
                "rankBonus": rank_bonus,                           # out of 10
                "finalScore": match_score,                         # 0–100
                "matchedSkills": matched_skill_list                # which top skills matched
            }

            match_explanation = (
                f"{matching_skills}/{len(top5_skills)} key skills "
                f"({round((base_score/60)*100,1)}% coverage); "
                f"avg proficiency {round(avg_proficiency,2)} → +{round(proficiency_bonus,1)}; "
                f"rank bonus +{rank_bonus} = {match_score}"
            )

            team_members.append({
                'id': emp['empID'],
                'name': f"{emp['firstname']} {emp['lastname']}",
                'title': emp['title'] or 'No title',
                'email': emp['email'],
                'department': emp['departmentname'] or 'No department',
                'team': emp['teamName'] or 'No team',
                'skills': [skill['skillName'] for skill in emp_skills[:5]],  # top 5 skills on card
                'avatar': emp['photo'],
                'matchScore': match_score,
                'matchBreakdown': match_breakdown,      # for UI tooltip/popover
                'matchExplanation': match_explanation   # quick title="" string
            })

        return {
            'top5_skills': top5_skills,
            'recommended_team': team_members,
            'ai_provider': ai_provider
        }

    finally:
        conn.close()
