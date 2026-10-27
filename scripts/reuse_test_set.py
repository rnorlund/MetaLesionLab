"""Make a picture-naming set in another language from an existing set's pictures: no new images.

Usage: python scripts/reuse_test_set.py NAME LANG WORDS_FILE [--from demo_en]
WORDS_FILE is the source set's word list translated, in the same order ("kessel: kettle" pins a meaning).
Output: runs/sets/NAME/ (manifest.json, candidates/)

The checks are Test Studio's, minus drawing: Muse Spark plans each word (accepted spellings, ambiguity
flags), then names the source set's kept picture in the language, and the name is coded with the
naming-error classifier. The second picture is named only when the first isn't coded Correct. SAM 3.1
results are copied from the source set, since SAM checks the English gloss. Used for the ten languages
added on Oct 27 (docs/languages.md); about $0.03 per 20-word set.
"""
import argparse
import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path

from metalesionlab.meta_api import REPO_ROOT, MetaAPI, image_data_url, spent
from metalesionlab.naming_errors import classify, phonemes, spark_semantic_judge, word_zipf
from metalesionlab.test_studio import _resized_png, naming_prompt, parse_word_list, plan_concepts


def name_picture(api: MetaAPI, image: bytes, lang: str) -> str:
    reply = api.chat([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": image_data_url(_resized_png(image, 512))}},
        {"type": "text", "text": naming_prompt(lang)},
    ]}])
    return reply.choices[0].message.content.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("lang")
    ap.add_argument("words_file")
    ap.add_argument("--from", dest="source", default="demo_en")
    args = ap.parse_args()

    src_dir, out_dir = REPO_ROOT / "runs" / "sets" / args.source, REPO_ROOT / "runs" / "sets" / args.name
    source = json.loads((src_dir / "manifest.json").read_text())
    concepts = parse_word_list(Path(args.words_file).read_text().splitlines())
    if len(concepts) != len(source["items"]):
        raise SystemExit(f"{args.words_file} has {len(concepts)} words; {args.source} has {len(source['items'])}")
    t0, cost0 = time.time(), spent()
    api = MetaAPI()
    judge = spark_semantic_judge(api)
    concepts = plan_concepts(api, concepts, args.lang)
    (out_dir / "candidates").mkdir(parents=True, exist_ok=True)
    items = []
    for concept, src in zip(concepts, source["items"]):
        results = []
        for k, c in enumerate(sorted(src["candidates"], key=lambda c: c["file"] != src["image"])):
            if not c["sam_ok"]:
                continue
            dst = out_dir / "candidates" / f"{concept.word}_{k}.png"
            shutil.copyfile(src_dir / c["file"], dst)
            name = name_picture(api, dst.read_bytes(), args.lang)
            code = classify(concept.word, name, args.lang, alternates=tuple(concept.alternates), judge=judge).code
            results.append({"file": str(dst.relative_to(out_dir)), "from": f"{args.source}/{c['file']}",
                            **{key: c[key] for key in ("sam_objects", "sam_confidence", "sam_area", "sam_ok")},
                            "spark_name": name, "spark_code": code, "spark_ok": code == "Correct"})
            if code == "Correct":
                break
        best = next((r for r in results if r["spark_ok"]), None)
        items.append({**asdict(concept), "lang": args.lang, "style": source["style"], "prompt": src["prompt"],
                      "zipf": round(word_zipf(concept.word, args.lang), 2),
                      "phonemes": len(phonemes(concept.word, args.lang)[0]),
                      "status": "kept" if best else "review", "image": best["file"] if best else None,
                      "candidates": results})
        names = ", ".join(f"{r['spark_name']} ({r['spark_code']})" for r in results)
        print(f"{items[-1]['status']:6s} {concept.word:14s} named: {names}")
    manifest = {"lang": args.lang, "style": source["style"], "pictures_from": args.source, "items": items}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    kept = sum(it["status"] == "kept" for it in items)
    print(f"\n{kept}/{len(items)} kept in {time.time() - t0:.0f}s for ${spent() - cost0:.2f} (shared ledger)")


if __name__ == "__main__":
    main()
