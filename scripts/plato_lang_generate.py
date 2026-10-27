"""Draw doodles with Muse Image from the same prompt in six languages.

Saves $PLATO_LANG_DIR/ai/<lang>/<concept>/NN.png (512 px) and logs each image in
ai/manifest.jsonl. Resumes: cells that already have enough images are skipped.
Cost: $0.01 per image (10 concepts x 6 languages x 10 images = $6.00). Stops if the shared
ledger total passes $40.

Usage: python scripts/plato_lang_generate.py [--n 10] [--concepts house,chair] [--langs en,es]
                                             [--max-usd 6.00] [--workers 8]
"""
import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.meta_api import IMAGE_PRICE, BudgetExceeded, MetaAPI, spent  # noqa: E402
from metalesionlab.plato_lang import CONCEPTS, LANGS, OUT, save_png  # noqa: E402

MAX_PER_CALL = 10  # the API's limit for n
PROJECT_STOP_USD = 40.0  # stop if the shared ledger passes this
RETRIES = 7  # waits of 10, 20, 40, 80, 120, 120, 120 s ride out a few minutes of network trouble
lock = threading.Lock()


def my_images(manifest: Path) -> int:
    if not manifest.exists():
        return 0
    return sum(1 for line in manifest.read_text().splitlines() if line.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--concepts", default=",".join(CONCEPTS))
    ap.add_argument("--langs", default=",".join(LANGS))
    ap.add_argument("--max-usd", type=float, default=6.00, help="cap on this experiment's image spend")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    prompts = json.loads((OUT / "prompts.json").read_text())
    manifest = OUT / "ai" / "manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    api = MetaAPI()

    jobs = []
    for concept in args.concepts.split(","):
        for lang in args.langs.split(","):
            folder = OUT / "ai" / lang / concept
            have = len(list(folder.glob("*.png"))) if folder.exists() else 0
            for start in range(have, args.n, MAX_PER_CALL):
                jobs.append((lang, concept, start, min(MAX_PER_CALL, args.n - start)))
    planned = sum(j[3] for j in jobs) * IMAGE_PRICE
    already = my_images(manifest) * IMAGE_PRICE
    print(f"{len(jobs)} calls, {planned / IMAGE_PRICE:.0f} images, ${planned:.2f} (spent so far ${already:.2f})")
    if already + planned > args.max_usd + 1e-9:
        sys.exit(f"would exceed --max-usd {args.max_usd}")
    if (total := spent()) + planned > PROJECT_STOP_USD:
        sys.exit(f"shared ledger is at ${total:.2f}; this batch would pass ${PROJECT_STOP_USD:.0f}")
    print(f"shared ledger before this batch: ${total:.2f}")

    def run(job):
        lang, concept, start, n = job
        if spent() > PROJECT_STOP_USD:
            print(f"  {lang}/{concept}: skipped, shared ledger passed ${PROJECT_STOP_USD:.0f}", flush=True)
            return 0
        prompt = prompts[lang][concept]["prompt"]
        for attempt in range(RETRIES):
            try:
                images = api.generate_images(prompt, n=n, output_format="png")
                break
            except BudgetExceeded:
                raise
            except Exception as e:  # noqa: BLE001 - DNS, connection and server errors: back off and retry
                wait = min(120, 10 * 2 ** attempt)
                print(f"  {lang}/{concept}: {type(e).__name__}: {e}; retry {attempt + 1} in {wait}s", flush=True)
                time.sleep(wait)
        else:
            return 0
        folder = OUT / "ai" / lang / concept
        for i, img in enumerate(images):
            path = folder / f"{start + i:02d}.png"
            save_png(img, path)
            with lock, manifest.open("a") as f:
                f.write(json.dumps({"lang": lang, "concept": concept, "file": str(path.relative_to(OUT)),
                                    "prompt": prompt, "ts": round(time.time(), 1)}, ensure_ascii=False) + "\n")
        print(f"  {lang}/{concept}: +{len(images)}", flush=True)
        return len(images)

    with ThreadPoolExecutor(args.workers) as pool:
        made = sum(pool.map(run, jobs))
    print(f"made {made} images; experiment image spend now ${my_images(manifest) * IMAGE_PRICE:.2f}")


if __name__ == "__main__":
    main()
