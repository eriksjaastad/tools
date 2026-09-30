"""Offline positive/negative contracts for the advisory AST scanner (#6900)."""

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from conftest import VALIDATORS_DIR, load_validator


VALIDATOR_PATH = str(Path(VALIDATORS_DIR) / "silent-failure-check.py")


@pytest.fixture(scope="module")
def silent_check():
    return load_validator("silent-failure-check.py")


def handler(body, exception="Exception", comment=""):
    clause = f"except {exception}:" if exception else "except:"
    return "def collect():\n    try:\n        query()\n    " + clause + comment + "\n" + textwrap.indent(body, "        ") + "\n"


@pytest.mark.parametrize("exception", ["", "Exception", "BaseException", "ValueError", "(OSError, ValueError)"])
@pytest.mark.parametrize("body", ["pass", "...", '"cleanup failed"', '"doc"\npass\n...', "None", "42"])
def test_inert_handlers(silent_check, body, exception):
    findings = silent_check.scan_source(handler(body, exception), "example.py")
    assert findings == [{
        "path": "example.py", "line": 4, "column": 5, "rule": "SF001",
        "message": "Exception handler contains only inert statements.",
    }]


@pytest.mark.parametrize("value", ["", "None", "False", "0", "0.0", "0j", "''", "b''", "[]", "{}", "()", "list()", "dict()", "set()", "tuple()", "frozenset()", "str()", "bytes()"])
@pytest.mark.parametrize("exception", ["Exception", "OSError"])
def test_empty_returns_even_with_logging(silent_check, value, exception):
    findings = silent_check.scan_source(handler(f"logger.warning('query failed')\nreturn {value}", exception))
    assert [(item["rule"], item["line"] ) for item in findings] == [("SF002", 6)]


@pytest.mark.parametrize("body", [
    "raise", "raise RuntimeError('query failed') from exc", "return Failure(exc)",
    "return {'error': str(exc)}", "return (None, 'failed')", "return (None, '', 'failed')",
    "return [1]", "return True", "return 2", "return 'error'", "return list(items)",
    "return dict(error=exc)", "recover()", "logger.warning('failed')\nraise",
    "raise\nreturn []", "return Failure(exc)\nreturn []",
    "if condition:\n    raise\nelse:\n    raise\nreturn []",
    "try:\n    return []\nfinally:\n    raise",
    "return [] or Failure(exc)", "return True or []", "return 1 or None",
])
def test_explicit_failures_and_nonempty_results(silent_check, body):
    assert silent_check.scan_source(handler(body)) == []


@pytest.mark.parametrize("body", [
    "if condition:\n    return []\nraise",
    "if condition:\n    raise\nreturn []",
    "while condition:\n    return {}",
    "for item in items:\n    return None",
    "with lock:\n    return False",
    "try:\n    raise\nfinally:\n    return []",
    "match value:\n    case 1:\n        return []",
    "return [] if condition else Failure(exc)",
    "return Failure(exc) if condition else {}",
    "return result or []", "return result and []", "return [] and Failure(exc)",
])
def test_nested_control_flow_defaults(silent_check, body):
    assert [item["rule"] for item in silent_check.scan_source(handler(body))] == ["SF002"]


@pytest.mark.parametrize("definition", [
    "def nested():\n    return []",
    "async def nested():\n    return []",
    "class Nested:\n    def method(self):\n        return []",
    "nested = lambda: []",
])
def test_nested_scope_returns_not_attributed(silent_check, definition):
    assert silent_check.scan_source(handler(definition + "\nraise")) == []


def test_nested_handlers_scanned_once_and_independently(silent_check):
    source = handler("try:\n    cleanup()\nexcept OSError:\n    return []\nraise")
    findings = silent_check.scan_source(source)
    assert [(item["line"], item["rule"]) for item in findings] == [(8, "SF002")]


def test_handler_in_nested_function_still_scanned(silent_check):
    source = handler("def nested():\n    try:\n        query()\n    except ValueError:\n        return []\nraise")
    assert [item["rule"] for item in silent_check.scan_source(source)] == ["SF002"]


@pytest.mark.parametrize("rule,body", [("SF001", "pass"), ("SF002", "return []")])
def test_rule_specific_handler_comment_suppresses(silent_check, rule, body):
    comment = f"  # governance: allow-silent {rule}: missing file means already cleaned"
    assert silent_check.scan_source(handler(body, "FileNotFoundError", comment)) == []
    source = handler(body).replace("    except", f"    # governance: allow-silent {rule}: explicit API contract\n    except")
    assert silent_check.scan_source(source) == []


@pytest.mark.parametrize("comment", [
    "# governance: allow-silent SF001:", "# governance: allow-silent SF001:   ",
    "# governance: allow-silent SF001: ...", "# governance: allow-silent SF002: wrong rule",
    "# governance: allow-silent: blanket", "# governance: allow-silent SF001,SF002: blanket",
])
def test_missing_reason_and_blanket_comments_do_not_suppress(silent_check, comment):
    assert [item["rule"] for item in silent_check.scan_source(handler("pass", comment="  " + comment))] == ["SF001"]


def test_string_and_distant_comment_do_not_suppress(silent_check):
    marker = "# governance: allow-silent SF001: irrelevant"
    source = marker + "\n\n" + handler(repr(marker))
    assert [item["rule"] for item in silent_check.scan_source(source)] == ["SF001"]


def test_trailing_comment_on_previous_statement_does_not_suppress(silent_check):
    source = handler("pass").replace("query()", "query() # governance: allow-silent SF001: unrelated")
    assert [item["rule"] for item in silent_check.scan_source(source)] == ["SF001"]


def test_suppression_cannot_escape_handler(silent_check):
    source = handler("pass", comment=" # governance: allow-silent SF001: cleaned") + handler("pass")
    assert len(silent_check.scan_source(source)) == 1
    source = handler("try:\n    cleanup()\nexcept OSError:\n    pass\nraise", comment=" # governance: allow-silent SF001: outer only")
    assert [item["rule"] for item in silent_check.scan_source(source)] == ["SF001"]


def test_return_line_suppression_does_not_replace_handler_rationale(silent_check):
    source = handler("return [] # governance: allow-silent SF002: not on handler")
    assert [item["rule"] for item in silent_check.scan_source(source)] == ["SF002"]


@pytest.mark.parametrize("rule,body", [("SF001", "pass"), ("SF002", "return []")])
def test_sibling_handler_does_not_inherit_indented_comment(silent_check, rule, body):
    source = (
        "def f():\n    try:\n        work()\n    except OSError:\n"
        "        raise\n"
        f"        # governance: allow-silent {rule}: first handler rationale\n"
        "    except Exception:\n"
        f"        {body}\n"
    )
    assert [item["rule"] for item in silent_check.scan_source(source)] == [rule]


@pytest.mark.parametrize("finalbody", ["raise", "raise RuntimeError('failed')", "return Failure(exc)", "if condition:\n    raise\nelse:\n    raise"])
def test_containing_finally_overrides_handler_return(silent_check, finalbody):
    source = (
        "def f():\n    try:\n        work()\n    except OSError:\n        return []\n    finally:\n"
        + textwrap.indent(finalbody, "        ") + "\n"
    )
    assert silent_check.scan_source(source) == []
    source = handler("try:\n    cleanup()\nexcept OSError:\n    return []\nfinally:\n" + textwrap.indent(finalbody, "    "))
    assert silent_check.scan_source(source) == []


@pytest.mark.parametrize("finalbody", ["return []", "return None", "if condition:\n    raise\nelse:\n    return {}"])
def test_overriding_finally_default_is_reported_once(silent_check, finalbody):
    source = handler("try:\n    cleanup()\nexcept OSError:\n    return []\nfinally:\n" + textwrap.indent(finalbody, "    "))
    findings = silent_check.scan_source(source)
    assert len(findings) == 1
    assert findings[0]["rule"] == "SF002"
    assert findings[0]["line"] > 9


def test_top_level_try_handler_finally_empty_override(silent_check):
    source = "def f():\n    try:\n        work()\n    except OSError:\n        return Failure(exc)\n    finally:\n        return []\n"
    findings = silent_check.scan_source(source)
    assert [(item["line"], item["rule"]) for item in findings] == [(7, "SF002")]


def test_handler_rationale_does_not_suppress_external_finally(silent_check):
    source = "def f():\n    try:\n        work()\n    except OSError: # governance: allow-silent SF002: intentional cache miss\n        return None\n    finally:\n        return []\n"
    assert [(item["line"], item["rule"]) for item in silent_check.scan_source(source)] == [(7, "SF002")]


def test_finally_uses_its_actual_enclosing_handler_rationale(silent_check):
    body = "try:\n    cleanup()\nexcept OSError: # governance: allow-silent SF002: inner only\n    return None\nfinally:\n    return []"
    assert [item["rule"] for item in silent_check.scan_source(handler(body))] == ["SF002"]
    assert silent_check.scan_source(handler(body, comment=" # governance: allow-silent SF002: outer cleanup contract")) == []


def test_finally_in_enclosing_function_does_not_mask_nested_scope(silent_check):
    source = "def f():\n    try:\n        def nested():\n            try:\n                work()\n            except OSError:\n                return []\n    finally:\n        raise\n"
    assert [item["rule"] for item in silent_check.scan_source(source)] == ["SF002"]


def test_outer_finally_overrides_inner_finally_default(silent_check):
    source = "def f():\n    try:\n        try:\n            work()\n        except OSError:\n            return []\n        finally:\n            return {}\n    finally:\n        raise\n"
    assert silent_check.scan_source(source) == []


@pytest.mark.parametrize("value", ["[*[]] or []", "{**{}} or []", "(*[],) or []", "{*[]} or []"])
def test_unpack_only_display_truth_is_not_assumed(silent_check, value):
    assert [item["rule"] for item in silent_check.scan_source(handler(f"return {value}"))] == ["SF002"]


@pytest.mark.parametrize("value", ["[1, *items] or []", "{'error': exc, **details} or []", "(1, *items) or []", "{1, *items} or []"])
def test_explicit_display_members_guarantee_truth(silent_check, value):
    assert silent_check.scan_source(handler(f"return {value}")) == []


def test_required_env_empty_fallback_does_not_hide_key_error(silent_check):
    source = "key = os.environ['REQUIRED_KEY'] or ''\n"
    assert silent_check.scan_source(source) == []


@pytest.mark.parametrize("source", [
    "key = os.getenv('OPTIONAL_KEY')", "key = os.environ.get('OPTIONAL_KEY')",
    "key = os.environ['REQUIRED_KEY']", "key = os.environ['KEY'] or 'valid-default'",
    "value = options.get('title', '')", "value = thing['KEY'] or ''",
    "value = os.environ[dynamic_key] or ''",
    "key = os.getenv('KEY', '')\nif not key:\n    raise RuntimeError('missing')",
])
def test_optional_defaults_and_other_subscripts_not_flagged(silent_check, source):
    assert silent_check.scan_source(source) == []


def test_try_star_and_unicode_positions(silent_check):
    source = "try:\n    query()\nexcept* ValueError:\n    pass\n"
    assert [item["rule"] for item in silent_check.scan_source(source)] == ["SF001"]
    source = handler("name = 'é'; return []")
    findings = silent_check.scan_source(source)
    assert findings[0]["column"] == len("        name = 'é'; ".encode()) + 1


def test_api_raises_on_malformed_source(silent_check):
    with pytest.raises(SyntaxError):
        silent_check.scan_source("try:\n    broken(")


def test_scan_file_encoding_and_non_python(silent_check, tmp_path):
    path = tmp_path / "latin.py"
    path.write_bytes(("# coding: latin-1\n# café\n" + handler("pass")).encode("latin-1"))
    assert silent_check.scan_file(path)[0]["rule"] == "SF001"
    assert silent_check.scan_file(tmp_path / "unreadable.json") == []
    assert silent_check.scan_file(tmp_path) == []
    with pytest.raises(FileNotFoundError):
        silent_check.scan_file(tmp_path / "missing.py")


def run_cli(*args, expected=0):
    command = [sys.executable, VALIDATOR_PATH, *map(str, args)]
    if expected:
        with pytest.raises(subprocess.CalledProcessError) as failure:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        assert failure.value.returncode == expected
        return failure.value.stdout, failure.value.stderr
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    return result.stdout, result.stderr


def test_cli_clean_findings_and_dry_run(tmp_path):
    clean, dirty = tmp_path / "clean.py", tmp_path / "dirty.py"
    clean.write_text(handler("raise"))
    dirty.write_text(handler("logger.warning('failed')\nreturn []"))
    assert run_cli(clean) == ("", "")
    stdout, stderr = run_cli(dirty, expected=1)
    assert "SF002" in stdout and stderr == ""
    normal, _ = run_cli("--json", dirty, expected=1)
    dry, _ = run_cli("--json", "--dry-run", dirty)
    assert normal == dry
    assert json.loads(dry)["errors"] == []


@pytest.mark.parametrize("kind", ["missing", "syntax", "encoding", "directory"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_cli_scan_errors_never_become_clean(tmp_path, kind, dry_run):
    path = tmp_path / "bad.py"
    if kind == "syntax":
        path.write_text("secret_do_not_echo = 'private-value\n")
    elif kind == "encoding":
        path.write_bytes(b"secret_do_not_echo = '\xff'")
    elif kind == "directory":
        path.mkdir()
    args = ["--json", path]
    if dry_run:
        args.insert(0, "--dry-run")
    stdout, stderr = run_cli(*args, expected=2)
    report = json.loads(stdout)
    assert len(report["errors"]) == 1
    assert report["findings"] == []
    assert "secret_do_not_echo" not in stdout + stderr
    assert "private-value" not in stdout + stderr


def test_cli_reports_findings_alongside_errors_deterministically(tmp_path):
    first, second, missing = (tmp_path / name for name in ("a.py", "b.py", "missing.py"))
    first.write_text(handler("pass"))
    second.write_text(handler("return []"))
    output, _ = run_cli("--json", "--dry-run", second, missing, first, second, expected=2)
    repeat, _ = run_cli("--json", "--dry-run", first, second, missing, expected=2)
    assert output == repeat
    assert [item["path"] for item in json.loads(output)["findings"]] == [str(first), str(second)]


def test_cli_requires_explicit_paths_and_does_not_recurse(tmp_path):
    run_cli(expected=2)
    (tmp_path / "dirty.py").write_text(handler("pass"))
    assert run_cli(tmp_path, tmp_path / "missing.json") == ("", "")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Platform lacks FIFOs")
def test_cli_rejects_fifo_before_open(tmp_path):
    path = tmp_path / "stream.py"
    os.mkfifo(path)
    stdout, _ = run_cli("--json", "--dry-run", path, expected=2)
    report = json.loads(stdout)
    assert report["errors"][0]["error"] == "OSError"
    assert report["findings"] == []


# --- Changed-lines mode (--staged / --base) --------------------------------

HISTORICAL = handler("logger.warning('failed')\nreturn []") + "\nVALUE = 1\n"


def rules(findings):
    return [(item["line"], item["rule"]) for item in findings]


def test_untouched_historical_finding_does_not_block_unrelated_edit(silent_check):
    after = HISTORICAL.replace("VALUE = 1", "VALUE = 2")
    assert silent_check.changed_findings(HISTORICAL, after, "m.py") == []


def test_moved_historical_finding_does_not_block(silent_check):
    after = "import logging\n\n\n" + HISTORICAL
    assert silent_check.changed_findings(HISTORICAL, after, "m.py") == []


def test_editing_the_flagged_line_blocks(silent_check):
    after = HISTORICAL.replace("return []", "return {}")
    assert rules(silent_check.changed_findings(HISTORICAL, after, "m.py")) == [(6, "SF002")]


def test_new_finding_blocks_beside_untouched_historical_one(silent_check):
    after = HISTORICAL + "\n" + handler("pass").replace("collect", "other")
    assert [rule for _, rule in rules(silent_check.changed_findings(HISTORICAL, after, "m.py"))] == ["SF001"]


def test_deleting_a_raise_that_leaves_an_inert_handler_blocks(silent_check):
    before = handler("pass\nraise")
    after = handler("pass")
    assert rules(silent_check.changed_findings(before, after, "m.py")) == [(4, "SF001")]


def test_deleting_a_rationale_comment_blocks(silent_check):
    comment = "    # governance: allow-silent SF001: best-effort cleanup of a disposable file\n"
    before = "def clean():\n    try:\n        remove()\n" + comment + "    except OSError:\n        pass\n"
    after = before.replace(comment, "")
    assert silent_check.scan_source(before) == []
    assert [rule for _, rule in rules(silent_check.changed_findings(before, after, "m.py"))] == ["SF001"]


def test_new_empty_env_fallback_blocks_and_historical_one_does_not(silent_check):
    before = 'import os\nTOKEN = os.getenv("TOKEN", "")\n'
    assert silent_check.changed_findings(before, before + "DEBUG = True\n", "m.py") == []
    after = before + 'KEY = os.environ.get("KEY") or ""\n'
    assert rules(silent_check.changed_findings(before, after, "m.py")) == [(3, "SF003")]


def test_unparseable_before_gives_no_baseline(silent_check):
    assert rules(silent_check.changed_findings("broken = (\n", HISTORICAL, "m.py")) == [(6, "SF002")]


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
    subprocess.run(["git", "init", "-q", str(root)], env=env, check=True, timeout=10)
    return root, env


def git_in(repo, *args):
    root, env = repo
    return subprocess.run(["git", *args], cwd=root, env=env, check=True,
                          capture_output=True, text=True, timeout=10).stdout


def stage_in(repo, name, text):
    (repo[0] / name).write_text(text)
    git_in(repo, "add", name)


def changed_cli(repo, *args):
    root, env = repo
    return subprocess.run([sys.executable, VALIDATOR_PATH, *args], cwd=root, env=env,
                          capture_output=True, text=True, timeout=30)


def test_staged_mode_blocks_new_and_passes_historical(repo):
    stage_in(repo, "m.py", HISTORICAL)
    first = changed_cli(repo, "--staged")
    assert first.returncode == 1 and "m.py:6:" in first.stdout and "SF002" in first.stdout
    git_in(repo, "commit", "-qm", "historical baseline")
    stage_in(repo, "m.py", HISTORICAL.replace("VALUE = 1", "VALUE = 2"))
    assert changed_cli(repo, "--staged").returncode == 0


def test_staged_mode_reads_the_index_not_the_worktree(repo):
    stage_in(repo, "m.py", "VALUE = 1\n")
    (repo[0] / "m.py").write_text(handler("pass"))
    assert changed_cli(repo, "--staged").returncode == 0
    stage_in(repo, "clean.py", "VALUE = 1\n")
    git_in(repo, "add", "m.py")
    assert changed_cli(repo, "--staged").returncode == 1


def test_staged_mode_path_filter_and_non_python(repo):
    stage_in(repo, "m.py", handler("pass"))
    stage_in(repo, "notes.txt", "except: pass\n")
    assert changed_cli(repo, "--staged", "notes.txt", "other.py").returncode == 0
    assert changed_cli(repo, "--staged", "notes.txt", "m.py").returncode == 1


def test_pure_rename_of_historical_findings_passes(repo):
    stage_in(repo, "old name.py", HISTORICAL)
    git_in(repo, "commit", "-qm", "historical baseline")
    git_in(repo, "mv", "old name.py", "new name.py")
    assert changed_cli(repo, "--staged").returncode == 0


def test_base_mode_checks_committed_changes(repo):
    stage_in(repo, "m.py", HISTORICAL)
    git_in(repo, "commit", "-qm", "historical baseline")
    base = git_in(repo, "rev-parse", "HEAD").strip()
    stage_in(repo, "m.py", HISTORICAL.replace("VALUE = 1", "VALUE = 2"))
    git_in(repo, "commit", "-qm", "unrelated edit")
    assert changed_cli(repo, "--base", base).returncode == 0
    stage_in(repo, "m.py", HISTORICAL + "\n" + handler("return None").replace("collect", "other"))
    git_in(repo, "commit", "-qm", "new silent handler")
    result = changed_cli(repo, "--base", base, "--json")
    assert result.returncode == 1
    assert [item["rule"] for item in json.loads(result.stdout)["findings"]] == ["SF002"]


def test_changed_mode_parse_error_is_an_error_without_source_leak(repo):
    stage_in(repo, "m.py", "secret_do_not_echo = ('private-value'\n")
    for args in (["--staged"], ["--staged", "--dry-run", "--json"]):
        result = changed_cli(repo, *args)
        assert result.returncode == 2
        assert "secret_do_not_echo" not in result.stdout + result.stderr
        assert "private-value" not in result.stdout + result.stderr


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="Platform lacks symlinks")
def test_changed_mode_skips_symlinked_python(repo):
    stage_in(repo, "real.txt", handler("pass"))
    os.symlink("real.txt", repo[0] / "link.py")
    git_in(repo, "add", "link.py")
    assert changed_cli(repo, "--staged").returncode == 0


def test_changed_mode_outside_git_fails_closed(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CEILING_DIRECTORIES"] = str(tmp_path)
    result = subprocess.run([sys.executable, VALIDATOR_PATH, "--staged"], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert "Unable to read changed Git source" in result.stderr


def test_staged_and_base_are_exclusive(repo):
    assert changed_cli(repo, "--staged", "--base", "HEAD").returncode == 2


def test_staged_merge_ignores_findings_brought_in_from_the_other_parent(repo):
    stage_in(repo, "base.py", "VALUE = 1\n")
    git_in(repo, "commit", "-qm", "base")
    trunk = git_in(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    git_in(repo, "checkout", "-qb", "feature")
    stage_in(repo, "feature.py", "FEATURE = 1\n")
    git_in(repo, "commit", "-qm", "feature work")
    git_in(repo, "checkout", "-q", trunk)
    stage_in(repo, "incoming.py", HISTORICAL)
    git_in(repo, "commit", "-qm", "someone else's silent handler")
    git_in(repo, "checkout", "-q", "feature")
    git_in(repo, "merge", "--no-commit", "--no-ff", trunk)
    assert changed_cli(repo, "--staged").returncode == 0
    stage_in(repo, "incoming.py", HISTORICAL + "\n" + handler("pass").replace("collect", "resolved"))
    result = changed_cli(repo, "--staged", "--json")
    assert result.returncode == 1
    assert [item["rule"] for item in json.loads(result.stdout)["findings"]] == ["SF001"]


# Review round 1 on 0c4b06f: a finding is governed by its handler, and
# explicit filters name files however the caller spells them.

BROAD = handler("logger.warning('failed')\nreturn []", "ValueError") + "\nVALUE = 1\n"


def test_broadening_the_handler_clause_blocks(silent_check):
    after = BROAD.replace("except ValueError:", "except Exception:")
    assert rules(silent_check.changed_findings(BROAD, after, "m.py")) == [(6, "SF002")]


def test_deleting_a_guard_inside_the_handler_blocks(silent_check):
    before = handler("if fatal():\n    raise\nreturn []")
    after = handler("return []")
    assert [rule for _, rule in rules(silent_check.changed_findings(before, after, "m.py"))] == ["SF002"]


def test_edit_in_the_try_body_does_not_touch_the_handler_finding(silent_check):
    after = BROAD.replace("query()", "query(timeout=5)")
    assert silent_check.changed_findings(BROAD, after, "m.py") == []


def test_finally_override_is_governed_by_its_handler(silent_check):
    before = ("def f():\n    try:\n        work()\n    except OSError:\n        return Failure(exc)\n"
              "    finally:\n        return []\n")
    after = before.replace("except OSError:", "except Exception:")
    assert rules(silent_check.scan_source(before)) == [(7, "SF002")]
    assert silent_check.changed_findings(before, before, "m.py") == []
    assert [rule for _, rule in rules(silent_check.changed_findings(before, after, "m.py"))] == ["SF002"]


@pytest.mark.parametrize("spelling", ["./pkg/m.py", "pkg/../pkg/m.py", "ABSOLUTE"])
def test_explicit_filter_spellings_select_the_staged_file(repo, spelling):
    (repo[0] / "pkg").mkdir()
    stage_in(repo, "pkg/m.py", handler("pass"))
    if spelling == "ABSOLUTE":
        spelling = str(repo[0] / "pkg" / "m.py")
    assert changed_cli(repo, "--staged", spelling).returncode == 1


def test_filter_relative_to_a_subdirectory(repo):
    (repo[0] / "pkg").mkdir()
    stage_in(repo, "pkg/m.py", handler("pass"))
    root, env = repo
    result = subprocess.run([sys.executable, VALIDATOR_PATH, "--staged", "m.py"], cwd=root / "pkg",
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1


def test_filter_matching_nothing_checks_nothing(repo, tmp_path):
    stage_in(repo, "m.py", handler("pass"))
    assert changed_cli(repo, "--staged", str(tmp_path / "elsewhere.py")).returncode == 0
    assert changed_cli(repo, "--staged").returncode == 1
