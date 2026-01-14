# Floor Manager Task: Verify Smart Routing Configuration

**Model:** Floor Manager (this is a verification task, not Worker delegation)
**Objective:** Verify the SSOT routing configuration is correct and complete

---

## ⚠️ DOWNSTREAM HARM ESTIMATE

- **If this fails:** Routing config could send tasks to wrong models. Classification tasks might hit slow models, code tasks might hit weak models.
- **Known pitfalls:** YAML syntax errors fail silently. Missing task types fall back to "auto" without warning.
- **Recovery:** Fix YAML file, rebuild.

---

## 📚 LEARNINGS APPLIED

- [x] Consulted project-scaffolding patterns (date: Jan 10, 2026)
- [x] SSOT pattern: Config lives in YAML, not hardcoded in TypeScript
- [x] Task types from spec: classification, extraction, code, reasoning, file_mod, auto

---

## CONSTRAINTS (READ FIRST)

- DO NOT modify src/server.ts in this task
- DO NOT add new task types not in the spec
- ONLY verify and fix config/routing.yaml

---

## 🎯 [ACCEPTANCE CRITERIA]

### File Structure
- [x] `config/routing.yaml` exists
- [x] File is valid YAML (no syntax errors)
- [x] File can be parsed by js-yaml

### Required Task Types
- [x] `classification` chain exists with llama3.2:3b first
- [x] `extraction` chain exists with llama3.2:3b first
- [x] `code` chain exists with qwen3:14b first
- [x] `reasoning` chain exists with deepseek-r1 first
- [x] `file_mod` chain exists with qwen3:14b first
- [x] `auto` chain exists as catch-all

### Chain Structure
- [x] Each chain has at least 2 models for fallback
- [x] Model names match installed Ollama models
- [x] No duplicate models in same chain

### Verification Command
```bash
# Parse YAML and print structure
node -e "const yaml = require('js-yaml'); const fs = require('fs'); console.log(JSON.stringify(yaml.load(fs.readFileSync('config/routing.yaml', 'utf8')), null, 2))"
```

---

## FLOOR MANAGER PROTOCOL

1. Read `config/routing.yaml`
2. Check each acceptance criterion
3. If any fail, fix the YAML file
4. Run verification command
5. Mark all criteria with [x] when verified
6. Report any discrepancies found

---
