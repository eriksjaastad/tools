# Utils package for agent-hub

# Re-export from the utils.py module (which is shadowed by this package)
import sys
from pathlib import Path

# Import from the actual utils.py file
_utils_module_path = Path(__file__).parent.parent / "utils.py"
if _utils_module_path.exists():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_utils_file", _utils_module_path)
    _utils_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_utils_module)

    # Re-export commonly used functions
    safe_read = _utils_module.safe_read
    atomic_write = _utils_module.atomic_write
    atomic_write_json = _utils_module.atomic_write_json
    archive_file = _utils_module.archive_file
    count_lines = _utils_module.count_lines
    get_sha256 = _utils_module.get_sha256
    MODEL_COST_MAP = _utils_module.MODEL_COST_MAP
