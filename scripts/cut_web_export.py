"""What can I cut? Ship a compact copy of the results with the web app.

runs/ is not in the repository, so a deployed site can't read runs/compress/glimmer.json. This writes
metalesionlab/web/data/cut_glimmer.json: the report from `what_can_i_cut.py export`, unchanged, plus
the guard answers each measured cut lost (from pruned.json), and a size check (at most 200 KB).
The /lab/cut page reads TOT_DATA_DIR/compress/glimmer.json when it exists and this copy otherwise.

Usage: python scripts/cut_web_export.py [--runs runs/compress]   (no GPU, no API calls)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "metalesionlab" / "web" / "data" / "cut_glimmer.json"
MAX_BYTES = 200 * 1024


def answers_lost(pruned: dict) -> dict[str, list[dict]]:
    """For each measured cut, the guard pictures named correctly intact and wrongly after the cut."""
    cuts = pruned.get("cuts") or {}
    base = {(it["word"], it["lang"]): it for it in (cuts.get("intact") or {}).get("items", [])}
    out = {}
    for name, cut in cuts.items():
        if name == "intact":
            continue
        lost = []
        for it in cut.get("items", []):
            b = base.get((it["word"], it["lang"]))
            if b and b.get("code") == "Correct" and it.get("code") != "Correct":
                said = str(it.get("said") or "").split("</")[0].strip()
                lost.append({"word": it["word"], "lang": it["lang"], "said": said[:60], "code": it.get("code")})
        out[name] = lost
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=REPO / "runs" / "compress")
    args = ap.parse_args()
    report = json.loads((args.runs / "glimmer.json").read_text())
    pruned_path = args.runs / "pruned.json"
    if pruned_path.exists():
        report["answers_lost"] = answers_lost(json.loads(pruned_path.read_text()))
    text = json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(text.encode()) > MAX_BYTES:
        raise SystemExit(f"cut_glimmer.json would be {len(text.encode()) // 1024} KB; trim it below 200 KB")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(REPO)} ({len(text.encode()) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
