from pathlib import Path

import pytest
from PIL import Image

from batch_crop import Job, parse_spec, run
from batch_crop.cli import main

RED, WHITE = (255, 0, 0), (255, 255, 255)


def make_image(path: Path, size=(400, 200), marker=(320, 80, 380, 120), fmt=None, **save):
    """White image with a red rectangle at `marker` (x1, y1, x2, y2)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, WHITE)
    img.paste(RED, marker)
    img.save(path, format=fmt, **save)
    return path


def is_red(px, tol=60):
    return px[0] > 255 - tol and px[1] < tol and px[2] < tol


def red_pixels(path: Path) -> int:
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        return sum(n for n, px in rgb.getcolors(rgb.width * rgb.height) if is_red(px))


@pytest.fixture
def dirs(tmp_path):
    src, out = tmp_path / "in", tmp_path / "out"
    src.mkdir()
    return src, out


def test_aspect_anchor_keeps_marker_in_crop(dirs):
    src, out = dirs
    make_image(src / "a.png")
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1@right#r", "-c", "aspect:1:1#c"]) == 0
    with Image.open(out / "a_r.png") as img:
        assert img.size == (200, 200)
        assert is_red(img.getpixel((150, 100)))  # marker x 320-380 shifts by 200
    assert red_pixels(out / "a_c.png") == 0  # centred crop (100-300) misses the marker


def test_size_box_rel_fill_positions(dirs):
    src, out = dirs
    make_image(src / "a.png")
    specs = ["size:80x60@0.875,0.5#s", "box:300,60,400,140#b", "rel:0.75,0.25,1,0.75#r", "fill:50x50@right#f"]
    assert main([str(src), "-o", str(out)] + sum((["-c", s] for s in specs), [])) == 0
    with Image.open(out / "a_s.png") as img:
        assert img.size == (80, 60)
        assert is_red(img.getpixel((40, 30))) and not is_red(img.getpixel((5, 5)))
    with Image.open(out / "a_b.png") as img:
        assert img.size == (100, 80)
        assert is_red(img.getpixel((50, 40))) and not is_red(img.getpixel((90, 40)))
    with Image.open(out / "a_r.png") as img:
        assert img.size == (100, 100)
        assert is_red(img.getpixel((50, 50)))
    with Image.open(out / "a_f.png") as img:
        assert img.size == (50, 50)  # 200x200 crop scaled down
        assert is_red(img.getpixel((37, 25)))


def test_exif_orientation_is_applied_before_cropping(dirs):
    src, out = dirs
    exif = Image.Exif()
    exif[0x0112] = 6  # stored landscape, displayed rotated 90 degrees clockwise
    exif[0x010F] = "SyntheticCam"  # camera make: metadata that must not be copied
    # Red left half in storage becomes the top half once rotated for display.
    make_image(src / "phone.jpg", size=(200, 100), marker=(0, 0, 100, 100), quality=95, exif=exif)
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1@top"]) == 0
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1@top", "-f", "png"]) == 0
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1@top", "-f", "webp"]) == 0
    for name in ("phone.jpg", "phone.png", "phone.webp"):
        with Image.open(out / name) as img:
            assert img.size == (100, 100)
            assert all(is_red(img.getpixel(p)) for p in [(10, 10), (90, 10), (10, 90), (90, 90)])
            assert dict(img.getexif()) == {}  # no orientation to re-apply, no camera metadata


def test_bad_files_do_not_stop_the_batch(dirs, capsys):
    src, out = dirs
    (src / "a_broken.jpg").write_bytes(b"this is not an image")
    make_image(src / "b_good.png")
    make_image(src / "c_small.png", size=(40, 40), marker=(0, 0, 1, 1))
    (src / "notes.txt").write_text("hello")
    assert main([str(src), "-o", str(out), "-c", "size:100x100"]) == 1
    assert (out / "b_good.png").exists()
    assert not (out / "a_broken.jpg").exists() and not (out / "c_small.png").exists()
    captured = capsys.readouterr()
    assert "1 written, 2 failed, 1 skipped" in captured.out
    assert "a_broken.jpg" in captured.err and "c_small.png" in captured.err


def test_unsupported_files_beside_images_do_not_fail(dirs):
    src, out = dirs
    make_image(src / "a.png")
    (src / "readme.txt").write_text("x")
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1"]) == 0


@pytest.mark.parametrize("setup, rel_input, message", [
    ({}, "missing", "input not found"),
    ({}, "missing/*.png", "input directory not found"),
    ({}, "in", "no supported images found"),  # empty directory
    ({"in/a.png": "img"}, "in/*.jpg", "no supported images found"),  # glob matches nothing
    ({"in/sub/a.png": "img"}, "in", "no supported images found"),  # only in a subfolder, no -r
    ({"in/.hidden.png": "img"}, "in", "no supported images found"),
    ({"in/notes.txt": "x", "in/data.csv": "x"}, "in", "2 unsupported file(s) ignored"),
    ({"in/notes.txt": "x"}, "in/notes.txt", "1 unsupported file(s) ignored"),
])
def test_no_inputs_is_a_usage_error(dirs, capsys, setup, rel_input, message):
    root = dirs[0].parent
    for rel, kind in setup.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        make_image(root / rel) if kind == "img" else (root / rel).write_text(kind)
    assert main([str(root / rel_input), "-o", str(dirs[1]), "-c", "aspect:1:1"]) == 2
    assert message in capsys.readouterr().err
    assert not dirs[1].exists()


def test_output_path_that_is_a_file_is_a_usage_error(dirs, capsys):
    src, out = dirs
    make_image(src / "a.png")
    out.write_text("not a folder")
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1"]) == 2
    assert "is not a directory" in capsys.readouterr().err


# Tree: in/a.png, in/nested/b.png, in/nested/nested/c.png
@pytest.mark.parametrize("rel_input, rel_output, flags, code", [
    ("in/a.png", "in/cropped", [], 0),  # one file can only ever reread itself
    ("in/a.png", "in", [], 2),  # beside the input
    ("in", "in/cropped", [], 0),  # top level only; the subfolder is never scanned
    ("in", "in/nested", [], 0),  # nested/ holds no input of a top-level run
    ("in", "in", [], 2),
    ("in", "in/cropped", ["-r"], 2),  # a recursive rerun would find the outputs
    ("in/nested", "in", ["-r"], 2),  # nested/c.png would be written to in/nested/c.png
    ("in/*.png", "in/cropped", [], 0),  # '*.png' matches one level; outputs sit two deep
    ("in/*.png", "in", [], 2),
    ("in/**/*.png", "in/cropped", [], 2),  # '**' matches any depth
    ("in/**/*.png", "in/deep/er", [], 2),  # even where no input sits yet
    ("in/*/*.png", "in/out", [], 0),  # outputs land at in/out/nested/b.png, three deep
    ("in/*/*.png", "in/nested", [], 2),  # that folder holds an input
    ("in/*/b.png", "in", [], 2),  # in/nested/b_sq.png would sit beside its input
])
def test_input_dir_guard(dirs, rel_input, rel_output, flags, code):
    root = dirs[0].parent
    for rel in ("in/a.png", "in/nested/b.png", "in/nested/nested/c.png"):
        make_image(root / rel)
    args = [str(root / rel_input), "-o", str(root / rel_output), "-c", "aspect:1:1#sq", *flags]
    assert main(args) == code
    if code == 2:
        assert not list(root.rglob("*_sq.png"))
    else:  # an identical rerun must not pick up the first run's outputs
        assert main(args + ["--overwrite"]) == 0
        assert not list(root.rglob("*_sq_sq.png"))


def test_output_inside_input_dir_is_refused(dirs):
    src, _ = dirs
    original = make_image(src / "a.png").read_bytes()
    assert main([str(src), "-o", str(src), "-c", "aspect:1:1"]) == 2
    # Even when allowed, an input is never overwritten, with or without --overwrite.
    assert main([str(src), "-o", str(src), "-c", "aspect:1:1", "--allow-input-dir", "--overwrite"]) == 1
    assert (src / "a.png").read_bytes() == original
    assert main([str(src), "-o", str(src), "-c", "aspect:1:1#sq", "--allow-input-dir"]) == 0
    assert Image.open(src / "a_sq.png").size == (200, 200)
    # A recursive run into a subfolder of the input never reads its own earlier outputs.
    args = [str(src), "-o", str(src / "cropped"), "-c", "aspect:1:1", "-r", "--allow-input-dir"]
    assert main(args) == 0
    assert main(args + ["--overwrite"]) == 0
    assert sorted(p.name for p in (src / "cropped").iterdir()) == ["a.png", "a_sq.png"]


@pytest.mark.parametrize("fmt, ext", [("keep", ".png"), ("webp", ".webp")])
def test_rerun_into_the_input_folder_skips_earlier_outputs(dirs, capsys, fmt, ext):
    src, _ = dirs
    make_image(src / "a.png")
    args = [str(src), "-o", str(src), "-c", "aspect:1:1#sq", "-f", fmt, "--allow-input-dir"]
    assert main(args) == 0
    assert "warning: output dir" in capsys.readouterr().out
    assert main(args) == 1  # a_sq exists; it is skipped as an input, and not replaced
    assert main(args + ["--overwrite"]) == 0  # ...unless asked
    out = capsys.readouterr().out
    assert f"skip a_sq{ext}: output of an earlier run" in out
    assert "1 skipped (earlier output)" in out
    assert sorted(p.name for p in src.iterdir()) == ["a.png", f"a_sq{ext}"]


def test_lookalike_name_without_a_source_is_still_cropped(dirs):
    src, _ = dirs
    make_image(src / "x_sq.png")  # named like an output, but no x.* beside it
    args = [str(src), "-o", str(src), "-c", "aspect:1:1#sq", "--allow-input-dir"]
    assert main(args) == 0
    assert sorted(p.name for p in src.iterdir()) == ["x_sq.png", "x_sq_sq.png"]


def test_earlier_outputs_of_other_specs_are_ordinary_inputs(dirs):
    src, _ = dirs
    make_image(src / "a.png")
    base = [str(src), "-o", str(src), "--allow-input-dir"]
    assert main(base + ["-c", "aspect:1:1#sq"]) == 0
    # Only names this run itself would write are recognised; the README says so.
    assert main(base + ["-c", "aspect:1:1#thumb"]) == 0
    assert sorted(p.name for p in src.iterdir()) == ["a.png", "a_sq.png", "a_sq_thumb.png", "a_thumb.png"]


@pytest.mark.parametrize("save_fails", [False, True])
def test_temp_files_never_touch_existing_dotfiles(dirs, monkeypatch, save_fails):
    src, out = dirs
    make_image(src / "a.png")
    out.mkdir()
    bystanders = {".a.png.partial": b"one", ".batch-crop-notes.png": b"two"}
    for name, data in bystanders.items():
        (out / name).write_bytes(data)
    if save_fails:
        def broken_save(self, fp, *args, **kwargs):
            Path(fp).write_bytes(b"half") if isinstance(fp, (str, Path)) else fp.write(b"half")
            raise OSError("disk full")
        monkeypatch.setattr(Image.Image, "save", broken_save)
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1"]) == (1 if save_fails else 0)
    expected = set(bystanders) | (set() if save_fails else {"a.png"})
    assert {p.name for p in out.iterdir()} == expected  # no stray temp file either way
    for name, data in bystanders.items():
        assert (out / name).read_bytes() == data


def test_outputs_get_normal_file_permissions(dirs):
    src, out = dirs
    make_image(src / "a.png")
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1"]) == 0
    reference = out / "reference.txt"
    reference.write_text("x")  # created the ordinary way, under the same umask
    assert (out / "a.png").stat().st_mode == reference.stat().st_mode


def test_existing_output_needs_overwrite_flag(dirs):
    src, out = dirs
    make_image(src / "a.png")
    out.mkdir()
    (out / "a.png").write_bytes(b"keep me")
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1"]) == 1
    assert (out / "a.png").read_bytes() == b"keep me"
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1", "--overwrite"]) == 0
    assert Image.open(out / "a.png").size == (200, 200)


def test_colliding_outputs_in_one_batch_fail(dirs):
    src, out = dirs
    make_image(src / "a.png")
    make_image(src / "a.bmp")
    # --overwrite still refuses to let a later input replace an earlier one's output.
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1", "-f", "webp", "--overwrite"]) == 1
    assert [p.name for p in out.iterdir()] == ["a.webp"]


def test_dry_run_reports_the_same_collisions(dirs, capsys):
    src, out = dirs
    make_image(src / "a.png")
    make_image(src / "a.bmp")
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1", "-f", "webp", "--dry-run"]) == 1
    captured = capsys.readouterr()
    assert "plan a.bmp" in captured.out and "a.png" in captured.err and "collides" in captured.err
    assert not out.exists()


def test_specs_of_one_file_cannot_share_an_output(dirs):
    src, out = dirs
    make_image(src / "a.png")
    spec = parse_spec("aspect:1:1#same")  # the CLI rejects duplicate names; the API must too
    summary = run(Job(input=str(src), output=out, specs=[spec, spec]), log=lambda _: None)
    assert [p.name for p, _ in summary.failed] == ["a.png"] and "collides" in summary.failed[0][1]
    assert not out.exists()


@pytest.mark.parametrize("dry", [False, True])
def test_file_that_fails_planning_claims_no_outputs(dirs, capsys, dry):
    src, out = dirs
    make_image(src / "a.bmp", size=(100, 100), marker=(0, 0, 1, 1))  # too small for #two
    make_image(src / "a.png", size=(400, 400), marker=(0, 0, 1, 1))
    args = [str(src), "-o", str(out), "-f", "webp", "-c", "aspect:1:1#one", "-c", "size:300x300#two"]
    assert main(args + (["--dry-run"] if dry else [])) == 1  # a.bmp fails; a.png must not
    captured = capsys.readouterr()
    assert "a.bmp" in captured.err and "a.png" not in captured.err
    if dry:
        assert captured.out.count("plan a.png") == 2
    else:
        assert sorted(p.name for p in out.iterdir()) == ["a_one.webp", "a_two.webp"]
        assert Image.open(out / "a_one.webp").size == (400, 400)  # from a.png, not a.bmp
        assert Image.open(out / "a_two.webp").size == (300, 300)


@pytest.mark.parametrize("fail_on, written_by_bmp, png_fails", [
    ("a_one.webp", [], False),  # a.bmp wrote nothing, so it blocks nothing
    ("a_two.webp", ["a_one.webp"], True),  # a.bmp really wrote a_one.webp; a.png may not replace it
])
def test_claims_after_a_failed_write(dirs, monkeypatch, capsys, fail_on, written_by_bmp, png_fails):
    import batch_crop.runner as runner

    real_save, writes = runner._save, []

    def flaky_save(img, out, *rest):
        if out.name == fail_on and not any(w[1] == "failed" for w in writes):
            writes.append((out.name, "failed"))  # only the first attempt at this name fails
            raise OSError("disk full")
        real_save(img, out, *rest)
        writes.append((out.name, "ok"))

    monkeypatch.setattr(runner, "_save", flaky_save)
    src, out = dirs
    make_image(src / "a.bmp")
    make_image(src / "a.png")
    args = [str(src), "-o", str(out), "-f", "webp", "-c", "aspect:1:1#one",
            "-c", "aspect:2:1#two", "--overwrite"]
    assert main(args) == 1  # a.bmp's write fails either way
    ok = [name for name, status in writes if status == "ok"]
    assert ok == written_by_bmp + ([] if png_fails else ["a_one.webp", "a_two.webp"])
    err = capsys.readouterr().err
    assert "a.bmp: OSError: disk full" in err
    assert ("a.png" in err) == png_fails


def test_dry_run_writes_nothing(dirs, capsys):
    src, out = dirs
    make_image(src / "a.png")
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1", "--dry-run"]) == 0
    assert not out.exists()
    assert "1 planned (dry run)" in capsys.readouterr().out


def test_recursive_glob_and_hidden_files(dirs):
    src, out = dirs
    make_image(src / "top.png")
    make_image(src / "nested" / "deep.png")
    make_image(src / ".hidden" / "secret.png")
    assert main([str(src), "-o", str(out / "flat"), "-c", "aspect:1:1"]) == 0
    assert sorted(p.name for p in (out / "flat").rglob("*.png")) == ["top.png"]
    assert main([str(src), "-o", str(out / "tree"), "-c", "aspect:1:1", "-r"]) == 0
    assert (out / "tree" / "nested" / "deep.png").exists()
    assert not (out / "tree" / ".hidden").exists()
    assert main([str(src / "**" / "d*.png"), "-o", str(out / "glob"), "-c", "aspect:1:1"]) == 0
    assert [p.name for p in (out / "glob").rglob("*.png")] == ["deep.png"]


def test_format_conversion_flattens_transparency(dirs):
    src, out = dirs
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(src / "clear.png")
    assert main([str(src), "-o", str(out), "-c", "aspect:1:1", "-f", "jpeg", "-q", "80"]) == 0
    with Image.open(out / "clear.jpg") as img:
        assert img.format == "JPEG" and img.mode == "RGB"
        assert img.getpixel((50, 50)) == pytest.approx(WHITE, abs=3)


def test_colour_profile_kept_only_when_colour_space_is_unchanged(dirs):
    src, out = dirs
    profile = b"synthetic-profile-bytes" * 4
    Image.new("CMYK", (100, 100), (0, 255, 255, 0)).save(src / "print.jpg", icc_profile=profile)
    Image.new("RGB", (100, 100), "white").save(src / "screen.png", icc_profile=profile)
    assert main([str(src), "-o", str(out / "keep"), "-c", "aspect:1:1"]) == 0
    assert main([str(src), "-o", str(out / "png"), "-c", "aspect:1:1", "-f", "png"]) == 0
    with Image.open(out / "keep" / "print.jpg") as img:
        assert img.mode == "CMYK" and img.info.get("icc_profile") == profile
    with Image.open(out / "png" / "print.png") as img:
        assert img.mode == "RGB" and "icc_profile" not in img.info  # CMYK profile dropped
    with Image.open(out / "png" / "screen.png") as img:
        assert img.info.get("icc_profile") == profile
