import sys
import os
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from router import AIRouter

def agent_skills_dry_run():
    router = AIRouter()
    
    # Context gathering (Dry run - no file writing)
    skills_root = Path("/Users/eriksjaastad/projects/agent-skills-library")
    claude_skills = list((skills_root / "claude-skills").glob("**/SKILL.md"))
    
    skill_summaries = []
    for skill_path in claude_skills:
        try:
            content = skill_path.read_text()
            # Just take the first 10 lines for context
            summary = "\n".join(content.split("\n")[:10])
            skill_summaries.append(f"File: {skill_path.relative_to(skills_root)}\n{summary}")
        except Exception:
            continue

    skills_context = "\n\n".join(skill_summaries)

    prompt = f"""
    You are the "Head of Agent R&D" for Erik's massive research/trading vault.
    
    CURRENT SKILLS IN LIBRARY:
    {skills_context}
    
    TASK:
    Erik just finished an ecosystem-wide "Gold Standard" scaffolding sweep. 
    He wants a "dry run" proposal for a NEW skill that helps him maintain this standard.
    
    PROPOSE:
    1. A new skill name that fits the library's naming convention.
    2. A brief "Skill Overview" (What it does).
    3. A "When to Activate" section (What user signals should trigger it).
    4. A "Connection" analysis: How does this new skill connect the "Image Workflow" (the massive central hub) to the "Project Tracker"?
    
    DRY RUN MODE: Do not write any files. Just provide the strategic proposal.
    """
    
    # This time, we FORCE the expensive tier for deep strategic insight
    print("🤖 AI Router: Starting the 'Head of Agent R&D' DEEP DIVE (Expensive Tier)...\n")
    res = router.chat([{"role": "user", "content": prompt}], tier="expensive")
    
    print(f"📍 Route: {res.tier.upper()} ({res.provider} / {res.model})")
    print("\n" + "="*50)
    print("STRATEGIC PROPOSAL")
    print("="*50 + "\n")
    print(res.text.strip())
    print("\n" + "="*50)

if __name__ == "__main__":
    # Ensure API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ Warning: OPENAI_API_KEY not found in environment. Only LOCAL tier will work.")
    
    agent_skills_dry_run()

