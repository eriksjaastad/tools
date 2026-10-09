import pytest

from batch_crop.specs import CropError, SpecError, compute_crop, parse_spec


def test_parse_full_spec():
    spec = parse_spec("aspect:16:9@top#wide")
    assert spec.mode == "aspect"
    assert spec.numbers == pytest.approx((16 / 9,))
    assert spec.anchor == (0.5, 0.0)
    assert spec.name == "wide"


def test_parse_focal_point_and_decimal_ratio():
    spec = parse_spec("aspect:1.5@0.25,0.75")
    assert spec.numbers == (1.5,)
    assert spec.anchor == (0.25, 0.75)


@pytest.mark.parametrize("text", [
    "aspect", "aspect:", "aspect:0:1", "aspect:1:2:3", "aspect:nan", "zoom:2",
    "size:10x", "size:10.5x20", "fill:0x10", "box:5,5,1,1", "box:1,1,5", "box:-1,0,5,5",
    "rel:0,0,1.5,1", "rel:0.5,0,0.5,1", "box:0,0,5,5@top", "aspect:1:1@middle",
    "aspect:1:1@2,2", "aspect:1:1#bad name", "aspect:1:1#",
])
def test_bad_specs_are_rejected(text):
    with pytest.raises(SpecError):
        parse_spec(text)


@pytest.mark.parametrize("text, size, box, resize", [
    ("aspect:1:1", (400, 200), (100, 0, 300, 200), None),
    ("aspect:1:1@left", (400, 200), (0, 0, 200, 200), None),
    ("aspect:1:1@0.9,0.5", (400, 200), (200, 0, 400, 200), None),  # clamped to edge
    ("aspect:1:1@top", (200, 400), (0, 0, 200, 200), None),
    ("aspect:2:1@bottom", (300, 300), (0, 150, 300, 300), None),
    ("size:100x50", (400, 200), (150, 75, 250, 125), None),
    ("size:100x50@bottom-right", (400, 200), (300, 150, 400, 200), None),
    ("fill:64x32", (300, 300), (0, 75, 300, 225), (64, 32)),
    ("box:10,20,110,70", (400, 200), (10, 20, 110, 70), None),
    ("rel:0.25,0,0.75,0.5", (400, 200), (100, 0, 300, 100), None),
    ("rel:0.5,0.5,0.5001,0.5001", (10, 10), (5, 5, 6, 6), None),  # never below 1px
])
def test_compute_crop(text, size, box, resize):
    assert compute_crop(parse_spec(text), *size) == (box, resize)


@pytest.mark.parametrize("text", ["size:500x10", "box:0,0,401,10"])
def test_crop_larger_than_image_fails(text):
    with pytest.raises(CropError):
        compute_crop(parse_spec(text), 400, 200)
