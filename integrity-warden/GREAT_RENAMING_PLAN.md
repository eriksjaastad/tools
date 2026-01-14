# The Great Renaming: Execution Plan (2026-01-14)

## 🎯 Goal
Standardize all top-level project names to lowercase-kebab-case, align local and remote naming, and fix descriptive drift.

## 🛡️ "Hands-Off" List (No Name Changes)
- `muffinpanrecipes` (Domain-linked)
- `synth-insight-labs` -> `synth-insight-labs` (Case change only)
- `cortana-personal-ai`
- `flo-fi`
- `holoscape` (Local now matches GitHub)
- `hypocrisynow`

## 🔄 Renaming Map

### Group A: Local Directory Renames (To Match GitHub)
| Old Local Name | New Local Name | Reason |
| :--- | :--- | :--- |
| `trading-copilot` | `trading-copilot` | Align with GitHub repo |
| `tax-organizer` | `tax-organizer` | Align with GitHub repo |
| `ai-model-scratch-build` | `ai-model-scratch-build` | Align with GitHub/Kebab-case |
| `smart-invoice-workflow` | `smart-invoice-workflow` | Shorten to match GitHub |

### Group B: Local Directory Renames (Standardization)
| Old Local Name | New Local Name | Reason |
| :--- | :--- | :--- |
| `Land` | `land-tracker` | Alignment with GitHub (to be updated) |
| `plugin-duplicate-detection` | `plugin-duplicate-detection` | Organization (Plugin prefix) |
| `plugin-find-names-chrome` | `plugin-find-names-chrome` | Organization (Plugin prefix) |
| `3d-pose-factory` | `3d-pose-factory` | Kebab-case |
| `ai-usage-billing-tracker` | `ai-usage-billing-tracker` | Kebab-case |
| `analyze-youtube-videos` | `analyze-youtube-videos` | (Already good) |
| `audit-agent` | `audit-agent` | (Already good) |
| `ai-journal` | `ai-journal` | Kebab-case |
| `automation-consulting` | `automation-consulting` | Kebab-case |
| `country-ai-futures-tracker` | `country-ai-futures-tracker` | Kebab-case |
| `sherlock-holmes` | `sherlock-holmes` | Kebab-case |
| `solutions-architect` | `solutions-architect` | Kebab-case |
| `van-build` | `van-build` | Kebab-case |
| `portfolio-ai` | `portfolio-ai` | Case fix |

### Group C: GitHub Repository Renames
| Local Project | Old GitHub Name | New GitHub Name |
| :--- | :--- | :--- |
| `holoscape` | `hologram` | `holoscape` |
| `image-workflow` | `image-workflow-scripts` | `image-workflow` |
| `land-tracker` | `arizona-land-bot` (or local) | `land-tracker` |

## 🧪 "The Ghost Prevention" Protocol
To ensure I don't get lost when context resets:
1. **Checkpointing:** I will update the root `WARDEN_LOG.yaml` after every 5 renames.
2. **The Warden Sweep:** I will run `integrity_warden.py` after the renames to generate a "Remediation List."
3. **Symbolic Links (Optional):** If a rename is particularly dangerous, I'll create a temporary symlink from the old name to the new name until all code is updated.

---
*Created by Super Manager (Gemini 3 Flash) - Jan 14, 2026*
