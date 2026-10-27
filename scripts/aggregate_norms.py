"""Aggregate the public naming test's reference-range contributions into public_data/.

Volunteers who finish the public test (/take) can add a summary of their result: language, set,
accuracy, median latency on correct answers, optional age band and the date; nothing else is
stored. Summaries collect in TOT_DATA_DIR/norms/<set>.jsonl. This script groups them by set and
set version (the exact pictures and words) and, for each group with at least 10 contributors,
writes public_data/naming_norms_<set>.json: n, mean, SD, 5th/50th/95th percentiles and range of
the number correct, the percent correct and the median latency, plus the age bands given. Groups
under 10 are reported and not written. Review the file before committing it.

    python scripts/aggregate_norms.py [--data-dir runs] [--min-n 10] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

from metalesionlab.assessment import NORMS_MIN_N, norms_summary
from metalesionlab.meta_api import REPO_ROOT

FIELDS = {"set", "set_version", "lang", "n_items", "correct", "accuracy_pct", "median_latency_ms", "age_band", "date"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=Path(os.environ.get("TOT_DATA_DIR", REPO_ROOT / "runs")))
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "public_data")
    ap.add_argument("--min-n", type=int, default=NORMS_MIN_N)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    files = sorted((args.data_dir / "norms").glob("*.jsonl"))
    if not files:
        print(f"No contributions in {args.data_dir / 'norms'} yet.")
        return 0
    for path in files:
        groups: dict[str, list[dict]] = defaultdict(list)
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if set(r) - FIELDS:  # only summaries belong here; anything else is refused, not published
                    raise SystemExit(f"{path}: unexpected fields {sorted(set(r) - FIELDS)}")
                groups[r["set_version"]].append(r)
        set_id = path.stem
        current = max(groups, key=lambda v: max(r["date"] for r in groups[v]))  # the version still collecting
        for version, records in sorted(groups.items(), key=lambda kv: kv[0] != current):
            stats = norms_summary(records, args.min_n)
            label = f"{set_id} version {version}{' (current)' if version == current else ''}: n = {stats['n']}"
            if not stats["ready"] or version != current:
                print(label + ("" if stats["ready"] else f" (needs {args.min_n}; not written)") +
                      ("" if version == current else " (older version; not written)"))
                continue
            dates = sorted(r["date"] for r in records)
            out = {
                "_about": ("Reference range for the Tippa Lingua public naming test: summaries contributed by adult "
                           "volunteers who reported no neurological or language condition and fluency in the test "
                           "language, scored automatically (Muse Voice Transcribe and the rule-based coder) exactly as "
                           "the public test scores everyone. Self-reported, self-selected volunteers; not clinical norms."),
                "set": set_id, "set_version": version, "lang": records[0]["lang"], "collected": [dates[0], dates[-1]],
                "written": time.strftime("%Y-%m-%d"), **stats, "source": "public_data",
            }
            target = args.out_dir / f"naming_norms_{set_id}.json"
            if args.dry_run:
                print(label + f" -> would write {target}")
            else:
                target.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
                print(label + f" -> wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
