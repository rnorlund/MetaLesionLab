"""Re-code Model Lab answers with the Muse Spark meaning judge (no GPU needed).

The GPU box codes answers without the judge, so associations ("milk" for cat) and every Spanish
meaning relation count as Unrelated there. This re-codes each condition file in place, rebuilds
index.json and, with --names, writes the set's glimmer_names.json from the intact condition.

Usage: python scripts/rescore_lesions.py runs/lesion/demo_en [--names runs/sets/demo_en]
"""
import argparse
import json
from pathlib import Path

from metalesionlab import meta_api
from metalesionlab.meta_api import MetaAPI
from metalesionlab.model_lab import rescore_result, save_result, write_index
from metalesionlab.naming_errors import spark_semantic_judge


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("result_dir", type=Path)
    ap.add_argument("--names", type=Path, help="set folder to write glimmer_names.json into")
    ap.add_argument("--judge-cache", type=Path, default=None)
    args = ap.parse_args()

    before = meta_api.spent()
    judge = spark_semantic_judge(MetaAPI(), cache_path=args.judge_cache)
    for f in sorted(args.result_dir.glob("*.json")):
        if f.name == "index.json" or f.name.startswith("severity_"):
            continue
        r = json.loads(f.read_text())
        old = dict(r["counts"])
        save_result(rescore_result(r, judge), f)
        if r["counts"] != old:
            print(f"{f.name}: {old} -> {r['counts']}")
        if args.names and r["condition"] == "intact":
            names = {row["word"]: {"name": row["said"], "code": row["code"]} for row in r["items"]}
            (args.names / "glimmer_names.json").write_text(json.dumps(names, ensure_ascii=False, indent=1))
            print(f"glimmer_names.json: {sum(v['code'] == 'Correct' for v in names.values())}/{len(names)} correct")
    write_index(args.result_dir)
    print(f"judge spend ${meta_api.spent() - before:.4f}")


if __name__ == "__main__":
    main()
