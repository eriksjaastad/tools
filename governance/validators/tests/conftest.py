"""Shared loader for the governance validators.

The validators are executable scripts whose filenames contain hyphens
(`source-deletion-check.py`), so they cannot be imported by module name. Load
them through importlib instead.

All validator test modules share this helper rather than each carrying a copy.
"""
import importlib.util
import os
import sys

VALIDATORS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)


def load_validator(filename: str):
    """Import a hyphenated validator script as a module.

    `filename` is the script's basename, e.g. "source-deletion-check.py".
    """
    path = os.path.join(VALIDATORS_DIR, filename)
    module_name = os.path.basename(filename)[: -len(".py")].replace("-", "_")

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load validator from {path}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod

