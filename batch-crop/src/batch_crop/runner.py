"""Find input images, crop them, and write the results safely."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps

from .specs import CropSpec, compute_crop

EXT_FORMAT = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP",
    ".tif": "TIFF", ".tiff": "TIFF", ".bmp": "BMP", ".gif": "GIF",
}
OUTPUT_FORMATS = {"jpeg": ("JPEG", ".jpg"), "png": ("PNG", ".png"), "webp": ("WEBP", ".webp")}
GLOB_CHARS = "*?["
RGB_MODES = {"RGB", "RGBA", "RGBX", "P", "PA"}


class UsageError(Exception):
    """The job as a whole cannot run (bad input path, unsafe output dir)."""


@dataclass
class Job:
    input: str
    output: Path
    specs: list[CropSpec]
    format: str = "keep"
    quality: int = 90
    recursive: bool = False
    dry_run: bool = False
    overwrite: bool = False
    allow_input_dir: bool = False


@dataclass
class Summary:
    written: int = 0
    planned: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)  # unsupported file types
    earlier: list[Path] = field(default_factory=list)  # outputs of an earlier identical run


def _is_relative_to(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


@dataclass
class Scan:
    """What an input search found, and how far below its root it looks."""

    root: Path  # output paths mirror the layout below this directory
    files: list[Path]
    any_depth: bool = False  # a recursive folder scan, or a glob containing '**'


def discover(input_str: str, recursive: bool) -> Scan:
    path = Path(input_str).expanduser()
    parts = path.parts
    glob_at = next((i for i, p in enumerate(parts) if any(c in p for c in GLOB_CHARS)), None)
    if glob_at is not None:
        root = Path(*parts[:glob_at]) if glob_at else Path(".")
        if not root.is_dir():
            raise UsageError(f"input directory not found: {root}")
        pattern = str(Path(*parts[glob_at:]))
        try:
            found = list(root.glob(pattern))
        except ValueError as exc:  # e.g. '**' mixed into a name on older Pythons
            raise UsageError(f"invalid glob pattern {input_str!r}: {exc}") from None
        any_depth = "**" in pattern
    elif path.is_dir():
        root, any_depth = path, recursive
        found = path.rglob("*") if recursive else path.glob("*")
    elif path.is_file():
        return Scan(path.parent, [path])
    else:
        raise UsageError(f"input not found: {input_str}")
    files = [
        f for f in found
        if f.is_file() and not any(p.startswith(".") for p in f.relative_to(root).parts)
    ]
    return Scan(root, sorted(files), any_depth)


def _output_path(src: Path, root: Path, job: Job, spec: CropSpec) -> tuple[Path, str]:
    rel = src.relative_to(root)
    if job.format == "keep":
        ext, fmt = src.suffix.lower(), EXT_FORMAT[src.suffix.lower()]
    else:
        fmt, ext = OUTPUT_FORMATS[job.format]
    suffix = f"_{spec.name}" if spec.name else ""
    return job.output / rel.parent / f"{rel.stem}{suffix}{ext}", fmt


def _prepare_mode(img: Image.Image, fmt: str) -> Image.Image:
    if fmt == "JPEG" and img.mode not in ("RGB", "L", "CMYK"):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    if fmt == "WEBP" and img.mode not in ("RGB", "RGBA"):
        return img.convert("RGBA" if img.has_transparency_data else "RGB")
    if img.mode == "CMYK" and fmt not in ("JPEG", "TIFF"):
        return img.convert("RGB")
    return img


def _save(img: Image.Image, out: Path, fmt: str, quality: int, icc: bytes | None) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    prepared = _prepare_mode(img, fmt)
    params: dict = {"quality": quality} if fmt in ("JPEG", "WEBP") else {}
    # A colour profile only describes the colour space it was made for; drop it on conversion.
    # Some encoders fall back to image.info, so the stale profile is removed there too.
    if icc and (prepared.mode == img.mode or {prepared.mode, img.mode} <= RGB_MODES):
        params["icc_profile"] = icc
    else:
        prepared.info.pop("icc_profile", None)
    # Write to a fresh, uniquely named file, then rename it into place. O_EXCL guarantees the
    # name was not already taken, so cleanup can only ever remove a file this call created.
    # Mode 0o666 lets the umask decide permissions, as for any newly created file.
    tmp = out.with_name(f".batch-crop-{uuid.uuid4().hex}{out.suffix}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(fd, "wb") as handle:
            prepared.save(handle, format=fmt, **params)
        tmp.replace(out)
    except BaseException:
        tmp.unlink(missing_ok=True)  # governance: allow-delete DS001: removes only the O_EXCL temp file this call created, after its write failed
        raise


def _process(src: Path, root: Path, job: Job, protected: set[Path], claimed: set[Path],
             summary: Summary, log: Callable[[str], None]) -> None:
    """Crop one file with every spec. All outputs are planned before any is written.

    `claimed` holds outputs other files of this batch own. A path joins it only once this
    file really owns it: after its write succeeds, or, in a dry run, once the whole plan
    succeeds. A file that fails planning, or whose write fails, blocks nothing it never wrote.
    """
    with Image.open(src) as opened:
        opened.load()
        img = ImageOps.exif_transpose(opened)
    icc = img.info.get("icc_profile")
    plans = []
    planned: set[Path] = set()
    for spec in job.specs:
        box, resize = compute_crop(spec, *img.size)
        out, fmt = _output_path(src, root, job, spec)
        key = out.resolve()
        if key in protected:
            raise ValueError(f"output {out} would overwrite an input file")
        if key in claimed or key in planned:
            raise ValueError(f"output {out} collides with another output in this batch")
        if out.exists() and not job.overwrite:
            raise ValueError(f"output {out} already exists (use --overwrite to replace it)")
        planned.add(key)
        plans.append((key, out, fmt, box, resize))
    rel = src.relative_to(root)
    for key, out, fmt, box, resize in plans:
        size = resize or (box[2] - box[0], box[3] - box[1])
        if job.dry_run:
            claimed.add(key)
            summary.planned += 1
            log(f"plan {rel} -> {out} crop={box} size={size[0]}x{size[1]}")
            continue
        cropped = img.crop(box)
        if resize:
            cropped = cropped.resize(resize, Image.Resampling.LANCZOS)
        _save(cropped, out, fmt, job.quality, icc)
        claimed.add(key)
        summary.written += 1
        log(f"ok   {rel} -> {out} ({size[0]}x{size[1]})")


def _output_location_problem(scan: Scan, images: list[Path], job: Job) -> str | None:
    """Explain why outputs could collide with inputs or be found by a later run, if they could.

    Outputs mirror the input layout: ``root/<sub>/x.png`` goes to ``output/<sub>/x_name.png``.
    A single file, a top-level folder scan, or a glob without '**' only finds files at one
    fixed depth below root. A mirrored output can only sit at that depth when the output dir
    is root itself, and then it lands beside its own input, which the folder test catches.
    A recursive scan or a '**' glob finds files at any depth, so no output may land below root.
    """
    root_r, out_r = scan.root.resolve(), job.output.resolve()
    input_dirs = {f.resolve().parent for f in images}
    if out_r in input_dirs:
        return f"output dir {job.output} holds input images"
    for src in images:
        for spec in job.specs:
            out = _output_path(src, scan.root, job, spec)[0].resolve()
            if out.parent in input_dirs or (scan.any_depth and root_r in out.parents):
                return (f"output {out} would land where the input search looks for images, "
                        "so a later run could crop it again")
    return None


def _earlier_outputs(root: Path, images: list[Path], job: Job) -> set[Path]:
    """Inputs that are exactly what this run would write for another input.

    With --allow-input-dir the outputs can sit among the inputs, so a rerun would find
    a.png and its earlier output a_sq.png side by side. Such files are not re-cropped.
    """
    made_by: dict[Path, set[Path]] = {}
    for src in images:
        for spec in job.specs:
            made_by.setdefault(_output_path(src, root, job, spec)[0].resolve(), set()).add(src)
    return {f for f in images if made_by.get(f.resolve(), set()) - {f}}


def run(job: Job, log: Callable[[str], None] = print) -> Summary:
    scan = discover(job.input, job.recursive)
    root, files = scan.root, scan.files
    out_r = job.output.resolve()
    if out_r.exists() and not out_r.is_dir():
        raise UsageError(f"output {job.output} exists and is not a directory")
    if job.allow_input_dir and root.resolve() in out_r.parents:  # never re-read our own outputs
        files = [f for f in files if not _is_relative_to(f.resolve(), out_r)]
    images = [f for f in files if f.suffix.lower() in EXT_FORMAT]
    if not images:
        ignored = f" ({len(files)} unsupported file(s) ignored)" if files else ""
        raise UsageError(f"no supported images found for input {job.input}{ignored}")
    problem = _output_location_problem(scan, images, job)
    if problem and not job.allow_input_dir:
        raise UsageError(
            f"{problem}; choose an output dir outside the input, or pass --allow-input-dir"
        )
    if problem:
        log(f"warning: {problem} (allowed by --allow-input-dir)")
    earlier = _earlier_outputs(root, images, job)
    summary = Summary()
    # An earlier output of this same run may be replaced (with --overwrite); real inputs never.
    protected = {f.resolve() for f in files if f not in earlier}
    claimed: set[Path] = set()
    for src in files:
        rel = src.relative_to(root)
        if src.suffix.lower() not in EXT_FORMAT:
            summary.skipped.append(src)
            log(f"skip {rel}: unsupported file type")
            continue
        if src in earlier:
            summary.earlier.append(src)
            log(f"skip {rel}: output of an earlier run with these specs")
            continue
        try:
            _process(src, root, job, protected, claimed, summary, log)
        except Exception as exc:  # one bad file must not stop the batch; it is reported
            summary.failed.append((src, f"{type(exc).__name__}: {exc}"))
            log(f"FAIL {rel}: {type(exc).__name__}: {exc}")
    return summary
