"""Command-line entry point and TOML config loading."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from .runner import OUTPUT_FORMATS, Job, UsageError, run
from .specs import CropSpec, SpecError, build_spec, parse_spec

FORMAT_CHOICES = ("keep", *OUTPUT_FORMATS)
CONFIG_KEYS = {
    "input": str, "output": str, "crop": list, "format": str, "quality": int,
    "recursive": bool, "overwrite": bool, "allow_input_dir": bool,
}
CROP_TABLE_KEYS = {"mode", "value", "anchor", "name"}


class ConfigError(Exception):
    """The config file or the merged settings are invalid."""


def _crop_entry(entry: object, where: str) -> CropSpec:
    if isinstance(entry, str):
        return parse_spec(entry)
    if not isinstance(entry, dict):
        raise ConfigError(f"{where} must be a spec string or a table")
    unknown = set(entry) - CROP_TABLE_KEYS
    if unknown:
        raise ConfigError(f"{where} has unknown key(s): {', '.join(sorted(unknown))}")
    if not all(isinstance(entry.get(k), str) for k in ("mode", "value")):
        raise ConfigError(f"{where} needs string 'mode' and 'value'")
    for key in ("anchor", "name"):
        if key in entry and not isinstance(entry[key], str):
            raise ConfigError(f"{where}.{key} must be a string")
    return build_spec(entry["mode"], entry["value"], entry.get("anchor"), entry.get("name"))


def load_config(path: Path) -> dict:
    """Read a TOML config. Relative paths inside it resolve against its directory."""
    try:
        data = tomllib.loads(path.read_bytes().decode("utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except IsADirectoryError:
        raise ConfigError(f"config path is a directory, not a file: {path}") from None
    except OSError as exc:  # permission denied and other read failures
        raise ConfigError(f"cannot read config file {path}: {exc.strerror or exc}") from None
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{path}: not valid UTF-8 text ({exc.reason} at byte {exc.start})") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML: {exc}") from None
    unknown = set(data) - set(CONFIG_KEYS)
    if unknown:
        raise ConfigError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
    for key, value in data.items():
        if not isinstance(value, CONFIG_KEYS[key]) or (CONFIG_KEYS[key] is int and isinstance(value, bool)):
            raise ConfigError(f"{path}: '{key}' must be of type {CONFIG_KEYS[key].__name__}")
    for key in ("input", "output"):
        if key in data and not Path(data[key]).expanduser().is_absolute():
            data[key] = str(path.parent / data[key])
    if "crop" in data:
        data["crop"] = [_crop_entry(e, f"crop[{i}]") for i, e in enumerate(data["crop"])]
    return data


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="batch-crop",
        description="Crop many images at once. Spec form: MODE:VALUE[@ANCHOR][#NAME]",
        epilog="Modes: aspect:W:H  size:WxH  fill:WxH  box:x1,y1,x2,y2  rel:x1,y1,x2,y2. "
               "Anchors: center, top, bottom, left, right, top-left, ..., or fx,fy.",
    )
    p.add_argument("input", nargs="?", help="input directory, image file, or quoted glob")
    p.add_argument("-o", "--output", help="output directory")
    p.add_argument("-c", "--crop", action="append", metavar="SPEC", help="crop spec (repeatable)")
    p.add_argument("--config", type=Path, help="TOML config file; flags override it")
    p.add_argument("-f", "--format", choices=FORMAT_CHOICES, default=None, help="output format (default keep)")
    p.add_argument("-q", "--quality", type=int, default=None, help="JPEG/WebP quality 1-100 (default 90)")
    p.add_argument("-r", "--recursive", action="store_true", default=None, help="descend into subdirectories")
    p.add_argument("-n", "--dry-run", action="store_true", help="show what would be written; write nothing")
    p.add_argument("--overwrite", action="store_true", default=None, help="replace existing output files")
    p.add_argument("--allow-input-dir", action="store_true", default=None,
                   help="allow outputs beside inputs or where a rerun would find them")
    return p


def build_job(args: argparse.Namespace) -> Job:
    settings = load_config(args.config) if args.config else {}
    for key in ("input", "output", "format", "quality", "recursive", "overwrite", "allow_input_dir"):
        if getattr(args, key) is not None:
            settings[key] = getattr(args, key)
    if args.crop:
        settings["crop"] = [parse_spec(s) for s in args.crop]
    for key in ("input", "output"):
        if not settings.get(key):
            raise ConfigError(f"missing {key} (give it as a flag or in the config file)")
    specs = settings.get("crop") or []
    if not specs:
        raise ConfigError("no crop spec given (use --crop or 'crop' in the config)")
    fmt = settings.get("format", "keep")
    if fmt not in FORMAT_CHOICES:
        raise ConfigError(f"format must be one of {', '.join(FORMAT_CHOICES)}, got {fmt!r}")
    quality = settings.get("quality", 90)
    if not 1 <= quality <= 100:
        raise ConfigError(f"quality must be 1-100, got {quality}")
    if len(specs) > 1:  # several outputs per image need distinct names
        specs = [s if s.name else CropSpec(s.mode, s.value, s.numbers, s.anchor, str(i + 1))
                 for i, s in enumerate(specs)]
    names = [s.name for s in specs]
    if len(set(names)) != len(names):
        raise ConfigError(f"crop names must be unique, got {names}")
    return Job(
        input=settings["input"], output=Path(settings["output"]).expanduser(), specs=specs,
        format=fmt, quality=quality, recursive=bool(settings.get("recursive")),
        dry_run=args.dry_run, overwrite=bool(settings.get("overwrite")),
        allow_input_dir=bool(settings.get("allow_input_dir")),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        job = build_job(args)
        summary = run(job)
    # Per-image failures are handled inside run(); anything reaching here stops the whole job.
    except (ConfigError, SpecError, UsageError, OSError, ValueError) as exc:
        print(f"batch-crop: error: {exc}", file=sys.stderr)
        return 2
    done = f"{summary.planned} planned (dry run)" if job.dry_run else f"{summary.written} written"
    earlier = f", {len(summary.earlier)} skipped (earlier output)" if summary.earlier else ""
    print(f"\nSummary: {done}, {len(summary.failed)} failed, "
          f"{len(summary.skipped)} skipped (unsupported){earlier}")
    for path, msg in summary.failed:
        print(f"  failed: {path}: {msg}", file=sys.stderr)
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
