import sys
import os
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from router import AIRouter

def audit_reasoning_dry_run():
    router = AIRouter()
    
    prompt = """
    You are the "Head of Agent R&D". 
    Erik wants a "skill" that leverages his fast Go-based 'audit-agent' and his 'ai_router' without creating "busy work" or "blocking development".
    
    SYSTEM CONTEXT:
    1. Go 'audit' tool: Extremely fast at scanning files and finding rule violations (missing tags, bad frontmatter, open tasks).
    2. 'ai_router': Routes tasks between local Ollama (FREE) and Cloud ($).
    3. Erik's preference: Local models doing as much as possible, no intrusive governance, focus on helpfulness over "rule enforcement".
    
    TASK:
    Propose a skill that acts as a "Smart Filter" for the audit data.
    
    PROPOSE:
    1. Skill Name: (Something that sounds like an assistant, not a cop).
    2. The "Intelligence Layer": How does it use the local model to make the Go audit data *less* annoying?
    3. The "Human Oversight" loop: How does Erik interact with it?
    4. Why it's NOT busy work: What specific pain does it remove?
    
    DRY RUN MODE: No file writing. Just strategy.
    """
    
    # This time, we use the expensive tier for a more "Erik-centric" architecture
    print("🤖 AI Router: Refing the proposal with high-reasoning (Expensive Tier)...\n")
    res = router.chat([{"role": "user", "content": prompt}], tier="expensive")
    
    print(f"📍 Route: {res.tier.upper()} ({res.provider} / {res.model})")
    print("\n" + "="*50)
    print("THE 'HELPFUL ASSISTANT' PROPOSAL")
    print("="*50 + "\n")
    print(res.text.strip())
    print("\n" + "="*50)

if __name__ == "__main__":
    audit_reasoning_dry_run()

