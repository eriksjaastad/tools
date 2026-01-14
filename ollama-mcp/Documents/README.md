# Documentation

**Last Updated:** 2026-01-01  
**Audience:** Developers, Operators, AI Collaborators

---

## Quick Start

### New to this project?
1. Read `core/ARCHITECTURE_OVERVIEW.md` (5-10 min)
2. Skim this README for relevant sections
3. Check `../TODO.md` for current work

### Daily shortcuts
- Current work: `../TODO.md`
- Code standards: `reference/CODE_QUALITY_RULES.md`
- Safety rules: `../.cursorrules`

---

## Documentation Structure

This project follows the **Documents/ pattern** - a centralized documentation directory that prevents root-level sprawl and makes information discoverable.

### Core Directories

#### `core/`
**Purpose:** Essential architecture and operations documentation

**Files:**
- `ARCHITECTURE_OVERVIEW.md` - System map, how components fit together
- `OPERATIONS_GUIDE.md` - How to run, build, and maintain

---

#### `guides/`
**Purpose:** How-to documents for specific tasks

**Files:**
- `SETUP_CHECKLIST.md` - Installation and configuration
- `TELEMETRY_GUIDE.md` - Walkthrough of the telemetry system

---

#### `reference/`
**Purpose:** Standards, conventions, and knowledge base

**Files:**
- `EXAMPLE_OUTPUT.md` - Sample tool outputs
- `TELEMETRY_QUICKREF.md` - Quick reference for telemetry logs

---

#### `archives/`
**Purpose:** Historical documentation

**Subdirectories:**
- `implementations/` - Completed feature summaries (`DELIVERY_SUMMARY.md`, `IMPLEMENTATION_SUMMARY.md`)

---

## Maintenance

### Document Review Schedule

**Monthly:**
- Update `../TODO.md` (keep current)
- Check `core/` docs for accuracy

**Quarterly:**
- Review `archives/` for expiration candidates

---

*This structure is based on the [project-scaffolding](https://github.com/eriksjaastad/project-scaffolding) Documents/ pattern.*

