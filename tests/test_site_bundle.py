"""scripts/build_site_bundle.py: what it copies, and that its privacy checks catch planted problems."""
import importlib.util
import json
import re
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_site_bundle.py"
spec = importlib.util.spec_from_file_location("build_site_bundle", SCRIPT)
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def _png(path: Path, color) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (64, 64), "white")
    img.paste(color, (16, 16, 48, 48))
    img.save(path)


@pytest.fixture
def runs(tmp_path):
    r = tmp_path / "runs"
    d = r / "sets" / "demo_xx"
    for name in ("cat_0", "cat_1", "saw_0", "saw_1"):
        _png(d / "candidates" / f"{name}.png", (40, 40, 40))
    cand = lambda f: {"file": f"candidates/{f}.png", "sam_ok": True, "spark_ok": True}  # noqa: E731
    (d / "manifest.json").write_text(json.dumps({"lang": "xx", "items": [
        {"word": "cat", "status": "kept", "image": "candidates/cat_1.png", "candidates": [cand("cat_0"), cand("cat_1")]},
        {"word": "saw", "status": "review", "image": None, "candidates": [cand("saw_0"), cand("saw_1")]}]}))
    _png(r / "sets" / "other" / "candidates" / "x_0.png", (0, 0, 0))
    (r / "sets" / "other" / "manifest.json").write_text(json.dumps({"items": []}))
    lesion = r / "lesion" / "demo_xx"
    lesion.mkdir(parents=True)
    (lesion / "index.json").write_text(json.dumps({"conditions": [{"file": "intact.json"}]}))
    (lesion / "intact.json").write_text(json.dumps({"id": "intact", "items": [], "accuracy": 1}))
    (lesion / "unlisted.json").write_text("{}")
    scenes = r / "scenes"
    _png(scenes / "s1.png", (200, 0, 0))
    (scenes / "s1.json").write_text(json.dumps({"id": "s1", "content_units": ["a"], "token_sha": "abc",
                                                "image_file": str(scenes / "s1.png")}))
    return r


def test_copies_only_what_the_site_reads(runs, tmp_path):
    out = tmp_path / "bundle"
    assert B.bundle_sets(runs, out, ["demo_*"], quantize=True) == ["demo_xx"]
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.png"))
    assert files == ["sets/demo_xx/candidates/cat_1.png", "sets/demo_xx/candidates/saw_0.png",
                     "sets/demo_xx/candidates/saw_1.png"]  # the chosen picture, and a review item's candidates
    items = json.loads((out / "sets" / "demo_xx" / "manifest.json").read_text())["items"]
    assert [c["file"] for c in items[0]["candidates"]] == ["candidates/cat_1.png"]
    assert B.bundle_lesion(runs, out, ["demo_xx"]) >= 1
    assert not (out / "lesion" / "demo_xx" / "unlisted.json").exists()
    B.bundle_scenes(runs, out, quantize=False)
    scene = json.loads((out / "scenes" / "s1.json").read_text())
    assert scene["image_file"] == "s1.png" and "token_sha" not in scene
    assert B.check_bundle(out, require_patterns=False) == []


@pytest.mark.parametrize("name,content,expected", [
    ("sets/demo_xx/clip.wav", b"RIFF\x00\x00\x00\x00WAVEfmt ", "audio"),
    ("sets/demo_xx/note.json", b"RIFF\x00\x00\x00\x00WAVEfmt ", "audio"),  # audio under another name
    ("sets/demo_xx/table.csv", b"a,b\n", "data guard"),
    ("cache/x.json", b'{"k": "MODEL_API_KEY=abc"}', "API key"),
    ("cache/x.json", b'{"k": "sk-abcdefghijklmnopqrstuvwxyz123456"}', "API key"),
    ("cache/x.json", b'{"path": "/Users/someone/data.png"}', "local path"),
    ("cache/x.json", b'{"id": "ZZQ1234"}', "private-data pattern"),
    ("plato/human/cat.json", b"{}", "human drawings"),
    ("cache/x.json", b'{"src": "quickdraw ndjson"}', "Quick, Draw"),
])
def test_privacy_checks_catch_planted_problems(runs, tmp_path, monkeypatch, name, content, expected):
    out = tmp_path / "bundle"
    B.bundle_sets(runs, out, ["demo_*"], quantize=False)
    monkeypatch.setattr(B, "private_patterns", lambda: [re.compile(rb"ZZQ[0-9]{4}")])
    assert B.check_bundle(out) == []
    (out / name).parent.mkdir(parents=True, exist_ok=True)
    (out / name).write_bytes(content)
    problems = B.check_bundle(out)
    assert problems and any(expected.lower() in p.lower() for p in problems), problems


def test_the_real_api_key_is_found_anywhere(runs, tmp_path, monkeypatch):
    out = tmp_path / "bundle"
    B.bundle_sets(runs, out, ["demo_*"], quantize=False)
    monkeypatch.setattr(B, "api_key", lambda: b"plainkey-0123456789")
    png = next(out.rglob("*.png"))
    png.write_bytes(png.read_bytes() + b"plainkey-0123456789")
    assert any("contains the Meta API key" in p for p in B.check_bundle(out, require_patterns=False))


def test_missing_private_patterns_fail_unless_allowed(runs, tmp_path, monkeypatch):
    out = tmp_path / "bundle"
    B.bundle_sets(runs, out, ["demo_*"], quantize=False)
    monkeypatch.setattr(B, "private_patterns", lambda: None)
    assert any("private_patterns.txt not found" in p for p in B.check_bundle(out))
    assert B.check_bundle(out, require_patterns=False) == []


# --- one bundle per site -------------------------------------------------------------------------

def build(monkeypatch, *args) -> int:
    monkeypatch.setattr(B.sys, "argv", ["build_site_bundle.py", *args, "--allow-missing-patterns"])
    return B.main()


def test_plato_bundle_carries_nothing_from_runs(runs, tmp_path, monkeypatch):
    out = tmp_path / "plato"
    assert build(monkeypatch, "--site", "plato", "--runs", str(runs), "--out", str(out)) == 0
    assert [p.relative_to(out).as_posix() for p in out.rglob("*")] == ["BUNDLE.json"]
    marker = json.loads((out / "BUNDLE.json").read_text())
    assert marker["site"] == "plato" and marker["sets"] == [] and marker["lesion_conditions"] == 0
    assert "Plato" in marker["about"]


def test_lingua_bundle_has_the_lab_data(runs, tmp_path, monkeypatch):
    out = tmp_path / "lingua"
    assert build(monkeypatch, "--site", "lingua", "--runs", str(runs), "--out", str(out)) == 0
    marker = json.loads((out / "BUNDLE.json").read_text())
    assert marker["site"] == "lingua" and marker["sets"] == ["demo_xx"] and marker["scenes"] == 1
    assert (out / "sets" / "demo_xx" / "manifest.json").is_file() and (out / "lesion" / "demo_xx" / "index.json").is_file()


def test_the_default_site_is_plato(runs, tmp_path, monkeypatch):
    monkeypatch.delenv("MLL_SITE", raising=False)
    out = tmp_path / "default"
    assert build(monkeypatch, "--runs", str(runs), "--out", str(out)) == 0
    assert json.loads((out / "BUNDLE.json").read_text())["site"] == "plato"


@pytest.mark.parametrize("site", ["plato", "lingua"])
def test_staged_space_serves_its_site(site, tmp_path, monkeypatch):
    out = tmp_path / "bundle"
    assert build(monkeypatch, "--site", "plato", "--out", str(out)) == 0  # any bundle will do here
    stage = tmp_path / "space"
    B.stage_space(out, stage, site)
    docker = (stage / "Dockerfile").read_text()
    assert f"ARG MLL_SITE={site}\n" in docker and "MLL_SITE=${MLL_SITE}" in docker
    readme = (stage / "README.md").read_text()
    name = B.brand.SITES[site].name
    assert f"title: {name}" in readme and f"MLL_SITE={site}" in readme
    desc = re.search(r"^short_description: (.*)$", readme, re.M).group(1)
    assert len(desc) <= 60  # the Hub's limit
    assert (stage / "metalesionlab" / "brand.py").is_file() and (stage / "dist" / "site_data" / "BUNDLE.json").is_file()
