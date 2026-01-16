import os
from pathlib import Path

# Mapping of current index filenames to new ones
INDEX_RENAMES = {
    "00_Index_trading-copilot.md": "00_Index_trading-copilot.md",
    "00_Index_tax-organizer.md": "00_Index_tax-organizer.md",
    "00_Index_ai-usage-billing-tracker.md": "00_Index_ai-usage-billing-tracker.md",
    "00_Index_ai-model-scratch-build.md": "00_Index_ai-model-scratch-build.md",
    "00_Index_smart-invoice-workflow.md": "00_Index_smart-invoice-workflow.md",
    "00_Index_land-tracker.md": "00_Index_land-tracker.md",
    "00_Index_plugin-duplicate-detection.md": "00_Index_plugin-duplicate-detection.md",
    "00_Index_plugin-find-names-chrome.md": "00_Index_plugin-find-names-chrome.md",
    "00_Index_3d-pose-factory.md": "00_Index_3d-pose-factory.md",
    "00_Index_ai-journal.md": "00_Index_ai-journal.md",
    "00_Index_automation-consulting.md": "00_Index_automation-consulting.md",
    "00_Index_country-ai-futures-tracker.md": "00_Index_country-ai-futures-tracker.md",
    "00_Index_sherlock-holmes.md": "00_Index_sherlock-holmes.md",
    "00_Index_solutions-architect.md": "00_Index_solutions-architect.md",
    "00_Index_van-build.md": "00_Index_van-build.md",
    "00_Index_portfolio-ai.md": "00_Index_portfolio-ai.md",
    "00_Index_synth-insight-labs.md": "00_Index_synth-insight-labs.md",
    "00_Index_holoscape.md": "00_Index_holoscape.md",
    "00_Index_cortana-personal-ai.md": "00_Index_cortana-personal-ai.md",
    "00_Index_flo-fi.md": "00_Index_flo-fi.md",
    "00_Index_subscription-tracker.md": "00_Index_subscription-tracker.md",
    "00_Index_national-cattle-brands.md": "00_Index_national-cattle-brands.md",
    "00_Index_prospector.md": "00_Index_prospector.md",
}

def rename_indices(root_dir):
    root_path = Path(root_dir)
    renamed_count = 0
    
    for old_name, new_name in INDEX_RENAMES.items():
        # Search for the old index file in all subdirectories
        for index_file in root_path.rglob(old_name):
            new_file_path = index_file.with_name(new_name)
            try:
                index_file.rename(new_file_path)
                print(f"Renamed: {index_file.relative_to(root_path)} -> {new_name}")
                renamed_count += 1
            except Exception as e:
                print(f"Error renaming {index_file}: {e}")
                
    print(f"\nRenamed {renamed_count} index files.")

if __name__ == "__main__":
    rename_indices("[USER_HOME]/projects")
