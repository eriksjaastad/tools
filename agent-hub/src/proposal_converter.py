import re
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from .utils import atomic_write, atomic_write_json, safe_read, archive_file
from .validators import validate_contract, VALID_COMPLEXITIES

COMPLEXITY_LIMITS = {
    "trivial": {"max_rebuttals": 1, "max_review_cycles": 2, "cost_ceiling_usd": 0.25, "timeout_minutes": {"implementer": 5, "local_review": 5, "judge": 5}},
    "minor": {"max_rebuttals": 2, "max_review_cycles": 5, "cost_ceiling_usd": 0.50, "timeout_minutes": {"implementer": 10, "local_review": 15, "judge": 15}},
    "major": {"max_rebuttals": 4, "max_review_cycles": 8, "cost_ceiling_usd": 2.00, "timeout_minutes": {"implementer": 20, "local_review": 20, "judge": 20}},
    "critical": {"max_rebuttals": 6, "max_review_cycles": 10, "cost_ceiling_usd": 5.00, "timeout_minutes": {"implementer": 30, "local_review": 30, "judge": 30}},
}

def parse_proposal(content: str) -> Dict[str, Any]:
    """
    Parses a PROPOSAL_FINAL.md content into a structured dictionary.
    """
    result = {
        "title": "",
        "target_project": "",
        "complexity": "minor",
        "source_files": [],
        "target_file": "",
        "requirements": [],
        "acceptance_criteria": [],
        "constraints": {
            "allowed_paths": [],
            "forbidden_paths": [],
            "delete_allowed": False,
            "max_diff_lines": 200
        },
        "notes": ""
    }

    # Extract Title
    title_match = re.search(r"^# Proposal:\s*(.*)$", content, re.MULTILINE)
    if title_match:
        result["title"] = title_match.group(1).strip()

    # Extract Target Project
    project_match = re.search(r"\*\*Target Project:\*\*\s*(.*)$", content, re.MULTILINE)
    if project_match:
        result["target_project"] = project_match.group(1).strip()

    # Extract Complexity
    complexity_match = re.search(r"\*\*Complexity:\*\*\s*(.*)$", content, re.MULTILINE)
    if complexity_match:
        comp = complexity_match.group(1).strip().lower()
        for c in VALID_COMPLEXITIES:
            if c in comp:
                result["complexity"] = c
                break

    # Extract Source Files
    source_section = re.search(r"## 3\. Source Files\n(.*?)(?=\n##|$)", content, re.DOTALL)
    if source_section:
        files = re.findall(r"-\s*[`']?(.*?)[`']?\s*$", source_section.group(1), re.MULTILINE)
        result["source_files"] = [f.strip() for f in files if f.strip()]

    # Extract Target Output
    target_section = re.search(r"## 4\. Target Output\n(.*?)(?=\n##|$)", content, re.DOTALL)
    if target_section:
        target = re.search(r"-\s*[`']?(.*?)[`']?\s*$", target_section.group(1), re.MULTILINE)
        if target:
            result["target_file"] = target.group(1).strip()

    # Extract Requirements
    req_section = re.search(r"## 5\. Requirements\n(.*?)(?=\n##|$)", content, re.DOTALL)
    if req_section:
        reqs = re.findall(r"-\s*\[\s*\]\s*(.*)$", req_section.group(1), re.MULTILINE)
        result["requirements"] = [r.strip() for r in reqs if r.strip()]

    # Extract Acceptance Criteria
    ac_section = re.search(r"## 6\. Acceptance Criteria\n(.*?)(?=\n##|$)", content, re.DOTALL)
    if ac_section:
        acs = re.findall(r"-\s*\[\s*\]\s*(.*)$", ac_section.group(1), re.MULTILINE)
        result["acceptance_criteria"] = [a.strip() for a in acs if a.strip()]

    # Extract Constraints
    constraints_section = re.search(r"## 7\. Constraints\n(.*?)(?=\n##|$)", content, re.DOTALL)
    if constraints_section:
        block = constraints_section.group(1)
        
        allowed_match = re.search(r"\*\*Allowed paths:\*\*\s*(.*)$", block, re.MULTILINE)
        if allowed_match:
            paths = re.findall(r"[`']?([^`',]+)[`']?", allowed_match.group(1))
            result["constraints"]["allowed_paths"] = [p.strip() for p in paths if p.strip()]
            
        forbidden_match = re.search(r"\*\*Forbidden paths:\*\*\s*(.*)$", block, re.MULTILINE)
        if forbidden_match:
            paths = re.findall(r"[`']?([^`',]+)[`']?", forbidden_match.group(1))
            result["constraints"]["forbidden_paths"] = [p.strip() for p in paths if p.strip()]
            
        delete_match = re.search(r"\*\*Deletions allowed:\*\*\s*(.*)$", block, re.MULTILINE)
        if delete_match:
            result["constraints"]["delete_allowed"] = "yes" in delete_match.group(1).lower()
            
        diff_match = re.search(r"\*\*Max diff size:\*\*\s*(\d+)", block, re.MULTILINE)
        if diff_match:
            result["constraints"]["max_diff_lines"] = int(diff_match.group(1))

    # Extract Notes
    notes_section = re.search(r"## 8\. Notes for Implementer\n(.*?)(?=\n---|$)", content, re.DOTALL)
    if notes_section:
        result["notes"] = notes_section.group(1).strip()

    return result

def generate_task_id(project: str, title: str) -> str:
    """
    Format: {PROJECT}-{SEQUENCE}-{SLUG}
    """
    project_slug = re.sub(r'[^A-Z0-9]', '', project.upper()) or "PROJ"
    title_slug = re.sub(r'[^A-Z0-9]', '-', title.upper()).strip('-')
    title_slug = '-'.join(filter(None, title_slug.split('-')))[:20] or "TASK"
    
    # Use seconds and a small random part to ensure uniqueness in quick tests
    sequence = datetime.now(timezone.utc).strftime("%m%d%H%M%S")
    
    return f"{project_slug}-{sequence}-{title_slug}"

def create_contract(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds the full TASK_CONTRACT.json structure.
    """
    complexity = proposal.get("complexity", "minor")
    limits = COMPLEXITY_LIMITS.get(complexity, COMPLEXITY_LIMITS["minor"])
    
    task_id = generate_task_id(proposal["target_project"], proposal["title"])
    now = datetime.now(timezone.utc).isoformat()
    
    contract = {
        "schema_version": "2.0",
        "task_id": task_id,
        "project": proposal["target_project"],
        "complexity": complexity,
        "status": "pending_implementer",
        "status_reason": "Contract initialized from proposal",
        "last_transition_id": str(uuid.uuid4()),
        "attempt": 1,
        "timestamps": {
            "created_at": now,
            "updated_at": now,
            "deadline_at": (datetime.now(timezone.utc)).isoformat() # Placeholder
        },
        "git": {
            "repo_root": str(Path.cwd()), # Default to current dir
            "base_branch": "main",
            "task_branch": f"task/{task_id}",
            "base_commit": ""
        },
        "roles": {
            "implementer": "qwen2.5-coder:14b",
            "local_reviewer": "deepseek-r1:7b",
            "judge": "claude-code-cli"
        },
        "limits": {
            "max_rebuttals": limits["max_rebuttals"],
            "max_review_cycles": limits["max_review_cycles"],
            "timeout_minutes": limits["timeout_minutes"],
            "token_budget": 50000,
            "cost_ceiling_usd": limits["cost_ceiling_usd"]
        },
        "constraints": {
            "allowed_paths": proposal["constraints"]["allowed_paths"],
            "forbidden_paths": proposal["constraints"]["forbidden_paths"],
            "allowed_operations": ["edit", "create"],
            "delete_allowed": proposal["constraints"]["delete_allowed"],
            "max_diff_lines": proposal["constraints"]["max_diff_lines"]
        },
        "specification": {
            "source_files": [{"path": f, "sha256": ""} for f in proposal["source_files"]],
            "target_file": proposal["target_file"],
            "requirements": proposal["requirements"],
            "acceptance_criteria": proposal["acceptance_criteria"]
        },
        "handoff_data": {
            "implementer_notes": proposal.get("notes", ""),
            "changed_files": [],
            "diff_summary": "",
            "local_review_passed": None,
            "local_review_issues": [],
            "judge_report_path": "_handoff/JUDGE_REPORT.md",
            "judge_report_json": "_handoff/JUDGE_REPORT.json",
            "rebuttal_path": "_handoff/REBUTTAL.md"
        },
        "lock": {
            "held_by": None,
            "acquired_at": None,
            "expires_at": None
        },
        "breaker": {
            "status": "armed",
            "triggered_by": None,
            "trigger_reason": None,
            "rebuttal_count": 0,
            "review_cycle_count": 0,
            "tokens_used": 0,
            "cost_usd": 0.00
        },
        "history": []
    }
    
    return contract

def write_rejection(handoff_dir: Path, issues: List[str]):
    """
    Writes PROPOSAL_REJECTED.md to handoff_dir.
    """
    now = datetime.now(timezone.utc).isoformat()
    content = f"""# Proposal Rejected

**Original Proposal:** PROPOSAL_FINAL.md
**Rejected At:** {now}

## Issues

""" + "\n".join(f"{i+1}. {issue}" for i, issue in enumerate(issues)) + """

## What's Needed

- Ensure all required fields are present and valid
- Specifiy a target_file
- Provide at least one requirement

## Action Required

Super Manager: Revise proposal and resubmit as PROPOSAL_FINAL.md
"""
    atomic_write(handoff_dir / "PROPOSAL_REJECTED.md", content)

def convert_proposal(proposal_path: Path, handoff_dir: Path) -> Optional[Path]:
    """
    Converts a proposal file to a TASK_CONTRACT.json file.
    Returns the path to the created contract or None if rejected.
    """
    content = safe_read(proposal_path)
    if not content:
        return None
        
    proposal = parse_proposal(content)
    
    # Validation
    issues = []
    if not proposal["title"]:
        issues.append("Missing title in proposal")
    if not proposal["target_project"]:
        issues.append("Missing target project")
    if not proposal["target_file"]:
        issues.append("Missing target file")
    if not proposal["requirements"]:
        issues.append("Empty requirements list")
        
    if issues:
        write_rejection(handoff_dir, issues)
        return None
        
    contract = create_contract(proposal)
    
    # Final schema validation
    is_valid, errors = validate_contract(contract)
    if not is_valid:
        write_rejection(handoff_dir, errors)
        return None
        
    contract_path = handoff_dir / "TASK_CONTRACT.json"
    atomic_write_json(contract_path, contract)
    
    # Archive proposal
    archive_dir = handoff_dir / "archive"
    archive_file(proposal_path, archive_dir, suffix=contract["task_id"])
    
    return contract_path
