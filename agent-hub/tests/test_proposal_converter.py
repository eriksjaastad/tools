import pytest
import json
from pathlib import Path
from src.proposal_converter import parse_proposal, create_contract, convert_proposal, generate_task_id

@pytest.fixture
def sample_proposal_content():
    return """# Proposal: Merge Auth Docs

**Proposed By:** Erik + Claude
**Date:** 2026-01-17
**Target Project:** Agent-Hub
**Complexity:** major

---

## 1. What We're Doing
Merging auth v1 and v2 docs.

## 2. Why It Matters
Documentation is inconsistent.

## 3. Source Files
- `docs/auth_v1.md`
- `docs/auth_v2.md`

## 4. Target Output
- `docs/auth_final.md`

## 5. Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## 6. Acceptance Criteria
- [ ] Criterion 1

## 7. Constraints
- **Allowed paths:** `docs/`, `README.md`
- **Forbidden paths:** `.env`, `AGENTS.md`
- **Deletions allowed:** No
- **Max diff size:** 200 lines

## 8. Notes for Implementer
Be careful.

---

**Erik Approval:** ☐ Approved  
"""

def test_parse_proposal(sample_proposal_content):
    proposal = parse_proposal(sample_proposal_content)
    assert proposal["title"] == "Merge Auth Docs"
    assert proposal["target_project"] == "Agent-Hub"
    assert proposal["complexity"] == "major"
    assert "docs/auth_v1.md" in proposal["source_files"]
    assert proposal["target_file"] == "docs/auth_final.md"
    assert "Requirement 1" in proposal["requirements"]
    assert "Criterion 1" in proposal["acceptance_criteria"]
    assert "docs/" in proposal["constraints"]["allowed_paths"]
    assert ".env" in proposal["constraints"]["forbidden_paths"]
    assert proposal["constraints"]["delete_allowed"] is False

def test_create_contract(sample_proposal_content):
    proposal = parse_proposal(sample_proposal_content)
    contract = create_contract(proposal)
    
    assert contract["schema_version"] == "2.0"
    assert contract["project"] == "Agent-Hub"
    assert contract["complexity"] == "major"
    assert contract["limits"]["cost_ceiling_usd"] == 2.00
    assert contract["specification"]["target_file"] == "docs/auth_final.md"
    assert len(contract["specification"]["requirements"]) == 2

def test_convert_proposal_success(tmp_path, sample_proposal_content):
    handoff_dir = tmp_path / "_handoff"
    handoff_dir.mkdir()
    proposal_path = handoff_dir / "PROPOSAL_FINAL.md"
    proposal_path.write_text(sample_proposal_content)
    
    contract_path = convert_proposal(proposal_path, handoff_dir)
    
    assert contract_path is not None
    assert contract_path.exists()
    assert (handoff_dir / "TASK_CONTRACT.json").exists()
    
    # Check archive
    archive_dir = handoff_dir / "archive"
    assert archive_dir.exists()
    assert len(list(archive_dir.glob("PROPOSAL_FINAL_*.md"))) == 1
    assert not proposal_path.exists()

def test_convert_proposal_rejection(tmp_path):
    handoff_dir = tmp_path / "_handoff"
    handoff_dir.mkdir()
    proposal_path = handoff_dir / "PROPOSAL_FINAL.md"
    # Malformed proposal (missing target file)
    proposal_path.write_text("# Proposal: Broken\n**Target Project:** Test\n## 5. Requirements\n- [ ] Fix it")
    
    contract_path = convert_proposal(proposal_path, handoff_dir)
    
    assert contract_path is None
    assert (handoff_dir / "PROPOSAL_REJECTED.md").exists()
    rejection_content = (handoff_dir / "PROPOSAL_REJECTED.md").read_text()
    assert "Missing target file" in rejection_content

def test_generate_unique_task_ids():
    id1 = generate_task_id("ProjectA", "Title A")
    import time
    time.sleep(1) # Ensure timestamp changes if using it
    id2 = generate_task_id("ProjectA", "Title A")
    assert id1 != id2
