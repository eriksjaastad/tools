import os
import re

# Precise mapping for project name replacements
# Including variants with hyphens, spaces, and underscores
REPLACEMENTS = [
    (r"trading-copilot", "trading-copilot"),
    (r"trading-copilot", "trading-copilot"),
    (r"trading-copilot", "trading-copilot"),
    
    (r"tax-organizer", "tax-organizer"),
    (r"tax-organizer", "tax-organizer"),
    (r"tax-organizer", "tax-organizer"),
    
    (r"ai-model-scratch-build", "ai-model-scratch-build"),
    (r"ai-model-scratch-build", "ai-model-scratch-build"),
    
    (r"smart-invoice-workflow", "smart-invoice-workflow"),
    (r"smart-invoice-workflow", "smart-invoice-workflow"),
    (r"smart-invoice-workflow", "smart-invoice-workflow"),
    
    (r"3d-pose-factory", "3d-pose-factory"),
    (r"3d-pose-factory", "3d-pose-factory"),
    (r"3d-pose-factory", "3d-pose-factory"),
    
    (r"ai-usage-billing-tracker", "ai-usage-billing-tracker"),
    (r"ai-usage-billing-tracker", "ai-usage-billing-tracker"),
    (r"ai-usage-billing-tracker", "ai-usage-billing-tracker"),
    
    (r"automation-consulting", "automation-consulting"),
    (r"automation-consulting", "automation-consulting"),
    
    (r"country-ai-futures-tracker", "country-ai-futures-tracker"),
    (r"country-ai-futures-tracker", "country-ai-futures-tracker"),
    
    (r"sherlock-holmes", "sherlock-holmes"),
    (r"sherlock-holmes", "sherlock-holmes"),
    
    (r"solutions-architect", "solutions-architect"),
    (r"solutions-architect", "solutions-architect"),
    
    (r"van-build", "van-build"),
    (r"van-build", "van-build"),
    
    (r"national-cattle-brands", "national-cattle-brands"),
    (r"national-cattle-brands", "national-cattle-brands"),

    (r"synth-insight-labs", "synth-insight-labs"),
    (r"synth-insight-labs", "synth-insight-labs"),
    
    (r"cortana-personal-ai", "cortana-personal-ai"),
    (r"cortana-personal-ai", "cortana-personal-ai"),
    
    (r"holoscape", "holoscape"),
    (r"flo-fi", "flo-fi"),
    (r"portfolio-ai", "portfolio-ai"),
    
    (r"subscription-tracker", "subscription-tracker"),
    (r"subscription-tracker", "subscription-tracker"),

    # Cross-references and paths
    (r"projects/land-tracker", "projects/land-tracker"),
    (r"\[\[Land\]\]", "[[land-tracker]]"),
    (r"\[\[Land\|", "[[land-tracker|"),
    
    # Index files
    (r"00_Index_trading-copilot", "00_Index_trading-copilot"),
    (r"00_Index_tax-organizer", "00_Index_tax-organizer"),
    (r"00_Index_ai-usage-billing-tracker", "00_Index_ai-usage-billing-tracker"),
    (r"00_Index_ai-model-scratch-build", "00_Index_ai-model-scratch-build"),
    (r"00_Index_smart-invoice-workflow", "00_Index_smart-invoice-workflow"),
    (r"00_Index_land-tracker", "00_Index_land-tracker"),
    (r"00_Index_plugin-duplicate-detection", "00_Index_plugin-duplicate-detection"),
    (r"00_Index_plugin-find-names-chrome", "00_Index_plugin-find-names-chrome"),
    (r"00_Index_3d-pose-factory", "00_Index_3d-pose-factory"),
    (r"00_Index_automation-consulting", "00_Index_automation-consulting"),
    (r"00_Index_country-ai-futures-tracker", "00_Index_country-ai-futures-tracker"),
    (r"00_Index_solutions-architect", "00_Index_solutions-architect"),
    (r"00_Index_van-build", "00_Index_van-build"),
    (r"00_Index_portfolio-ai", "00_Index_portfolio-ai"),
    (r"00_Index_synth-insight-labs", "00_Index_synth-insight-labs"),
    (r"00_Index_holoscape", "00_Index_holoscape"),
    (r"00_Index_cortana-personal-ai", "00_Index_cortana-personal-ai"),
    (r"00_Index_flo-fi", "00_Index_flo-fi"),
    (r"00_Index_subscription-tracker", "00_Index_subscription-tracker"),
    (r"00_Index_national-cattle-brands", "00_Index_national-cattle-brands"),
    (r"00_Index_prospector", "00_Index_prospector"),
]

EXCLUDE_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", "ai-journal"}
TEXT_EXTENSIONS = {".md", ".py", ".sh", ".bash", ".zsh", ".json", ".yaml", ".yml", ".txt", ".cursorrules", ".plist", ".toml", ".cfg", ".ini"}

def remediate(root_dir):
    print(f"Starting deep remediation sweep in {root_dir}...")
    updated_count = 0
    
    for root, dirs, files in os.walk(root_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            file_path = os.path.join(root, file)
            if any(file.endswith(ext) for ext in TEXT_EXTENSIONS):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    new_content = content
                    for pattern, replacement in REPLACEMENTS:
                        new_content = re.sub(pattern, replacement, new_content)
                    
                    if new_content != content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        # print(f"  [FIXED] {file_path}")
                        updated_count += 1
                except Exception as e:
                    print(f"  [ERROR] {file_path}: {e}")
    
    print(f"\nDeep remediation complete. Updated {updated_count} files.")

if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "/Users/eriksjaastad/projects"
    remediate(root)
