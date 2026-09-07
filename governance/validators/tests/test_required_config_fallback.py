"""SF003's intentionally bounded syntax and explicit optional-value contracts."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def scanner():
    path = Path(__file__).resolve().parents[1] / "silent-failure-check.py"
    spec = importlib.util.spec_from_file_location("required_config_scanner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("expression", [
    "os.getenv('SERVICE_API_KEY', '')",
    "os.environ.get('SERVICE_API_KEY', '')",
    "os.getenv('SERVICE_API_KEY', default='')",
    "os.getenv('SERVICE_API_KEY') or ''",
    "os.environ.get('SERVICE_API_KEY') or ''",
    "os.getenv('FIRST') or os.getenv('SECOND') or ''",
    "os.getenv('SERVICE_API_KEY', '') or ''",
])
def test_empty_configuration_candidate(scanner, expression):
    findings = scanner.scan_source(f"key = {expression}\n")
    assert [(f["rule"], f["line"], f["column"]) for f in findings] == [("SF003", 1, 1)]


@pytest.mark.parametrize("source", [
    "key = os.environ['SERVICE_API_KEY'] or ''",
    "key = os.getenv('OPTIONAL_FEATURE')",
    "host = os.getenv('HOST', 'localhost')",
    "value = options.get('title', '')",
    "key = os.getenv('SERVICE_API_KEY', '')\nif not key:\n    raise ValueError('missing configuration')",
    "key: str = os.getenv('SERVICE_API_KEY') or ''\nif not key:\n    log()\n    raise ValueError('missing configuration')",
])
def test_required_lookup_optional_none_and_explicit_validation(scanner, source):
    assert scanner.scan_source(source) == []


@pytest.mark.parametrize("guard", [
    "if not other:\n    raise ValueError()",
    "if key:\n    raise ValueError()",
    "if not key:\n    log()",
    "if not key:\n    if condition:\n        raise ValueError()",
    "if not key:\n    return []\n    raise ValueError()",
    "if not key:\n    if alternate:\n        return []\n    raise ValueError()",
])
def test_ineffective_validation_is_not_exempt(scanner, guard):
    assert scanner.scan_source("key = os.getenv('KEY', '')\n" + guard)[0]["rule"] == "SF003"


def test_optional_default_requires_local_rationale(scanner):
    source = "label = os.getenv('OPTIONAL_LABEL', '')  # governance: allow-silent SF003: absent label deliberately renders no suffix\n"
    assert scanner.scan_source(source) == []
    assert scanner.scan_source(source + "key = os.getenv('KEY', '')\n")[0]["line"] == 2


def test_multiline_statement_rationale_and_marker_strings(scanner):
    source = "# governance: allow-silent SF003: optional label has no suffix\nlabel = os.getenv(\n    'LABEL', ''\n)\n"
    assert scanner.scan_source(source) == []
    assert scanner.scan_source("note = '# governance: allow-silent SF003: fake'\nkey = os.getenv('KEY', '')\n")[0]["line"] == 2


def test_handler_rationale_cannot_suppress_configuration(scanner):
    source = "try:\n    query()\nexcept ValueError: # governance: allow-silent SF003: wrong anchor\n    key = os.getenv('KEY', '')\n    raise\n"
    assert scanner.scan_source(source)[0]["rule"] == "SF003"


@pytest.mark.parametrize("value", [
    "Client(api_key=os.getenv('KEY', ''))", "[os.getenv('KEY', '')]",
    "os.getenv('PRIMARY') or Client(os.getenv('KEY', '')) or ''",
    "os.getenv(os.getenv('ENV_NAME', ''), '')",
])
def test_checking_container_or_client_does_not_validate_credential(scanner, value):
    source = f"result = {value}\nif not result:\n    raise ValueError()\n"
    assert scanner.scan_source(source)[0]["rule"] == "SF003"
