"""Plato's Forms, the Platonic clock: analysis of Muse Spark's readings (docs/plato_forms_plan.md).

  analyze                         -> $PLATO_FORMS_DIR/results_clock.json
  spotcheck-sheet                 the pre-registered by-eye sample (60 pictures, seeded) as numbered
                                  contact sheets in clock/spotcheck/, WITHOUT Spark's readings
  spotcheck-score                 compares clock/spotcheck/byeye.json (the analyst's readings) with Spark's

Readings come from scripts/plato_forms_read.py read (reader spark-v1-minimal, fixed by the validation).
Primary 10:10 share: all pictures in the denominator (no hands or unreadable = not 10:10); secondary:
pictures with a read time. Time-asked measures get CIs from a cluster bootstrap over requested times.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from scipy.stats import binomtest, fisher_exact  # noqa: E402

from metalesionlab.plato import QUICKDRAW_CREDIT, ci, to_jsonable  # noqa: E402
from metalesionlab.plato_forms import (CORRECT, FORMS_DIR, WINDOW, chance_ten_ten, fmt_time,  # noqa: E402
                                       is_ten_ten, is_ten_ten_hour_slack, parse_time, time_distance,
                                       time_distance_hour_slack, unslug, wilson_ci)

READER = "spark-v1-minimal"
CLOCK = FORMS_DIR / "clock"
BOOT = 10000
GROUPS = {  # name -> (source, condition filter: 'any', 'asked' or 'default' for people)
    "muse_doodle_default": ("muse_doodle", "any"), "muse_doodle_asked": ("muse_doodle", "asked"),
    "muse_photo_default": ("muse_photo", "any"), "muse_photo_asked": ("muse_photo", "asked"),
    "sdxl_doodle_default": ("sdxl_doodle", "any"), "sdxl_doodle_asked": ("sdxl_doodle", "asked"),
    "sdxl_photo_default": ("sdxl_photo", "any"), "sdxl_photo_asked": ("sdxl_photo", "asked"),
    "people": ("people", "default"),
}


def readings(reader: str = READER) -> list[dict]:
    path = CLOCK / "readings" / f"{reader}.jsonl"
    rows = {}
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["path"]] = r  # a re-read replaces an earlier line
    return list(rows.values())


def in_group(r: dict, source: str, cond: str) -> bool:
    if r["source"] != source:
        return False
    if cond == "asked":
        return r["cond"] != "any"
    return r["cond"] == cond


def share(k: int, n: int) -> dict:
    return {"k": k, "n": n, "share": k / n if n else float("nan"), "ci95": wilson_ci(k, n)}


def cluster_boot(rows: list[dict], fn, rng, reps: int = BOOT) -> list[float]:
    """CI of fn(rows) resampling requested times (clusters) with replacement."""
    by = {}
    for r in rows:
        by.setdefault(r["cond"], []).append(r)
    keys = list(by)
    vals = []
    for _ in range(reps):
        pick = rng.choice(len(keys), len(keys), replace=True)
        vals.append(fn([r for i in pick for r in by[keys[i]]]))
    return ci(np.array(vals))


def group_stats(rows: list[dict], asked: bool, rng) -> dict:
    n = len(rows)
    t = [parse_time(r["time"]) for r in rows]
    status = Counter(r["status"] for r in rows)
    k1010 = sum(is_ten_ten(x) for x in t)
    readable = sum(x is not None for x in t)
    chance = chance_ten_ten()
    out = {"n": n, "status": dict(status), "share_no_hands": status.get("no_hands", 0) / n if n else None,
           "ten_ten": share(k1010, n), "ten_ten_of_readable": share(k1010, readable),
           "ten_ten_p_vs_chance": binomtest(k1010, n, chance, alternative="two-sided").pvalue if n else None,
           "ten_ten_exact": sum(x == (10, 10) for x in t),
           "times": Counter(fmt_time(x) for x in t if x is not None).most_common()}  # every read time, with its count
    # post hoc sensitivity (see plato_forms.is_ten_ten_hour_slack): the read hour may be one off
    k_slack = sum(is_ten_ten_hour_slack(x) for x in t)
    out["ten_ten_hour_slack"] = share(k_slack, n)
    out["ten_ten_hour_slack_p_vs_chance"] = binomtest(k_slack, n, chance_ten_ten(hour_slack=True)).pvalue if n else None
    if asked:
        def acc(rs, either=False):
            ok = [parse_time(r["time"]) is not None and
                  time_distance(parse_time(r["time"]), parse_time(unslug(r["cond"])), either) <= CORRECT for r in rs]
            return float(np.mean(ok)) if rs else float("nan")

        def tt(rs):
            return float(np.mean([is_ten_ten(parse_time(r["time"])) for r in rs])) if rs else float("nan")

        def acc_slack(rs):
            ok = [parse_time(r["time"]) is not None and
                  time_distance_hour_slack(parse_time(r["time"]), parse_time(unslug(r["cond"]))) <= CORRECT for r in rs]
            return float(np.mean(ok)) if rs else float("nan")

        def minute_ok(r):
            x = parse_time(r["time"])
            if x is None:
                return False
            d = abs(x[1] - parse_time(unslug(r["cond"]))[1]) % 60
            return min(d, 60 - d) <= CORRECT

        out["accuracy_hour_slack"] = acc_slack(rows)
        out["accuracy_hour_slack_ci95_cluster"] = cluster_boot(rows, acc_slack, rng)
        out["minute_correct"] = float(np.mean([minute_ok(r) for r in rows]))
        errs = [time_distance(x, parse_time(unslug(r["cond"]))) for r, x in zip(rows, t) if x is not None]
        hour_ok = [x[0] == parse_time(unslug(r["cond"]))[0] for r, x in zip(rows, t) if x is not None]
        out.update({
            "accuracy": acc(rows), "accuracy_ci95_cluster": cluster_boot(rows, acc, rng),
            "accuracy_either_order": acc(rows, True),
            "accuracy_either_order_ci95_cluster": cluster_boot(rows, lambda rs: acc(rs, True), rng),
            "ten_ten_ci95_cluster": cluster_boot(rows, tt, rng),
            "hour_correct_of_readable": float(np.mean(hour_ok)) if hour_ok else None,
            "median_error_min": float(np.median(errs)) if errs else None,
            "mean_error_min": float(np.mean(errs)) if errs else None,
            "per_time": {},
        })
        for cond in sorted({r["cond"] for r in rows}, key=lambda s: parse_time(unslug(s))):
            rs = [r for r in rows if r["cond"] == cond]
            ts = [parse_time(r["time"]) for r in rs]
            want = parse_time(unslug(cond))
            out["per_time"][unslug(cond)] = {
                "n": len(rs), "correct": sum(x is not None and time_distance(x, want) <= CORRECT for x in ts),
                "correct_either_order": sum(x is not None and time_distance(x, want, True) <= CORRECT for x in ts),
                "ten_ten": sum(is_ten_ten(x) for x in ts), "no_time": sum(x is None for x in ts),
                "read": [fmt_time(x) for x in ts]}
    return out


def fisher(a: dict, b: dict) -> dict:
    t = [[a["k"], a["n"] - a["k"]], [b["k"], b["n"] - b["k"]]]
    odds, p = fisher_exact(t)
    return {"difference": a["share"] - b["share"], "odds_ratio": float(odds), "p": float(p)}


def cmd_analyze(args):
    rng = np.random.default_rng(20261027)
    rows = readings(args.reader)
    res = {"experiment": "The Platonic clock: what time does an AI draw?", "reader": args.reader,
           "window_min": WINDOW, "correct_within_min": CORRECT, "chance_ten_ten": chance_ten_ten(),
           "chance_ten_ten_hour_slack": chance_ten_ten(hour_slack=True),
           "human_data": QUICKDRAW_CREDIT, "groups": {}}
    for name, (source, cond) in GROUPS.items():
        g = [r for r in rows if in_group(r, source, cond)]
        if g:
            res["groups"][name] = group_stats(g, cond == "asked", rng)
    G = res["groups"]
    comp = {}
    for a, b in [("muse_doodle_default", "people"), ("sdxl_doodle_default", "people"),
                 ("muse_doodle_default", "sdxl_doodle_default"), ("muse_photo_default", "sdxl_photo_default"),
                 ("muse_doodle_asked", "sdxl_doodle_asked"), ("muse_doodle_default", "muse_doodle_asked"),
                 ("sdxl_doodle_default", "sdxl_doodle_asked")]:
        if a in G and b in G:
            comp[f"{a} vs {b}"] = fisher(G[a]["ten_ten"], G[b]["ten_ten"])
    res["comparisons_ten_ten"] = comp
    chance = res["chance_ten_ten"]
    pred = {}
    if "muse_doodle_default" in G:
        g = G["muse_doodle_default"]
        pred["C1_muse_default_mostly_1010"] = g["ten_ten"]["share"] >= 0.5 and g["ten_ten_p_vs_chance"] < 0.05
    if "muse_doodle_asked" in G:
        g = G["muse_doodle_asked"]
        pred["C2_muse_ignores_asked_time"] = (g["ten_ten"]["share"] >= 0.25 and g["ten_ten"]["share"] > chance
                                              and g["ten_ten_p_vs_chance"] < 0.05 and g["accuracy"] < 0.5)
    if "sdxl_doodle_default" in G and "muse_doodle_default" in G:
        g = G["sdxl_doodle_default"]
        pred["C3_sdxl_default_above_chance_below_muse"] = (g["ten_ten"]["share"] > chance and g["ten_ten_p_vs_chance"] < 0.05
                                                           and g["ten_ten"]["share"] < G["muse_doodle_default"]["ten_ten"]["share"])
    if "sdxl_doodle_asked" in G:
        pred["C4_sdxl_rarely_draws_asked_time"] = G["sdxl_doodle_asked"]["accuracy"] < 0.25
    if "people" in G and "muse_doodle_default" in G:
        pred["C5_people_rarely_1010"] = (G["people"]["ten_ten"]["share"] < 0.15 and
                                         comp["muse_doodle_default vs people"]["p"] < 0.05 and
                                         G["people"]["ten_ten"]["share"] < G["muse_doodle_default"]["ten_ten"]["share"])
    res["predictions"] = {k: bool(v) for k, v in pred.items()}
    eye = CLOCK / "spotcheck" / "byeye_no_time_sets.json"
    res["byeye_no_time"] = json.loads(eye.read_text()) if eye.exists() else None
    sc = CLOCK / "spotcheck" / "score.json"
    res["spotcheck"] = json.loads(sc.read_text()) if sc.exists() else None
    val = CLOCK / "readings" / f"validation_{args.reader}.jsonl"
    if val.exists():
        res["validation"] = validation_summary(val)
    out = FORMS_DIR / "results_clock.json"
    out.write_text(json.dumps(to_jsonable(p_as_text(res)), indent=1))
    print(f"wrote {out}")
    report(res)


def p_as_text(x, key: str = ""):
    """A copy with p-values as text with 2 significant digits ('9.4e-07'): to_jsonable rounds floats to
    4 decimals, which would print tiny p-values as 0."""
    if isinstance(x, dict):
        return {k: p_as_text(v, k) for k, v in x.items()}
    if isinstance(x, list):
        return [p_as_text(v) for v in x]
    if isinstance(x, float) and (key == "p" or key.endswith("p_vs_chance")):
        return f"{x:.2g}"
    return x


def validation_summary(path: Path) -> dict:
    truth = {v["id"]: v for v in json.loads((CLOCK / "validation" / "truth.json").read_text())}
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    timed = [r for r in rows if truth[r["id"]]["time"]]
    d = [time_distance(parse_time(r["time"]), parse_time(truth[r["id"]]["time"])) if parse_time(r["time"]) else 999
         for r in timed]
    false = [r for r in timed if is_ten_ten(parse_time(r["time"])) and not is_ten_ten(parse_time(truth[r["id"]]["time"]))]
    n_not = sum(not is_ten_ten(parse_time(truth[r["id"]]["time"])) for r in timed)
    nh = [r for r in rows if not truth[r["id"]]["time"]]
    k = sum(x <= CORRECT for x in d)
    return {"n_timed": len(timed), "within5": share(k, len(timed)),
            "errors": [{"truth": truth[r["id"]]["time"], "read": r["time"], "style": truth[r["id"]]["style"]}
                       for r, x in zip(timed, d) if x > CORRECT],
            "false_ten_ten": share(len(false), n_not), "no_hands_found": share(sum(r["status"] == "no_hands" for r in nh), len(nh)),
            "styles": sorted({v["style"] for v in truth.values()})}


def report(res: dict) -> None:
    print(f"chance of about-10:10: {res['chance_ten_ten']:.3f}")
    for name, g in res["groups"].items():
        t = g["ten_ten"]
        line = (f"{name:22s} n={g['n']:3d} 10:10 {t['k']:3d} = {t['share']:.2f} [{t['ci95'][0]:.2f}, {t['ci95'][1]:.2f}] "
                f"p={g['ten_ten_p_vs_chance']:.2g} no-hands {g['share_no_hands']:.2f}")
        line += f" | slack 10:10 {g['ten_ten_hour_slack']['k']} = {g['ten_ten_hour_slack']['share']:.2f}"
        if "accuracy" in g:
            line += (f" | slack acc {g['accuracy_hour_slack']:.2f} {g['accuracy_hour_slack_ci95_cluster']} minute {g['minute_correct']:.2f}")
            line += (f" | accuracy {g['accuracy']:.2f} {g['accuracy_ci95_cluster']} either {g['accuracy_either_order']:.2f}"
                     f" hour {g['hour_correct_of_readable']:.2f} median err {g['median_error_min']}")
        print(line)
        print(f"   top times {g['times'][:6]}")
    for k, v in res["comparisons_ten_ten"].items():
        print(f"{k}: diff {v['difference']:.2f} p={v['p']:.2g}")
    print("predictions", res["predictions"])
    for name in ("muse_doodle_asked", "sdxl_doodle_asked", "muse_photo_asked", "sdxl_photo_asked"):
        if name in res["groups"]:
            print(name, {t: (x["correct"], x["ten_ten"], x["read"]) for t, x in res["groups"][name]["per_time"].items()})


# ---------- by-eye spot check (pre-registered: 60 pictures, seeded, blind to Spark's readings) ----------

SPOT = {"muse_doodle": 15, "sdxl_doodle": 15, "muse_photo": 5, "sdxl_photo": 5, "people": 20}


def spot_sample(rows: list[dict]) -> list[dict]:
    rng = np.random.default_rng(20261029)
    out = []
    for source, k in SPOT.items():
        pool = sorted([r for r in rows if r["source"] == source], key=lambda r: r["path"])
        out += [pool[i] for i in sorted(rng.choice(len(pool), k, replace=False))]
    return out


def picture_path(r: dict) -> Path:
    from plato_forms_read import SOURCES  # noqa: PLC0415

    root = SOURCES[r["source"]]
    return root / r["file"] if r["source"] == "people" else root / r["cond"] / r["file"]


def cmd_sheet(args):
    from PIL import Image, ImageDraw, ImageFont

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sample = spot_sample(readings(args.reader))
    folder = CLOCK / "spotcheck"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sample.json").write_text(json.dumps([{"i": i, "path": r["path"]} for i, r in enumerate(sample)], indent=1))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    cell, cols = 300, 5
    for page in range(0, len(sample), 20):
        chunk = sample[page:page + 20]
        rows_n = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell, rows_n * cell), "white")
        d = ImageDraw.Draw(sheet)
        for j, r in enumerate(chunk):
            im = Image.open(picture_path(r)).convert("RGB")
            im.thumbnail((cell - 20, cell - 40))
            x, y = (j % cols) * cell, (j // cols) * cell
            sheet.paste(im, (x + 10, y + 36))
            d.text((x + 8, y + 4), f"#{page + j}", fill="red", font=font)
        sheet.save(folder / f"sheet_{page // 20}.png")
    print(f"wrote {len(sample)} pictures to {folder}/sheet_*.png (no readings shown)")


def cmd_score(args):
    folder = CLOCK / "spotcheck"
    sample = json.loads((folder / "sample.json").read_text())
    eye = json.loads((folder / "byeye.json").read_text())  # {"0": "10:10" | "none" | "unclear", ...}
    by = {r["path"]: r for r in readings(args.reader)}
    agree, rows = 0, []
    n_scored = 0
    for s in sample:
        mine = eye.get(str(s["i"]))
        r = by[s["path"]]
        spark = parse_time(r["time"])
        if mine in (None, "unclear"):
            rows.append({"i": s["i"], "path": s["path"], "eye": mine, "spark": r["time"], "agree": None})
            continue
        n_scored += 1
        mt = parse_time(mine)
        ok = (mt is None and spark is None) or (mt is not None and spark is not None and time_distance(mt, spark, True) <= CORRECT)
        agree += ok
        rows.append({"i": s["i"], "path": s["path"], "eye": mine, "spark": r["time"], "agree": bool(ok),
                     "eye_1010": is_ten_ten(mt), "spark_1010": is_ten_ten(spark)})
    same1010 = sum(x["eye_1010"] == x["spark_1010"] for x in rows if x["agree"] is not None)
    out = {"n_sample": len(sample), "n_scored": n_scored, "agree": agree, "agreement": agree / max(n_scored, 1),
           "agree_on_ten_ten": same1010, "unclear_by_eye": len(sample) - n_scored,
           "by_source": {src: {"n": sum(1 for x in rows if x["path"].startswith(src + "/") and x["agree"] is not None),
                               "agree": sum(1 for x in rows if x["path"].startswith(src + "/") and x["agree"])}
                         for src in SPOT},
           "disagreements": [x for x in rows if x["agree"] is False], "rows": rows}
    (folder / "score.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("analyze", cmd_analyze), ("spotcheck-sheet", cmd_sheet), ("spotcheck-score", cmd_score)):
        p = sub.add_parser(name)
        p.add_argument("--reader", default=READER)
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
