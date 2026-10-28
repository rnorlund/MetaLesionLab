"""Build the data bundle a public deployment of one site reads (TIPPA_DATA_DIR), and check it.

One codebase serves two sites (MLL_SITE, metalesionlab/brand.py), and each gets its own bundle:

    --site plato   Plato's Chair (the default). Its pages read only files in the repository (web/data/,
                   public_data/, static/), so the bundle holds no data from runs/ at all: just BUNDLE.json.
                   Nothing of the naming lab (picture sets, lesion runs, scenes, judgments) goes with it.
    --site lingua  Tippa Lingua, the sister project: the part of runs/ its pages read, below.

runs/ holds everything the experiments produced (159 MB, gitignored). The Lingua site needs much
less, so this copies exactly what its pages read into dist/site_data/ (gitignored):

    sets/<demo set>/      manifest.json and the chosen picture of each item (the other candidates
                          are left out); an item still in review keeps its candidates. Pictures are
                          re-encoded as 256-color PNGs under the same names (--no-quantize keeps them).
    lesion/<set>/         index.json and the conditions it lists (Model Lab, You vs. the AI)
    scenes/               description scenes: JSON without its edit-token hash, and the picture
    cache/                Muse Spark's cached meaning judgments (typed challenge games are free)
    compress/glimmer.json the layer-removal results (/lab/cut)
    bilingual/results.json the bilingual lesion results, when present
    BUNDLE.json           what was copied, from where and when

Then it checks the bundle and exits non-zero if any check fails:
- the data guard: the blocked file extensions in .githooks/pre-commit and the private-data patterns
  in .githooks/private_patterns.txt (never committed; looked up in the main checkout too);
- no audio, by extension or by file signature;
- no API key: the MODEL_API_KEY value itself (never printed), key-shaped strings and key names;
- no human drawings (Quick, Draw! files) and no participant or patient folders;
- no absolute local paths.

    python scripts/build_site_bundle.py --site plato|lingua [--out dist/site_data] [--sets 'demo_*'] [--stage dist/space]

--stage also assembles a ready-to-upload folder for a Hugging Face Space (Docker SDK): the tracked
app code, public_data/, the Dockerfile (built for that site: MLL_SITE) and the bundle, with a Space
README for the site. See deploy/README.md.
"""
from __future__ import annotations

import argparse
import fnmatch
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from metalesionlab import brand, meta_api  # noqa: E402

MARKER = "BUNDLE.json"
AUDIO_EXT = {".wav", ".wave", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".oga", ".opus", ".webm", ".aif", ".aiff",
             ".wma", ".amr", ".3gp", ".caf", ".mp4", ".mov"}
ALLOWED_EXT = {".json", ".png", ".jpg", ".jpeg", ".webp"}
# Things that must never be in a public bundle, by path.
FORBIDDEN_PATH = re.compile(r"quickdraw|quick_draw|doodle|ndjson|(^|/)human(/|$)|participant|patient|subject|"
                            r"(^|/)\.env|costs\.jsonl|norms|donations", re.I)  # donations: Draw a chair, never in a bundle
KEY_SHAPES = [re.compile(rb"MODEL_API_KEY"), re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}"),
              re.compile(rb"Bearer\s+[A-Za-z0-9._-]{20,}"), re.compile(rb"\bhf_[A-Za-z0-9]{30,}")]
SPACE_README = {
    "plato": f"""---
title: {brand.PLATO.name}
emoji: 🪑
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Draw a chair, then see what Meta's AI drew
---

# {brand.PLATO.name}: {brand.PLATO.tagline.lower()}

Plato thought every chair is a copy of one ideal chair. Draw yours in 20 seconds, then see what Meta's
image model drew and where your chair lands among 200 people's. Seven of Plato's questions, put to Meta's
AI and to people, with the results replayed from the experiments; and Ask Socrates, a Muse Spark agent
that answers from those results.

This Space is the live demo of https://github.com/rnorlund/MetaLesionLab (MLL_SITE=plato). Ask Socrates
is the only part that calls Meta's models; its calls are capped per day for all visitors together.
Research and teaching use only; nothing here is medical advice.
""",
    "lingua": f"""---
title: {brand.LINGUA.name}
emoji: 🗣️
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: {brand.LINGUA.tagline}, on Meta's models
---

# {brand.LINGUA.name}

Build picture-based language tests in minutes, give them by voice, score them automatically, and run
the same tests on Meta's open-weight model to see where language breaks.

This Space is the live demo of https://github.com/rnorlund/MetaLesionLab (MLL_SITE=lingua). Calls to Meta's
models are capped per day for all visitors together; once the day's budget is used up, the site shows
recorded examples instead. Research and teaching use only; not a medical test.
""",
}


# --- copying -------------------------------------------------------------------------------------

def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, data, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")) if compact else \
        json.dumps(data, ensure_ascii=False, indent=1)
    path.write_text(text)


def copy_picture(src: Path, dst: Path, quantize: bool) -> None:
    """Same name and size; 256 colors without dithering (line drawings look the same, files are
    about 40% smaller). Pictures with many colors, such as photos, are copied as they are."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if quantize and src.suffix.lower() == ".png":
        img = Image.open(src)
        if (img.getcolors(1 << 16) or None) is not None:  # at most 65,536 colors: drawn, not photographed
            q = img.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
            buf = io.BytesIO()
            q.save(buf, "PNG", optimize=True)
            if buf.tell() < src.stat().st_size:
                dst.write_bytes(buf.getvalue())
                return
    shutil.copyfile(src, dst)


def bundle_sets(runs: Path, out: Path, patterns: list[str], quantize: bool) -> list[str]:
    names = []
    for d in sorted((runs / "sets").iterdir() if (runs / "sets").is_dir() else []):
        if not d.is_dir() or not any(fnmatch.fnmatch(d.name, p) for p in patterns):
            continue
        if not (d / "manifest.json").is_file():
            print(f"  sets/{d.name}: no manifest.json, skipped")
            continue
        manifest = read_json(d / "manifest.json")
        files, dropped = set(), 0
        for item in manifest.get("items", []):
            cands = item.get("candidates") or []
            if item.get("image"):  # the chosen picture only
                keep = [c for c in cands if c.get("file") == item["image"]]
                dropped += len(cands) - len(keep)
                item["candidates"] = keep
                files.add(item["image"])
            else:  # still in review: its candidates are what the reviewer chooses from
                files.update(c["file"] for c in cands if c.get("file"))
        for rel in sorted(files):
            if Path(rel).is_absolute() or ".." in Path(rel).parts or not (d / rel).is_file():
                raise SystemExit(f"sets/{d.name}: bad or missing picture {rel!r}")
            copy_picture(d / rel, out / "sets" / d.name / rel, quantize)
        write_json(out / "sets" / d.name / "manifest.json", manifest)
        if (d / "webmeta.json").is_file():
            meta = {k: v for k, v in read_json(d / "webmeta.json").items() if k != "token_sha"}
            write_json(out / "sets" / d.name / "webmeta.json", meta)
        print(f"  sets/{d.name}: {len(manifest.get('items', []))} items, {len(files)} pictures "
              f"({dropped} unchosen candidates left out)")
        names.append(d.name)
    return names


def challenge_conditions() -> dict[str, set[str]]:
    """Conditions You vs. the AI asks for by name, so they ship even if an index leaves them out."""
    try:
        import metalesionlab.web.app  # noqa: F401  (loads the challenge module the way the app does)
        from metalesionlab.web.challenge import GAMES
    except Exception as e:  # the web extras aren't installed: rely on the index alone
        print(f"  (couldn't read the challenge's conditions: {e})")
        return {}
    return {g["set"]: {cond for _, cond in g["inside"]} | {"intact"} for g in GAMES.values()}


def bundle_lesion(runs: Path, out: Path, sets: list[str]) -> int:
    n = 0
    wanted = challenge_conditions()
    for d in sorted((runs / "lesion").iterdir() if (runs / "lesion").is_dir() else []):
        if not (d / "index.json").is_file() or d.name not in sets:
            continue
        index = read_json(d / "index.json")
        files = {e["file"] for e in index.get("conditions", []) if isinstance(e, dict) and e.get("file")}
        files |= {f"{c}.json" for c in wanted.get(d.name, ()) if (d / f"{c}.json").is_file()}
        for name in sorted(files):
            if Path(name).name != name or not (d / name).is_file():
                print(f"  lesion/{d.name}: {name} listed but missing, skipped")
                continue
            write_json(out / "lesion" / d.name / name, read_json(d / name), compact=True)
        write_json(out / "lesion" / d.name / "index.json", index, compact=True)
        print(f"  lesion/{d.name}: {len(files)} conditions")
        n += len(files)
    return n


def bundle_scenes(runs: Path, out: Path, quantize: bool) -> int:
    n = 0
    src = runs / "scenes"
    for path in sorted([*src.glob("*.json"), *src.glob("*/*.json")] if src.is_dir() else []):
        scene = read_json(path)
        if not (isinstance(scene, dict) and "id" in scene and "content_units" in scene):
            continue
        image = Path(str(scene.get("image_file", "")))
        if not image.is_absolute():
            image = path.parent / image
        scene = {k: v for k, v in scene.items() if k != "token_sha"}
        if image.is_file():
            copy_picture(image, out / "scenes" / image.name, quantize)
            scene["image_file"] = image.name  # relative to scenes/, never a local absolute path
        else:
            scene.pop("image_file", None)
        write_json(out / "scenes" / path.name, scene)
        n += 1
    print(f"  scenes: {n}")
    return n


def bundle_small(runs: Path, out: Path) -> list[str]:
    copied = []
    for rel in ["cache/semantic_judge.json", "cache/second_rater.json", "compress/glimmer.json"]:
        if (runs / rel).is_file():
            write_json(out / rel, read_json(runs / rel), compact=rel.startswith("cache/"))
            copied.append(rel)
    bilingual = next((d / "results.json" for d in (runs / "bilingual_core100", runs / "bilingual")
                      if (d / "results.json").is_file()), None)  # the n = 100 replication when present
    if bilingual:
        write_json(out / "bilingual" / "results.json", read_json(bilingual), compact=True)
        copied.append("bilingual/results.json")
    print("  " + ", ".join(copied))
    return copied


# --- checks --------------------------------------------------------------------------------------

def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def hook_file(name: str) -> Path | None:
    """A file in .githooks/ here, or in the main checkout when this is a git worktree."""
    candidates = [REPO / ".githooks" / name]
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    if common:
        candidates.append(Path(common).parent / ".githooks" / name)
    return next((p for p in candidates if p.is_file()), None)


def blocked_extensions() -> re.Pattern:
    hook = hook_file("pre-commit")
    text = hook.read_text() if hook else ""
    m = re.search(r"^blocked='([^']+)'", text, re.M)
    if not m:
        raise SystemExit("Couldn't read the blocked extensions from .githooks/pre-commit.")
    return re.compile(m.group(1), re.I)  # the hook matches with nocasematch


def private_patterns() -> list[re.Pattern] | None:
    path = hook_file("private_patterns.txt")
    if path is None:
        return None
    return [re.compile(line.strip().encode()) for line in path.read_text().splitlines() if line.strip()]


def api_key() -> bytes | None:
    try:
        key = meta_api.load_api_key()
    except RuntimeError:
        return None
    return key.encode() if len(key) >= 8 else None


def is_audio(head: bytes) -> bool:
    return (head[:4] == b"RIFF" and head[8:12] in (b"WAVE", b"AIFF")) or head[:3] == b"ID3" or \
        head[:4] in (b"OggS", b"fLaC", b"\x1aE\xdf\xa3", b"FORM", b"caff") or \
        (head[4:8] == b"ftyp") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xf1", b"\xff\xf9")


def check_bundle(out: Path, require_patterns: bool = True) -> list[str]:
    problems: list[str] = []
    blocked = blocked_extensions()
    patterns = private_patterns()
    if patterns is None:
        msg = "private_patterns.txt not found, so the private-data patterns weren't checked"
        if require_patterns:
            problems.append(msg)
        else:
            print("  WARNING: " + msg)
    key = api_key()
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        rel = path.relative_to(out).as_posix()
        data = path.read_bytes()
        if blocked.search(rel):
            problems.append(f"{rel}: data-file extension blocked by the data guard")
        if path.suffix.lower() in AUDIO_EXT or is_audio(data[:16]):
            problems.append(f"{rel}: audio")
        if path.suffix.lower() not in ALLOWED_EXT:
            problems.append(f"{rel}: unexpected file type")
        if FORBIDDEN_PATH.search(rel):
            problems.append(f"{rel}: path suggests human drawings, participant data, the ledger, volunteer data or donated drawings")
        if key and key in data:
            problems.append(f"{rel}: contains the Meta API key")
        if any(p.search(data) for p in KEY_SHAPES):
            problems.append(f"{rel}: contains something shaped like an API key")
        is_text = path.suffix.lower() == ".json"
        if is_text:
            if patterns and any(p.search(data) for p in patterns):
                problems.append(f"{rel}: matches a private-data pattern")
            if re.search(rb"/Users/|/home/[a-z]|[A-Z]:\\\\Users", data):
                problems.append(f"{rel}: contains an absolute local path")
            if re.search(rb"quickdraw|quick, draw", data, re.I):
                problems.append(f"{rel}: mentions Quick, Draw! data")
        if patterns and any(p.search(rel.encode()) for p in patterns):
            problems.append(f"{rel}: file name matches a private-data pattern")
    return problems


def report_size(out: Path) -> tuple[int, int]:
    by_top: Counter = Counter()
    count = 0
    biggest = []
    for p in out.rglob("*"):
        if p.is_file():
            size = p.stat().st_size
            parts = p.relative_to(out).parts
            by_top["/".join(parts[:2]) if parts[0] in ("sets", "lesion") and len(parts) > 2 else parts[0]] += size
            count += 1
            biggest.append((size, p.relative_to(out).as_posix()))
    total = sum(by_top.values())
    for name, size in sorted(by_top.items()):
        print(f"  {name:28s} {size / 1e6:7.2f} MB")
    print(f"  {'total':28s} {total / 1e6:7.2f} MB in {count} files")
    big = [f"{rel} ({size / 1e6:.1f} MB)" for size, rel in sorted(biggest, reverse=True) if size > 5e6]
    if big:
        print("  over 5 MB: " + ", ".join(big))
    return total, count


# --- staging a Hugging Face Space -----------------------------------------------------------------

def stage_space(bundle: Path, stage: Path, site: str = brand.DEFAULT_SITE) -> None:
    """Tracked app code, public_data, the container files and the bundle, laid out like the repo so
    the same Dockerfile builds here and from the repo root. The staged Dockerfile serves `site`."""
    if stage.exists():
        if not (stage / "Dockerfile").is_file() or not (stage / "dist" / "site_data" / MARKER).is_file():
            raise SystemExit(f"{stage} exists and isn't a staged Space; remove it or choose another --stage.")
        shutil.rmtree(stage)
    tracked = git("ls-files", "-z", "metalesionlab", "public_data", "pyproject.toml", "LICENSE").split("\0")
    tracked = [t for t in tracked if t and (REPO / t).is_file()]
    if not tracked:
        raise SystemExit("git ls-files found no app code; run this from a git checkout.")
    for rel in tracked:
        (stage / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, stage / rel)
    for rel in ["Dockerfile", ".dockerignore", "requirements-web.txt", "deploy/start.sh"]:
        (stage / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, stage / rel)
    shutil.copytree(bundle, stage / "dist" / "site_data")
    (stage / "README.md").write_text(SPACE_README[site])
    dockerfile = stage / "Dockerfile"
    text = dockerfile.read_text()
    if "ARG MLL_SITE=" not in text:
        raise SystemExit("The Dockerfile has no ARG MLL_SITE line, so the staged Space can't pick its site.")
    dockerfile.write_text(re.sub(r"^ARG MLL_SITE=\S*$", f"ARG MLL_SITE={site}", text, count=1, flags=re.M))
    problems = [f"{p.relative_to(stage)}" for p in stage.rglob("*") if p.is_file() and
                (p.suffix in (".pyc",) or p.name in (".env", "private_patterns.txt", "costs.jsonl"))]
    if problems:
        raise SystemExit(f"Staging picked up files that must not be uploaded: {problems}")
    size = sum(p.stat().st_size for p in stage.rglob("*") if p.is_file())
    print(f"Staged a Hugging Face Space for {brand.SITES[site].name} (MLL_SITE={site}) in {stage}: "
          f"{len(tracked) + 5} code files plus the bundle, {size / 1e6:.1f} MB. Upload it as described in deploy/README.md.")


# --- main ----------------------------------------------------------------------------------------

def write_marker(out: Path, site: str, **fields) -> None:
    write_json(out / MARKER, {
        "site": site, "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": git("rev-parse", "--short", "HEAD"), **fields,
        "about": f"Data for the {brand.SITES[site].name} web app (MLL_SITE={site}, TIPPA_DATA_DIR). "
                 "Written by scripts/build_site_bundle.py.",
    })


def build_lingua(args, out: Path) -> None:
    runs = args.runs.resolve()
    if not (runs / "sets").is_dir() and args.runs == REPO / "runs":
        common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
        if common and (Path(common).parent / "runs" / "sets").is_dir():
            runs = Path(common).parent / "runs"  # a worktree: use the main checkout's data
    if not (runs / "sets").is_dir():
        raise SystemExit(f"No sets/ in {runs}.")
    if out == runs or out.is_relative_to(runs) or runs.is_relative_to(out):
        raise SystemExit(f"Refusing to write the bundle to {out}.")
    prepare(out)
    print(f"Building the {brand.LINGUA.name} bundle from {runs} into {out}")
    sets = bundle_sets(runs, out, args.sets or ["demo_*"], quantize=not args.no_quantize)
    if not sets:
        raise SystemExit("No picture sets matched.")
    n_conditions = bundle_lesion(runs, out, sets)
    n_scenes = bundle_scenes(runs, out, quantize=not args.no_quantize)
    small = bundle_small(runs, out)
    if args.no_bilingual and (out / "bilingual").exists():
        shutil.rmtree(out / "bilingual")
        small = [s for s in small if not s.startswith("bilingual/")]
    write_marker(out, "lingua", sets=sets, lesion_conditions=n_conditions, scenes=n_scenes, other=small,
                 pictures="chosen picture per item (candidates for items in review)" +
                          ("" if args.no_quantize else ", re-encoded as 256-color PNG"))


def build_plato(args, out: Path) -> None:
    """The Plato site reads only files in the repository, so its bundle carries no data from runs/."""
    prepare(out)
    print(f"Building the {brand.PLATO.name} bundle into {out}: its pages read only files in the repository "
          "(web/data/, public_data/, static/), so nothing from runs/ is copied")
    write_marker(out, "plato", sets=[], lesion_conditions=0, scenes=0, other=[],
                 reads="metalesionlab/web/data/*.json, public_data/plato_*.json and static/ (all in the image)")


def prepare(out: Path) -> None:
    if out in (REPO, Path.home(), Path("/")) or REPO.is_relative_to(out):
        raise SystemExit(f"Refusing to write the bundle to {out}.")
    if out.exists():
        if not (out / MARKER).is_file():
            raise SystemExit(f"{out} exists and isn't a bundle (no {MARKER}); remove it or choose another --out.")
        shutil.rmtree(out)
    out.mkdir(parents=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", choices=sorted(brand.SITES), default=None,
                    help=f"which site's bundle (default: MLL_SITE, else {brand.DEFAULT_SITE})")
    ap.add_argument("--runs", type=Path, default=REPO / "runs",
                    help="lingua: source data folder (default runs/; a worktree falls back to the main checkout's)")
    ap.add_argument("--out", type=Path, default=REPO / "dist" / "site_data")
    ap.add_argument("--sets", action="append", default=None, help="lingua: set folders to include (glob; default demo_*)")
    ap.add_argument("--no-quantize", action="store_true", help="lingua: copy pictures byte for byte")
    ap.add_argument("--no-bilingual", action="store_true", help="lingua: leave out the bilingual results")
    ap.add_argument("--allow-missing-patterns", action="store_true",
                    help="build even if .githooks/private_patterns.txt can't be found")
    ap.add_argument("--stage", type=Path, help="also assemble a Hugging Face Space folder for the site here")
    args = ap.parse_args()
    site = brand.site_key(args.site)

    out = args.out.resolve()
    (build_plato if site == "plato" else build_lingua)(args, out)

    print("Size:")
    report_size(out)
    print("Privacy checks:")
    problems = check_bundle(out, require_patterns=not args.allow_missing_patterns)
    if problems:
        print("  FAILED:\n    " + "\n    ".join(problems))
        print("Don't deploy this bundle. Fix the source data or the bundle rules, then build again.")
        return 1
    print("  passed: data-guard extensions and private patterns, no audio, no API key, no human drawings, "
          "no participant data, no local paths")
    if args.stage:
        stage_space(out, args.stage.resolve(), site)
    return 0


if __name__ == "__main__":
    sys.exit(main())
