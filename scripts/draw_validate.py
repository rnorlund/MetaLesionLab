"""Draw your chair: check that the /draw scores make sense on real drawings (no API calls).

1. Muse Image's first-run doodles (the PNGs) through ink_crop and the web model: they should land at
   Muse's prototype (small distance, closer than nearly all people's drawings).
2. People's drawings from the experiment: rendered from their stored strokes, their embeddings must
   match the experiment's cached ones (this checks the CPU model and the rendering); normalised again
   by the visitor's stroke path, they move by about a pixel (this shows the pipeline's sensitivity).
3. Held-out people's drawings (Quick, Draw! drawings after the 200 the reference uses, streamed from the
   public bucket) through the stroke path: their originality percentiles should spread over 0-100,
   roughly uniformly, since they are new draws from the same population.

Writes $PLATO_DIR/draw_validation.json (outside the repository) and prints a summary.

    python scripts/draw_validate.py [--keys chair ...] [--held-out 50]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from metalesionlab import draw  # noqa: E402
from metalesionlab.plato import (BY_KEY, PLATO_DIR, ink_crop, load_dir, render_strokes,  # noqa: E402
                                 stream_quickdraw)


def stream_with_retry(category: str, keep: int, tries: int = 6) -> list[dict]:
    for i in range(tries):
        try:
            return stream_quickdraw(category, keep=keep, max_lines=keep * 3)
        except Exception as e:  # DNS on this Mac drops out now and then
            wait = min(120, 5 * 2 ** i)
            print(f"  {category}: {type(e).__name__}: {e}; retry in {wait}s", flush=True)
            time.sleep(wait)
    raise SystemExit(f"couldn't stream {category}")


def summary(values) -> dict:
    a = np.asarray(values, dtype=float)
    return {"n": int(a.size), "mean": round(float(a.mean()), 3), "median": round(float(np.median(a)), 3),
            "q10": round(float(np.quantile(a, 0.1)), 3), "q90": round(float(np.quantile(a, 0.9)), 3),
            "min": round(float(a.min()), 3), "max": round(float(a.max()), 3)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--held-out", type=int, default=50)
    ap.add_argument("--in-sample", type=int, default=20)
    args = ap.parse_args()
    ref = draw.Reference.load()
    keys = args.keys or list(ref.entries)
    embed = draw.load_embedder()
    print(f"embedder: {embed.backend}")
    out = {"backend": embed.backend, "concepts": {}}
    all_ai, all_held, all_cos, all_direct = [], [], [], []

    for key in keys:
        res = {}
        # 1. Muse's doodles
        files = load_dir(PLATO_DIR / "ai" / "doodle" / key)
        vecs = embed([ink_crop(Image.open(f).convert("RGB")) for f in files])
        stored = np.load(PLATO_DIR / "embeddings" / "ai_doodle" / f"{key}.npz")["cls"]
        cos_ai = (draw.unit(vecs) * draw.unit(stored)).sum(1)
        ai_scores = [ref.score(key, v) for v in vecs]
        res["muse"] = {
            "n": len(files), "cos_to_cached_embedding_min": round(float(cos_ai.min()), 5),
            "d_ai": summary([s["d_ai"] for s in ai_scores]),
            "people_closer_to_muse_pct": summary([s["people_closer_to_muse"] for s in ai_scores]),
            "originality_pct": summary([s["originality"] for s in ai_scores]),
            "own_concept_top3": float(np.mean([s["own_rank"] <= 3 for s in ai_scores])),
        }
        all_ai += ai_scores

        # 2. people's drawings from the reference. Their strokes are already in Quick, Draw! form, so
        # rendering them directly must reproduce the cached embeddings; running the normalisation again
        # moves them by about a pixel, which shows how sensitive the pipeline is to tiny shifts.
        lines = (PLATO_DIR / "human" / key / "strokes.ndjson").read_text().splitlines()
        recs = [json.loads(line) for line in lines]
        k = min(args.in_sample, len(recs))
        stored = draw.unit(np.load(PLATO_DIR / "embeddings" / "human" / f"{key}.npz")["cls"][:k])
        direct = embed([ink_crop(render_strokes(r["drawing"])) for r in recs[:k]])
        again = embed([draw.render(r["drawing"]) for r in recs[:k]])
        cos_direct = (draw.unit(direct) * stored).sum(1)
        cos_h = (draw.unit(again) * stored).sum(1)
        res["people_in_sample"] = {"n": k, "cos_direct": summary(cos_direct), "cos_renormalised": summary(cos_h)}
        all_cos += cos_h.tolist()
        all_direct += cos_direct.tolist()

        # 3. held-out people's drawings
        if args.held_out:
            used = {r["key_id"] for r in recs}
            stream = stream_with_retry(BY_KEY[key].quickdraw, keep=len(recs) + args.held_out + 20)
            held = [r for r in stream if r["key_id"] not in used][:args.held_out]
            vecs = embed([draw.render(r["drawing"]) for r in held])
            hs = [ref.score(key, v) for v in vecs]
            pct = np.array([s["originality"] for s in hs])
            res["people_held_out"] = {
                "n": len(held), "originality_pct": summary(pct),
                "by_quarter": [int(((pct >= lo) & (pct < lo + 25)).sum()) for lo in (0, 25, 50, 75)][:3] +
                              [int((pct >= 75).sum())],
                "people_closer_to_muse_pct": summary([s["people_closer_to_muse"] for s in hs]),
                "d_ai": summary([s["d_ai"] for s in hs]),
                "own_concept_top3": float(np.mean([s["own_rank"] <= 3 for s in hs])),
            }
            all_held += hs
        out["concepts"][key] = res
        m = res["muse"]
        h = res.get("people_held_out", {})
        print(f"{key:9s} Muse: d_ai median {m['d_ai']['median']:.3f}, people closer to Muse "
              f"{m['people_closer_to_muse_pct']['median']:.0f}%, originality {m['originality_pct']['median']:.0f}%; "
              f"people direct cos {res['people_in_sample']['cos_direct']['min']:.4f}+, "
              f"renormalised median {res['people_in_sample']['cos_renormalised']['median']:.3f}; "
              f"held-out n={h.get('n')}: originality mean {h.get('originality_pct', {}).get('mean')}, "
              f"quarters {h.get('by_quarter')}, d_ai median {h.get('d_ai', {}).get('median')}", flush=True)

    if all_held:
        from scipy.stats import kstest

        pct = np.array([s["originality"] for s in all_held]) / 100
        out["overall_held_out"] = {
            "n": len(all_held), "originality_pct": summary(pct * 100),
            "deciles": np.histogram(pct, bins=10, range=(0, 1))[0].tolist(),
            "ks_vs_uniform_p": round(float(kstest(pct, "uniform").pvalue), 4),
            "d_ai": summary([s["d_ai"] for s in all_held]),
            "own_concept_top3": float(np.mean([s["own_rank"] <= 3 for s in all_held])),
        }
    out["overall_muse"] = {"n": len(all_ai), "d_ai": summary([s["d_ai"] for s in all_ai]),
                           "people_closer_to_muse_pct": summary([s["people_closer_to_muse"] for s in all_ai]),
                           "originality_pct": summary([s["originality"] for s in all_ai])}
    out["overall_people_direct_cos"] = summary(all_direct)
    out["overall_people_renormalised_cos"] = summary(all_cos)
    path = PLATO_DIR / "draw_validation.json"
    path.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k.startswith("overall")}, indent=1))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
