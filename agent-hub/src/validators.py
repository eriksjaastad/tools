import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import jsonschema
from jsonschema import validate

VALID_STATUSES = [
    "pending_implementer",
    "implementation_in_progress",
    "pending_local_review",
    "pending_judge_review",
    "judge_review_in_progress",
    "review_complete",
    "pending_rebuttal",
    "merged",
    "timeout_implementer",
    "timeout_judge",
    "erik_consultation"
]

VALID_COMPLEXITIES = ["trivial", "minor", "major", "critical"]

CONTRACT_SCHEMA = {
    "type": "object",
    "required": [
        "schema_version",
        "task_id",
        "project",
        "status",
        "complexity",
        "specification"
    ],
    "properties": {
        "schema_version": {"const": "2.0"},
        "task_id": {"type": "string", "minLength": 1},
        "project": {"type": "string", "minLength": 1},
        "status": {"type": "string", "enum": VALID_STATUSES},
        "complexity": {"type": "string", "enum": VALID_COMPLEXITIES},
        "specification": {
            "type": "object",
            "required": ["target_file", "requirements"],
            "properties": {
                "target_file": {"type": "string", "minLength": 1},
                "requirements": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"}
                }
            }
        },
        "constraints": {
            "type": "object",
            "properties": {
                "allowed_paths": {"type": "array", "items": {"type": "string"}},
                "forbidden_paths": {"type": "array", "items": {"type": "string"}}
            }
        }
    }
}

class ContractValidationError(Exception):
    """Raised when a contract fails validation."""
    pass

def validate_contract(contract: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Returns (is_valid, list_of_errors)
    Checks required fields exist, status/complexity values, and path conflicts.
    """
    errors = []
    
    # 1. JSON Schema Validation
    try:
        validate(instance=contract, schema=CONTRACT_SCHEMA)
    except jsonschema.ValidationError as e:
        errors.append(f"Schema validation error: {e.message}")
        # If schema validation fails, return early because further checks might fail
        return False, errors

    # 2. Path Overlap Check
    constraints = contract.get("constraints", {})
    allowed = set(constraints.get("allowed_paths", []))
    forbidden = set(constraints.get("forbidden_paths", []))
    overlap = allowed.intersection(forbidden)
    if overlap:
        errors.append(f"Paths cannot be in both allowed and forbidden: {list(overlap)}")

    is_valid = len(errors) == 0
    return is_valid, errors

def load_and_validate(path: Path) -> Dict[str, Any]:
    """
    Loads JSON from file and validates schema.
    Raises ContractValidationError if invalid.
    """
    if not path.exists():
        raise ContractValidationError(f"Contract file not found: {path}")
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            contract = json.load(f)
    except json.JSONDecodeError as e:
        raise ContractValidationError(f"Invalid JSON in contract: {e}")
        
    is_valid, errors = validate_contract(contract)
    if not is_valid:
        raise ContractValidationError(f"Contract validation failed: {'; '.join(errors)}")
        
    return contract
