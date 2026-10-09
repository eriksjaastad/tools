import os
from pathlib import Path

import pytest
from PIL import Image

from batch_crop.cli import main


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path):
    (tmp_path / "photos").mkdir()
    Image.new("RGB", (300, 100), "white").save(tmp_path / "photos" / "p.png")
    return tmp_path


def test_config_relative_paths_tables_and_flag_override(project, monkeypatch, tmp_path_factory):
    cfg = write(project / "crop.toml", """
input = "photos"
output = "out"
format = "webp"
quality = 70
crop = ["aspect:1:1#sq", { mode = "size", value = "60x40", anchor = "top-left", name = "corner" }]
""")
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))  # paths resolve from the config's folder
    assert main(["--config", str(cfg), "--format", "png"]) == 0
    assert Image.open(project / "out" / "p_sq.png").size == (100, 100)
    assert Image.open(project / "out" / "p_corner.png").size == (60, 40)
    assert main(["--config", str(cfg), "-o", str(project / "o2"), "-c", "aspect:3:1"]) == 0
    assert [p.name for p in (project / "o2").iterdir()] == ["p.webp"]  # --crop replaces the list


@pytest.mark.parametrize("body, message", [
    ('input = "photos"\noutput = "out"\ncrop = ["aspect:1:1"]\ncolour = 1', "unknown key(s): colour"),
    ('input = "photos"\noutput = [', "invalid TOML"),
    ('input = "photos"\noutput = "out"\nrecursive = "yes"\ncrop = ["aspect:1:1"]', "'recursive' must be of type bool"),
    ('input = "photos"\noutput = "out"\nquality = true\ncrop = ["aspect:1:1"]', "'quality' must be of type int"),
    ('input = "photos"\noutput = "out"\nquality = 0\ncrop = ["aspect:1:1"]', "quality must be 1-100"),
    ('input = "photos"\noutput = "out"\nformat = "gif"\ncrop = ["aspect:1:1"]', "format must be one of"),
    ('input = "photos"\noutput = "out"\ncrop = ["aspect:0:1"]', "aspect needs a positive"),
    ('input = "photos"\noutput = "out"\ncrop = [{ mode = "box" }]', "needs string 'mode' and 'value'"),
    ('input = "photos"\noutput = "out"\ncrop = [{ mode = "box", value = "0,0,5,5", zoom = 2 }]', "unknown key(s): zoom"),
    ('input = "photos"\noutput = "out"\ncrop = [3]', "must be a spec string or a table"),
    ('input = "photos"\noutput = "out"\ncrop = ["aspect:1:1#a", "aspect:2:1#a"]', "crop names must be unique"),
    ('input = "photos"\ncrop = ["aspect:1:1"]', "missing output"),
    ('input = "photos"\noutput = "out"', "no crop spec given"),
    ('input = "nope"\noutput = "out"\ncrop = ["aspect:1:1"]', "input not found"),
])
def test_config_errors_exit_2_and_write_nothing(project, capsys, body, message):
    cfg = write(project / "bad.toml", body)
    assert main(["--config", str(cfg)]) == 2
    assert message in capsys.readouterr().err
    assert not (project / "out").exists()


def test_missing_config_file(project, capsys):
    assert main(["--config", str(project / "absent.toml")]) == 2
    assert "config file not found" in capsys.readouterr().err


def test_config_path_is_a_directory(project, capsys):
    assert main(["--config", str(project / "photos")]) == 2
    assert "config path is a directory" in capsys.readouterr().err


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="root ignores file modes")
def test_unreadable_config_file(project, capsys):
    cfg = write(project / "locked.toml", 'input = "photos"\noutput = "out"\ncrop = ["aspect:1:1"]')
    cfg.chmod(0)
    try:
        assert main(["--config", str(cfg)]) == 2
    finally:
        cfg.chmod(0o644)
    assert "cannot read config file" in capsys.readouterr().err


def test_config_not_utf8(project, capsys):
    cfg = project / "latin1.toml"
    cfg.write_bytes('input = "fotos-café"\n'.encode("latin-1"))
    assert main(["--config", str(cfg)]) == 2
    assert "not valid UTF-8" in capsys.readouterr().err
    assert not (project / "out").exists()
