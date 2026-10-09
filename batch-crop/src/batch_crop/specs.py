"""Crop specs: parsing and geometry. No file I/O happens here.

A spec string has the form ``MODE:VALUE[@ANCHOR][#NAME]``, for example
``aspect:16:9@top#wide`` or ``box:10,10,410,310``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

MODES = ("aspect", "size", "fill", "box", "rel")
ANCHORED_MODES = ("aspect", "size", "fill")
ANCHORS = {
    "center": (0.5, 0.5),
    "top": (0.5, 0.0),
    "bottom": (0.5, 1.0),
    "left": (0.0, 0.5),
    "right": (1.0, 0.5),
    "top-left": (0.0, 0.0),
    "top-right": (1.0, 0.0),
    "bottom-left": (0.0, 1.0),
    "bottom-right": (1.0, 1.0),
}
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

Box = tuple[int, int, int, int]


class SpecError(ValueError):
    """A crop spec is malformed."""


class CropError(ValueError):
    """A valid spec cannot be applied to a particular image."""


@dataclass(frozen=True)
class CropSpec:
    mode: str
    value: str
    numbers: tuple[float, ...]
    anchor: tuple[float, float] = (0.5, 0.5)
    name: str = ""


def _floats(text: str, sep: str, count: int, what: str) -> tuple[float, ...]:
    parts = text.split(sep)
    if len(parts) != count:
        raise SpecError(f"{what} needs {count} numbers separated by '{sep}', got {text!r}")
    try:
        nums = tuple(float(p) for p in parts)
    except ValueError:
        raise SpecError(f"{what} has a non-numeric part: {text!r}") from None
    if not all(math.isfinite(v) for v in nums):
        raise SpecError(f"{what} numbers must be finite, got {text!r}")
    return nums


def _parse_value(mode: str, value: str) -> tuple[float, ...]:
    if mode == "aspect":
        parts = _floats(value, ":", value.count(":") + 1, "aspect")
        if len(parts) > 2 or min(parts) <= 0:
            raise SpecError(f"aspect needs a positive W:H or a single ratio, got {value!r}")
        return (parts[0] / parts[1] if len(parts) == 2 else parts[0],)
    if mode in ("size", "fill"):
        w, h = _floats(value.lower(), "x", 2, mode)
        if w < 1 or h < 1 or w != int(w) or h != int(h):
            raise SpecError(f"{mode} needs positive whole pixels like 800x600, got {value!r}")
        return (w, h)
    if mode == "box":
        x1, y1, x2, y2 = _floats(value, ",", 4, "box")
        if any(v != int(v) or v < 0 for v in (x1, y1, x2, y2)):
            raise SpecError(f"box needs non-negative whole pixels, got {value!r}")
    else:  # rel
        x1, y1, x2, y2 = _floats(value, ",", 4, "rel")
        if not all(0.0 <= v <= 1.0 for v in (x1, y1, x2, y2)):
            raise SpecError(f"rel values must be between 0 and 1, got {value!r}")
    if x2 <= x1 or y2 <= y1:
        raise SpecError(f"{mode} needs x2 > x1 and y2 > y1, got {value!r}")
    return (x1, y1, x2, y2)


def parse_anchor(text: str) -> tuple[float, float]:
    key = text.strip().lower()
    if key in ANCHORS:
        return ANCHORS[key]
    fx, fy = _floats(key, ",", 2, "anchor")
    if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
        raise SpecError(f"anchor point must be between 0 and 1, got {text!r}")
    return (fx, fy)


def build_spec(mode: str, value: str, anchor: str | None = None, name: str | None = None) -> CropSpec:
    mode = mode.strip().lower()
    if mode not in MODES:
        raise SpecError(f"unknown crop mode {mode!r}; choose one of {', '.join(MODES)}")
    numbers = _parse_value(mode, value.strip())
    if anchor is not None and mode not in ANCHORED_MODES:
        raise SpecError(f"{mode} takes no anchor; anchors apply to {', '.join(ANCHORED_MODES)}")
    if name is not None and not _NAME_RE.match(name):
        raise SpecError(f"name may use letters, digits, '-' and '_' only, got {name!r}")
    point = parse_anchor(anchor) if anchor is not None else ANCHORS["center"]
    return CropSpec(mode, value.strip(), numbers, point, name or "")


def parse_spec(text: str) -> CropSpec:
    """Parse ``MODE:VALUE[@ANCHOR][#NAME]``."""
    rest, _, name = text.partition("#")
    rest, at, anchor = rest.partition("@")
    mode, colon, value = rest.partition(":")
    if not colon or not value:
        raise SpecError(f"crop spec must look like MODE:VALUE, got {text!r}")
    return build_spec(mode, value, anchor if at else None, name if "#" in text else None)


def _place(cw: int, ch: int, w: int, h: int, anchor: tuple[float, float]) -> Box:
    """Put a cw x ch window as close to centred on the anchor as the image allows."""
    left = min(max(round(anchor[0] * w - cw / 2), 0), w - cw)
    top = min(max(round(anchor[1] * h - ch / 2), 0), h - ch)
    return (left, top, left + cw, top + ch)


def _largest(ratio: float, w: int, h: int) -> tuple[int, int]:
    if w / h > ratio:
        return max(1, min(w, round(h * ratio))), h
    return w, max(1, min(h, round(w / ratio)))


def compute_crop(spec: CropSpec, w: int, h: int) -> tuple[Box, tuple[int, int] | None]:
    """Return the crop box for a w x h image and an optional final resize size."""
    n = spec.numbers
    if spec.mode == "aspect":
        return _place(*_largest(n[0], w, h), w, h, spec.anchor), None
    if spec.mode == "size":
        cw, ch = int(n[0]), int(n[1])
        if cw > w or ch > h:
            raise CropError(f"image is {w}x{h}, smaller than size {cw}x{ch}")
        return _place(cw, ch, w, h, spec.anchor), None
    if spec.mode == "fill":
        tw, th = int(n[0]), int(n[1])
        return _place(*_largest(tw / th, w, h), w, h, spec.anchor), (tw, th)
    if spec.mode == "box":
        x1, y1, x2, y2 = (int(v) for v in n)
        if x2 > w or y2 > h:
            raise CropError(f"box {spec.value} extends past the {w}x{h} image")
        return (x1, y1, x2, y2), None
    # rel: fractions of the image, rounded, never smaller than 1 pixel
    x1 = min(round(n[0] * w), w - 1)
    y1 = min(round(n[1] * h), h - 1)
    x2 = min(max(round(n[2] * w), x1 + 1), w)
    y2 = min(max(round(n[3] * h), y1 + 1), h)
    return (x1, y1, x2, y2), None
