import pytest
from pathlib import Path
import json
from src.validators import validate_contract, load_and_validate, ContractValidationError

@pytest.fixture
def valid_contract():
    return {
        "schema_version": "2.0",
        "task_id": "TEST-001",
        "project": "TestProject",
        "status": "pending_implementer",
        "complexity": "minor",
        "specification": {
            "target_file": "src/main.py",
            "requirements": ["Implement feature X"]
        },
        "constraints": {
            "allowed_paths": ["src/"],
            "forbidden_paths": ["secrets/"]
        }
    }

def test_valid_contract(valid_contract):
    is_valid, errors = validate_contract(valid_contract)
    assert is_valid
    assert not errors

def test_missing_task_id(valid_contract):
    del valid_contract["task_id"]
    is_valid, errors = validate_contract(valid_contract)
    assert not is_valid
    assert any("task_id" in err for err in errors)

def test_invalid_status(valid_contract):
    valid_contract["status"] = "invalid_status"
    is_valid, errors = validate_contract(valid_contract)
    assert not is_valid
    assert any("status" in err for err in errors)

def test_path_conflict(valid_contract):
    valid_contract["constraints"]["forbidden_paths"] = ["src/"]
    is_valid, errors = validate_contract(valid_contract)
    assert not is_valid
    assert any("both allowed and forbidden" in err for err in errors)

def test_empty_requirements(valid_contract):
    valid_contract["specification"]["requirements"] = []
    is_valid, errors = validate_contract(valid_contract)
    assert not is_valid
    assert any(k in err.lower() for k in ["requirements", "too short", "fewer than", "non-empty"] for err in errors)

def test_wrong_schema_version(valid_contract):
    valid_contract["schema_version"] = "1.0"
    is_valid, errors = validate_contract(valid_contract)
    assert not is_valid
    # jsonschema message for const usually contains the expected value or property name
    assert any("schema_version" in err.lower() or "2.0" in err.lower() for err in errors)

def test_load_and_validate(tmp_path, valid_contract):
    contract_file = tmp_path / "contract.json"
    with open(contract_file, "w") as f:
        json.dump(valid_contract, f)
        
    loaded = load_and_validate(contract_file)
    assert loaded == valid_contract

def test_load_and_validate_failure(tmp_path, valid_contract):
    contract_file = tmp_path / "invalid_contract.json"
    valid_contract["status"] = "broken"
    with open(contract_file, "w") as f:
        json.dump(valid_contract, f)
        
    with pytest.raises(ContractValidationError):
        load_and_validate(contract_file)
