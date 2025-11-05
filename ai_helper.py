# ai_helper.py
import os
import sys
import json
import sqlite3
from typing import List, Dict
from dotenv import load_dotenv

# Import the AI logic from your AI Use Case 3.0 folder
import importlib.util
import os

ai_pdf_path = os.path.join(os.path.dirname(__file__), 'AI Use Case 3.0', 'ai_pdf_app.py')
spec = importlib.util.spec_from_file_location("ai_pdf_app", ai_pdf_path)
ai_pdf_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_pdf_app)

# Now extract the functions we need
suggest_team = ai_pdf_app.suggest_team
_conn = ai_pdf_app._conn
_get_skill_id_map = ai_pdf_app._get_skill_id_map
call_openai = ai_pdf_app.call_openai
call_anthropic = ai_pdf_app.call_anthropic
call_gemini = ai_pdf_app.call_gemini

load_dotenv()

DB_PATH = os.getenv("EMPLOYEE_DB_PATH", "employees.db")

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
    """Parse the AI response into top5 skills."""
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

def get_ai_team_recommendations(skills_needed: List[str], k: int = 4, ai_provider: str = None) -> Dict:
    """
    Use AI to analyze skills and recommend a team.
    
    Args:
        skills_needed: List of skill names needed for the project
        k: Number of team members to recommend (default 4)
        ai_provider: 'openai', 'anthropic', or 'gemini' (auto-detect from env if None)
    
    Returns:
        Dict with 'top5_skills' and 'recommended_team'
    """
    conn = _conn(DB_PATH)
    
    try:
        # Get skill ID map
        skill_id_map = _get_skill_id_map(conn)
        
        # Build prompt
        skills_text = ", ".join(skills_needed)
        prompt = build_prompt_for_skills(skills_text, skill_id_map)
        
        # Determine which AI provider to use
        if ai_provider is None:
            if os.getenv("OPENAI_API_KEY"):
                ai_provider = "openai"
            elif os.getenv("ANTHROPIC_API_KEY"):
                ai_provider = "anthropic"
            elif os.getenv("GOOGLE_API_KEY"):
                ai_provider = "gemini"
            else:
                raise RuntimeError("No AI API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY")
        
        # Call AI
        print(f"🤖 Using {ai_provider.upper()} for recommendations...")
        if ai_provider == "openai":
            result = call_openai(prompt)
        elif ai_provider == "anthropic":
            result = call_anthropic(prompt)
        elif ai_provider == "gemini":
            result = call_gemini(prompt)
        else:
            raise ValueError(f"Unknown AI provider: {ai_provider}")
        
        # Parse AI response
        try:
            top5_skills = parse_top5_json(result)
        except Exception as e:
            print(f"Failed to parse AI response: {e}")
            print(f"Raw response: {result}")
            raise RuntimeError(f"AI returned invalid JSON: {e}")
        
        # Use the existing suggest_team function to get employee recommendations
        team_emp_ids = suggest_team(DB_PATH, top5_skills, k=k, exclude=set())
        
        # Get detailed employee info
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
            
            if emp:
                # Get employee's skills with skillID
                emp_skills = conn.execute("""
                    SELECT s.skillID, s.skillName, es.profiencylevel
                    FROM EmployeeSkills es
                    JOIN Skills s ON es.skillID = s.skillID
                    WHERE es.empID = ?
                    ORDER BY es.profiencylevel DESC
                """, (emp_id,)).fetchall()
                
                # Calculate REAL match score based on:
                # 1. How many top5 skills they have
                # 2. Their proficiency levels
                # 3. Their rank in the suggestion (first = highest score)
                
                top5_skill_ids = [skill['skillID'] for skill in top5_skills]
                emp_skill_ids = [skill['skillID'] for skill in emp_skills]
                
                # Count matching skills
                matching_skills = sum(1 for sid in top5_skill_ids if sid in emp_skill_ids)
                
                # Calculate base score (0-60 based on skill overlap)
                base_score = (matching_skills / len(top5_skills)) * 60 if top5_skills else 0
                
                # Add proficiency bonus (0-30 based on avg proficiency of matching skills)
                if matching_skills > 0:
                    matching_proficiencies = [
                        skill['profiencylevel'] for skill in emp_skills 
                        if skill['skillID'] in top5_skill_ids
                    ]
                    avg_proficiency = sum(matching_proficiencies) / len(matching_proficiencies)
                    proficiency_bonus = (avg_proficiency / 10) * 30  # Scale to 0-30
                else:
                    proficiency_bonus = 0
                
                # Add rank bonus (0-10, decreases with rank)
                rank_bonus = max(0, 10 - (rank * 2))
                
                # Final score
                match_score = int(base_score + proficiency_bonus + rank_bonus)
                match_score = min(100, max(0, match_score))  # Clamp between 0-100
                
                team_members.append({
                    'id': emp['empID'],
                    'name': f"{emp['firstname']} {emp['lastname']}",
                    'title': emp['title'] or 'No title',
                    'email': emp['email'],
                    'department': emp['departmentname'] or 'No department',
                    'team': emp['teamName'] or 'No team',
                    'skills': [skill['skillName'] for skill in emp_skills[:5]],  # Top 5 skills
                    'avatar': emp['photo'],
                    'matchScore': match_score  # Now it's REAL!
                })

        
        return {
            'top5_skills': top5_skills,
            'recommended_team': team_members,
            'ai_provider': ai_provider
        }
        
    finally:
        conn.close()