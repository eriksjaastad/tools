"""Offline regressions for the token cache introduced and hardened in #6781."""

import importlib.util
import json
import os
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest


REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)


@pytest.fixture
def token_module(tmp_path, monkeypatch):
    """Isolate the cache from installed credentials and external services."""
    spec = importlib.util.spec_from_file_location(
        "github_app_token_test", REPO / "github-app-token.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "CACHE_DIR", tmp_path / "cache")

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz)

    def forbidden(*args, **kwargs):
        pytest.fail("Authentication tests must not fetch credentials or call providers")

    monkeypatch.setattr(module, "datetime", FrozenDatetime)
    monkeypatch.setattr(module, "mint_token", forbidden)
    monkeypatch.setattr(module.subprocess, "run", forbidden)
    monkeypatch.setattr(module.urllib.request, "urlopen", forbidden)
    return module


def write_entry(module, **overrides):
    entry = {
        "token": "offline-test-token",
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        "config": module._config_fingerprint("manager"),
    }
    entry.update(overrides)
    module.CACHE_DIR.mkdir(exist_ok=True)
    module._cache_path("manager").write_text(json.dumps(entry))
    return entry


def test_cache_hit_skips_minting(token_module):
    write_entry(token_module)
    assert token_module.generate_token("manager") == "offline-test-token"


@pytest.mark.parametrize("seconds,hit", [(301, True), (300, False), (299, False), (0, False), (-1, False)])
def test_expiry_safety_boundary(token_module, seconds, hit):
    write_entry(token_module, expires_at=(NOW + timedelta(seconds=seconds)).isoformat())
    expected = "offline-test-token" if hit else None
    assert token_module._read_cached_token("manager") == expected


def test_utc_z_expiry_is_supported(token_module):
    write_entry(token_module, expires_at="2026-09-06T13:00:00Z")
    assert token_module._read_cached_token("manager") == "offline-test-token"


@pytest.mark.parametrize("contents", ["{invalid", "", '{"expires_at": "invalid"}', "{}"])
def test_invalid_cache_is_a_miss(token_module, contents):
    token_module.CACHE_DIR.mkdir()
    token_module._cache_path("manager").write_text(contents)
    assert token_module._read_cached_token("manager") is None


@pytest.mark.parametrize("field", ["token", "expires_at", "config"])
def test_missing_fields_are_a_miss(token_module, field):
    entry = write_entry(token_module)
    del entry[field]
    token_module._cache_path("manager").write_text(json.dumps(entry))
    assert token_module._read_cached_token("manager") is None


@pytest.mark.parametrize("token", ["", None])
def test_empty_token_is_a_miss(token_module, token):
    write_entry(token_module, token=token)
    assert token_module._read_cached_token("manager") is None


@pytest.mark.parametrize("entry", [None, [], ["token"], 42, -42, True, "not an object"])
def test_non_object_cache_entries_are_misses(token_module, entry):
    token_module.CACHE_DIR.mkdir()
    token_module._cache_path("manager").write_text(json.dumps(entry))
    assert token_module._read_cached_token("manager") is None


@pytest.mark.parametrize("expiry", [None, 42, -42, True, [], {}])
def test_non_string_cache_expiry_is_a_miss(token_module, expiry):
    write_entry(token_module, expires_at=expiry)
    assert token_module._read_cached_token("manager") is None


@pytest.mark.parametrize("expiry", ["2099-01-01T00:00:00", "2099-01-01", "2099-01-01 00:00:00"])
def test_timezone_naive_cache_expiry_is_a_miss(token_module, expiry):
    write_entry(token_module, expires_at=expiry)
    assert token_module._read_cached_token("manager") is None


@pytest.mark.parametrize("token", [42, -42, True, ["token"], {"value": "token"}, " ", "\t\n"])
def test_non_string_or_blank_cached_token_is_a_miss(token_module, token):
    write_entry(token_module, token=token)
    assert token_module._read_cached_token("manager") is None


@pytest.mark.parametrize(
    "corruption",
    ["array", "null", "numeric-expiry", "naive-expiry", "numeric-token", "blank-token"],
)
def test_malformed_cache_remints_once_then_reuses_replacement(token_module, monkeypatch, capsys, corruption):
    entry = write_entry(token_module)
    if corruption == "array":
        entry = []
    elif corruption == "null":
        entry = None
    elif corruption == "numeric-expiry":
        entry["expires_at"] = 42
    elif corruption == "naive-expiry":
        entry["expires_at"] = "2099-01-01T00:00:00"
    elif corruption == "numeric-token":
        entry["token"] = 42
    else:
        entry["token"] = " \t\n"
    token_module._cache_path("manager").write_text(json.dumps(entry))
    mint = Mock(return_value=("new-offline-token", "2026-09-06T13:00:00Z"))
    monkeypatch.setattr(token_module, "mint_token", mint)

    assert token_module.generate_token("manager") == "new-offline-token"
    assert token_module.generate_token("manager") == "new-offline-token"
    mint.assert_called_once_with("manager")
    assert json.loads(token_module._cache_path("manager").read_text())["token"] == "new-offline-token"
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_missing_file_is_a_miss(token_module):
    assert token_module._read_cached_token("manager") is None


def test_unknown_identity_fails_before_credentials_or_cache(token_module, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["github-app-token.py", "claude", "--bundle"])
    with pytest.raises(SystemExit) as error:
        token_module.main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert "Unknown identity 'claude'" in captured.err
    assert captured.out == ""
    assert not token_module.CACHE_DIR.exists()


def test_unreadable_file_is_a_miss(token_module, monkeypatch):
    def unreadable(*args, **kwargs):
        raise PermissionError("offline simulated unreadable cache")

    monkeypatch.setattr(Path, "open", unreadable)
    assert token_module._read_cached_token("manager") is None


@pytest.mark.parametrize("index", [0, 1, 2])
def test_identity_configuration_drift_invalidates_cache(token_module, monkeypatch, index):
    write_entry(token_module)
    changed = list(token_module.IDENTITY_MAP["manager"])
    changed[index] += "-changed"
    monkeypatch.setitem(token_module.IDENTITY_MAP, "manager", tuple(changed))
    assert token_module._read_cached_token("manager") is None


def test_cache_miss_mints_and_reuses_token(token_module, monkeypatch):
    mint = Mock(return_value=("new-offline-token", "2026-09-06T13:00:00Z"))
    monkeypatch.setattr(token_module, "mint_token", mint)
    assert token_module.generate_token("manager") == "new-offline-token"
    assert token_module.generate_token("manager") == "new-offline-token"
    mint.assert_called_once_with("manager")


def test_no_cache_bypasses_read_and_write(token_module, monkeypatch):
    write_entry(token_module)
    mint = Mock(return_value=("new-offline-token", "2026-09-06T13:00:00Z"))
    monkeypatch.setattr(token_module, "mint_token", mint)
    assert token_module.generate_token("manager", use_cache=False) == "new-offline-token"
    assert token_module._read_cached_token("manager") == "offline-test-token"
    mint.assert_called_once_with("manager")


def test_missing_expiry_does_not_write_cache(token_module, monkeypatch):
    monkeypatch.setattr(token_module, "mint_token", Mock(return_value=("offline-token", None)))
    assert token_module.generate_token("manager") == "offline-token"
    assert not token_module.CACHE_DIR.exists()


@pytest.mark.parametrize("existing_directory", [False, True])
def test_cache_permissions_are_private(token_module, existing_directory):
    if existing_directory:
        token_module.CACHE_DIR.mkdir(mode=0o755)
        token_module.CACHE_DIR.chmod(0o755)
        token_module._cache_path("manager").write_text("stale")
        token_module._cache_path("manager").chmod(0o644)
    token_module._write_cached_token("manager", "offline-token", "2026-09-06T13:00:00Z")
    assert stat.S_IMODE(token_module.CACHE_DIR.stat().st_mode) == 0o700
    assert stat.S_IMODE(token_module._cache_path("manager").stat().st_mode) == 0o600


@pytest.mark.parametrize("position", ["temporary", "destination"])
def test_preplanted_symlink_target_is_untouched(token_module, tmp_path, position):
    token_module.CACHE_DIR.mkdir()
    victim = tmp_path / "unrelated-file"
    victim.write_text("preserve me")
    cache_path = token_module._cache_path("manager")
    link = cache_path.with_suffix(f".{os.getpid()}.tmp") if position == "temporary" else cache_path
    link.symlink_to(victim)
    token_module._write_cached_token("manager", "offline-token", "2026-09-06T13:00:00Z")
    assert victim.read_text() == "preserve me"
    assert not cache_path.is_symlink()
    assert token_module._read_cached_token("manager") == "offline-token"
    assert not list(token_module.CACHE_DIR.glob("*.tmp"))


def test_symlink_created_during_temp_open_is_not_followed(token_module, tmp_path, monkeypatch, capsys):
    victim = tmp_path / "unrelated-file"
    victim.write_text("preserve me")
    real_open = os.open

    def plant_link(path, flags, mode):
        Path(path).symlink_to(victim)
        return real_open(path, flags, mode)

    monkeypatch.setattr(token_module.os, "open", plant_link)
    token_module._write_cached_token("manager", "offline-token", "2026-09-06T13:00:00Z")
    assert victim.read_text() == "preserve me"
    assert not token_module._cache_path("manager").exists()
    assert "Warning: could not cache token" in capsys.readouterr().err


def test_cache_write_failure_warns_and_still_returns_minted_token(token_module, monkeypatch, capsys):
    token_module.CACHE_DIR.write_text("not a directory")
    monkeypatch.setattr(token_module, "mint_token", Mock(return_value=("offline-token", "2026-09-06T13:00:00Z")))
    assert token_module.generate_token("manager") == "offline-token"
    stderr = capsys.readouterr().err
    assert "Warning: could not cache token" in stderr
    assert "offline-token" not in stderr


def test_concurrent_process_writers_publish_complete_private_entries(tmp_path):
    # Separate processes are essential: production temporary names are PID-based.
    cache_dir = tmp_path / "cache"
    worker = """
import importlib.util
import json
import stat
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('token_cache_worker', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.CACHE_DIR = Path(sys.argv[2])
def forbidden(*args, **kwargs):
    raise AssertionError('offline worker attempted external authentication')
module.mint_token = forbidden
module.subprocess.run = forbidden
module.urllib.request.urlopen = forbidden
for iteration in range(30):
    module._write_cached_token('manager', 'offline-' + sys.argv[3], '2099-01-01T00:00:00Z')
    path = module._cache_path('manager')
    entry = json.loads(path.read_text())
    assert entry['token'] in {'offline-' + str(index) for index in range(6)}
    assert entry['expires_at'] == '2099-01-01T00:00:00Z'
    assert entry['config'] == module._config_fingerprint('manager')
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
"""

    def run_writer(index):
        return subprocess.run(
            [sys.executable, "-c", worker, str(REPO / "github-app-token.py"), str(cache_dir), str(index)],
            capture_output=True, text=True, check=True, timeout=30,
        )

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(run_writer, range(6)))
    assert all(result.stderr == "" for result in results)
    assert stat.S_IMODE(cache_dir.stat().st_mode) == 0o700
    assert not list(cache_dir.glob("*.tmp"))
    assert json.loads((cache_dir / "manager.json").read_text())["token"].startswith("offline-")
