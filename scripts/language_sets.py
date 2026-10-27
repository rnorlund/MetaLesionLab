"""Name an English picture set in other languages, without drawing new pictures.

The bilingual test shows the same pictures in every language (metalesionlab/bilingual.py), so the
Spanish, French and Portuguese versions of a set reuse the English set's picture files. This
copies them into runs/sets/<prefix>_<lang>/ and writes a manifest with each language's names
from the word table (target first, then accepted alternates). It also adds the table's English
alternates to the English manifest.

--spark asks Muse Spark to name each kept picture in each language (one chat per picture, about
$0.0015), a check on the table's names; its answers are stored as spark_name and spark_code.

Usage: python scripts/language_sets.py core100 [--table scripts/wordlists/core100.json]
           [--langs es fr pt] [--spark]
"""
from __future__ import annotations

import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from metalesionlab.meta_api import REPO_ROOT, MetaAPI, image_data_url, retry_network, spent
from metalesionlab.naming_errors import LANGUAGE_NAMES, classify
from metalesionlab.test_studio import _resized_png, derive_language_manifest, merge_alternates


def spark_name(api: MetaAPI, image: bytes, lang: str) -> str:
    """Muse Spark's one-word name for a picture, with Test Studio's agreement prompt."""
    reply = api.chat([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": image_data_url(_resized_png(image, 512))}},
        {"type": "text", "text": f"Name the object in this picture with exactly one word in "
                                 f"{LANGUAGE_NAMES.get(lang, lang)}. Reply with the word only."},
    ]}])
    return reply.choices[0].message.content.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prefix")
    ap.add_argument("--table", type=Path, default=REPO_ROOT / "scripts" / "wordlists" / "core100.json")
    ap.add_argument("--langs", nargs="+", default=["es", "fr", "pt"])
    ap.add_argument("--spark", action="store_true", help="check the names with Muse Spark (paid)")
    args = ap.parse_args()

    sets = REPO_ROOT / "runs" / "sets"
    table = json.loads(args.table.read_text())["items"]
    en_dir = sets / f"{args.prefix}_en"
    en = merge_alternates(json.loads((en_dir / "manifest.json").read_text()),
                          {t["en"]: t["names"]["en"] for t in table})
    (en_dir / "manifest.json").write_text(json.dumps(en, ensure_ascii=False, indent=1))
    api = MetaAPI() if args.spark else None
    cost0 = spent()
    for lang in args.langs:
        out = sets / f"{args.prefix}_{lang}"
        manifest = derive_language_manifest(en, {t["en"]: t["names"][lang] for t in table}, lang, en_dir.name)
        if (out / "manifest.json").exists():  # keep an earlier Muse Spark check when only names change
            old = {it["gloss"]: it for it in json.loads((out / "manifest.json").read_text())["items"]}
            for it in manifest["items"]:
                prev = old.get(it["gloss"], {})
                if "spark_name" in prev and prev.get("image") == it["image"]:
                    it["spark_name"] = prev["spark_name"]
                    it["spark_code"] = classify(it["word"], prev["spark_name"], lang, tuple(it["alternates"])).code
        (out / "candidates").mkdir(parents=True, exist_ok=True)
        for it in manifest["items"]:
            for c in it["candidates"]:
                shutil.copy2(en_dir / c["file"], out / c["file"])
        if api:
            kept = [it for it in manifest["items"] if it["status"] == "kept"]

            def check(it):
                said = retry_network(lambda: spark_name(api, (out / it["image"]).read_bytes(), lang))
                it["spark_name"] = said
                it["spark_code"] = classify(it["word"], said, lang, tuple(it["alternates"])).code
                return it

            with ThreadPoolExecutor(8) as pool:
                list(pool.map(check, kept))
            agree = [it for it in kept if it["spark_code"] == "Correct"]
            print(f"{lang}: Muse Spark agrees on {len(agree)}/{len(kept)}")
            for it in kept:
                if it["spark_code"] != "Correct":
                    print(f"    {it['gloss']:12s} {it['word']:14s} spark: {it['spark_name']!r} ({it['spark_code']})")
        (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
        print(f"{lang}: {sum(it['status'] == 'kept' for it in manifest['items'])} kept pictures -> {out}")
    if api:
        print(f"spent ${spent() - cost0:.3f}")


if __name__ == "__main__":
    main()
