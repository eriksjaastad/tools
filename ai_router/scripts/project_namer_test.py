import sys
import os
import json
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from router import AIRouter

def project_namer_test():
    router = AIRouter()
    
    # The "weird" directories to analyze
    weird_dirs = [
        "actionable-ai-intel",
        "agent-os",
        "flo-fi",
        "hologram",
        "hypocrisynow",
        "Prospector",
        "synth-insight-labs"
    ]
    
    print("🧠 Starting the Project Namer Test with AI Router...\n")
    
    results = {}
    
    for dir_name in weird_dirs:
        print(f"🔍 Analyzing directory: {dir_name}...")
        dir_path = Path(f"[USER_HOME]/projects/{dir_name}")
        
        # 1. LOCAL TIER: Get a quick summary of what's inside
        # We'll just pass the file list to the local model
        try:
            files = [f.name for f in dir_path.glob("*") if not f.name.startswith(".")]
            file_context = ", ".join(files[:15]) # Just a sample
        except Exception:
            file_context = "Could not read directory."

        prompt = f"""
        Directory Name: {dir_name}
        Files inside: {file_context}
        
        Task: 
        1. Briefly describe what this project seems to be based on the name and files.
        2. Suggest 3 creative, high-level alternative names that are more descriptive.
        
        Format your response exactly as:
        SUMMARY: [one sentence]
        NAMES: [Name 1], [Name 2], [Name 3]
        """
        
        # This is a perfect "auto" routing task. 
        # Short context + question should trigger "CHEAP" cloud or "LOCAL"
        res = router.chat([{"role": "user", "content": prompt}], tier="auto")
        
        print(f"📍 Route: {res.tier.upper()} ({res.provider})")
        print(res.text.strip())
        print("-" * 30 + "\n")

if __name__ == "__main__":
    # Ensure API key is set if you want cloud tiers to work
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ Warning: OPENAI_API_KEY not found in environment. Only LOCAL tier will work.")
    
    project_namer_test()

