import os
import re

# Comprehensive WikiLink replacement map
# Format: (Old WikiLink Name, New WikiLink Name)
WIKILINK_MAP = [
    (r"Trading Projects", "trading-copilot"),
    (r"TradingProjects", "trading-copilot"),
    (r"Tax processing", "tax-organizer"),
    (r"Tax-processing", "tax-organizer"),
    (r"TaxProcessing", "tax-organizer"),
    (r"AI model build from scratch", "ai-model-scratch-build"),
    (r"AI-model-build-from-scratch", "ai-model-scratch-build"),
    (r"AIModelBuild", "ai-model-scratch-build"),
    (r"Smart Invoice Follow-Up Workflow", "smart-invoice-workflow"),
    (r"Smart-Invoice-Follow-Up-Workflow", "smart-invoice-workflow"),
    (r"SmartInvoiceWorkflow", "smart-invoice-workflow"),
    (r"3D Pose Factory", "3d-pose-factory"),
    (r"3D-Pose-Factory", "3d-pose-factory"),
    (r"3DPoseFactory", "3d-pose-factory"),
    (r"AI usage-billing tracker", "ai-usage-billing-tracker"),
    (r"AI-usage-billing-tracker", "ai-usage-billing-tracker"),
    (r"AIUsageBillingTracker", "ai-usage-billing-tracker"),
    (r"AI-journal", "ai-journal"),
    (r"Automation Consulting", "automation-consulting"),
    (r"AutomationConsulting", "automation-consulting"),
    (r"Country AI Futures Tracker", "country-ai-futures-tracker"),
    (r"CountryAIFuturesTracker", "country-ai-futures-tracker"),
    (r"Sherlock Holmes", "sherlock-holmes"),
    (r"Sherlock-Holmes", "sherlock-holmes"),
    (r"Solutions Architect", "solutions-architect"),
    (r"SolutionsArchitect", "solutions-architect"),
    (r"Van Build", "van-build"),
    (r"VanBuild", "van-build"),
    (r"NationalCattleBrands", "national-cattle-brands"),
    (r"National-Cattle-Brands", "national-cattle-brands"),
    (r"SynthInsightLabs", "synth-insight-labs"),
    (r"Synth-Insight-Labs", "synth-insight-labs"),
    (r"Holoscape", "holoscape"),
    (r"Cortana personal AI", "cortana-personal-ai"),
    (r"CortanaPersonalAI", "cortana-personal-ai"),
    (r"Flo-Fi", "flo-fi"),
    (r"Portfolio-ai", "portfolio-ai"),
    (r"Subscription Tracker", "subscription-tracker"),
    (r"SubscriptionTracker", "subscription-tracker"),
    (r"Land", "land-tracker"),
]

# Path replacements for trading reports and other code
PATH_REPLACEMENTS = [
    (r"[USER_HOME]/projects/trading-copilot", "[USER_HOME]/projects/trading-copilot"),
    (r"[USER_HOME]/projects/trading-copilot", "[USER_HOME]/projects/trading-copilot"),
    (r"[USER_HOME]/projects/tax-organizer", "[USER_HOME]/projects/tax-organizer"),
    (r"[USER_HOME]/projects/tax-organizer", "[USER_HOME]/projects/tax-organizer"),
    (r"agent-os", "agent-os"), # Wait, we are getting rid of agent-os, but if we refer to the retired one it should be kebab
]

def fix_wikilinks(content):
    # Fix [[Old Name]] and [[Old Name|Display]]
    new_content = content
    for old, new in WIKILINK_MAP:
        # Match [[Old Name]]
        new_content = re.sub(r'\[\[\s*' + re.escape(old) + r'\s*\]\]', f'[[{new}]]', new_content)
        # Match [[Old Name|Display]]
        new_content = re.sub(r'\[\[\s*' + re.escape(old) + r'\s*\|', f'[[{new}|', new_content)
        # Match 00_Index variant
        new_content = re.sub(r'00_Index_' + re.escape(old), f'00_Index_{new}', new_content)
    
    for old_path, new_path in PATH_REPLACEMENTS:
        new_content = new_content.replace(old_path, new_path)
        
    return new_content

def run_cleanup(root_dir):
    print(f"Cleaning up {root_dir}...")
    count = 0
    for root, dirs, files in os.walk(root_dir):
        if any(exc in root for exc in [".git", "node_modules", "venv", "ai-journal"]): continue
        for file in files:
            if not file.endswith((".md", ".json", ".py", ".sh", ".yaml", ".txt")): continue
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                new_content = fix_wikilinks(content)
                
                if new_content != content:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    count += 1
            except Exception as e:
                print(f"Error in {path}: {e}")
    print(f"Updated {count} files.")

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "[USER_HOME]/projects"
    run_cleanup(target)
