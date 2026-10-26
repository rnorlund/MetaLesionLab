"""Check the Scorer with real Meta API calls. Speech is synthesized with macOS `say`; no recordings of
real people are used. Outputs go to runs/scorer/.

Usage:
  python scripts/verify_scorer.py rater [--images DIR]   second rater vs. the rule-based coder (~$0.05)
  python scripts/verify_scorer.py scenes                 one English and one Spanish scene (~$0.05)
  python scripts/verify_scorer.py describe SCENE_JSON VOICE "TEXT" [--label L]   speak, transcribe, score
  python scripts/verify_scorer.py fluency                planted repetitions and intrusions, en + es
--images is a Test Studio candidates folder holding spoon_1.png, ladder_1.png and pineapple_0.png,
used for the Visual cases.
"""
import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from metalesionlab.audio import duration_s, to_wav16k
from metalesionlab.meta_api import REPO_ROOT, MetaAPI, spent
from metalesionlab.naming_errors import classify, spark_semantic_judge
from metalesionlab.scorer import agreement, make_scene, score_description, score_fluency, second_rater

OUT = REPO_ROOT / "runs" / "scorer"

NAMING_PAIRS = [  # (lang, target, response)
    ("en", "cat", "cat"), ("en", "cat", "a black cat"), ("en", "cat", "dog"), ("en", "cat", "hat"),
    ("en", "cat", "rat"), ("en", "skirt", "shirt"), ("en", "anchor", "ankle"), ("en", "kettle", "kettin"),
    ("en", "ladder", "blorf"), ("en", "bench", "a seat in the park"), ("en", "cat", "I don't know"),
    ("en", "umbrella", "rain"), ("en", "cat", "chair"), ("en", "bench", "river"), ("en", "cat", "cag"),
    ("en", "couch", "sofa"), ("en", "carrot", "parrot"), ("en", "hammer", "screwdriver"),
    ("en", "elephant", "elegant"), ("en", "glove", "mitten"),
    ("es", "gato", "perro"), ("es", "gato", "pato"), ("es", "gato", "no sé"), ("es", "gato", "gapo"),
    ("es", "gato", "silla"), ("es", "cuchara", "tenedor"), ("es", "mesa", "masa"),
    ("es", "banco", "un asiento en el parque"), ("es", "llave", "llavo"), ("es", "zapato", "blinfo"),
]
# Visual errors need the picture. The fork case checks that a picture doesn't turn Semantic into Visual.
VISUAL_PAIRS = [("spoon_1.png", "spoon", "racket"), ("ladder_1.png", "ladder", "easel"),
                ("pineapple_0.png", "pineapple", "grenade"), ("spoon_1.png", "spoon", "fork")]


def synth(text: str, voice: str, fmt: str = "wav") -> bytes:
    """Speak `text` with macOS `say`; "wav" is 16 kHz mono via afconvert, "webm" is Opus like a browser."""
    with tempfile.TemporaryDirectory() as tmp:
        aiff, out = Path(tmp) / "s.aiff", Path(tmp) / f"s.{fmt}"
        subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)
        if fmt == "wav":
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(out)], check=True)
        else:
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(aiff), "-c:a", "libopus",
                            "-b:a", "32k", str(out)], check=True)
        return out.read_bytes()


def run_rater(api: MetaAPI, images: Path | None) -> dict:
    judge = spark_semantic_judge(api)
    rows = []
    for lang, target, response in NAMING_PAIRS:
        rule = classify(target, response, lang, judge=judge).code
        spark = second_rater(api, target, response, lang)
        rows.append({"lang": lang, "target": target, "response": response, "rule": rule, **spark})
        print(f"{lang} {target:9s} {response!r:28s} rule={rule:11s} spark={spark['code']:11s} {spark['rationale']}")
    stats = agreement([r["rule"] for r in rows], [r["code"] for r in rows])
    for lang in ("en", "es"):
        sub = [r for r in rows if r["lang"] == lang]
        stats[lang] = agreement([r["rule"] for r in sub], [r["code"] for r in sub])
    print(f"\nagreement: {stats}")
    visual = []
    if images:
        for file, target, response in VISUAL_PAIRS:
            image = (images / file).read_bytes()
            rule = classify(target, response, "en", judge=judge).code
            spark = second_rater(api, target, response, "en", image=image)
            visual.append({"image": file, "target": target, "response": response, "rule": rule, **spark})
            print(f"picture {target:9s} {response!r:10s} rule={rule:11s} spark={spark['code']:11s} {spark['rationale']}")
    result = {"pairs": rows, "agreement": stats, "visual": visual,
              "disagreements": [r for r in rows if r["rule"] != r["code"]]}
    (OUT / "second_rater.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return result


def run_scenes(api: MetaAPI) -> None:
    for lang, theme in (("en", None), ("es", "un mercado al aire libre")):
        scene = make_scene(api, lang, theme, out_dir=OUT / "scenes")
        print(json.dumps({k: scene[k] for k in ("id", "image_file", "description", "content_units", "has_text",
                                                 "draws")}, ensure_ascii=False, indent=1))


def run_describe(api: MetaAPI, scene_file: Path, voice: str, text: str, label: str) -> None:
    scene = json.loads(scene_file.read_text())
    wav = synth(text, voice)
    secs = duration_s(wav)
    transcript = api.transcribe(wav, language=scene["lang"])["transcript"]
    scores = score_description(api, transcript, scene, scene["lang"], secs)
    result = {"scene": scene["id"], "voice": voice, "spoken": text, "transcript": transcript,
              "duration_s": round(secs, 2), "scores": scores}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    (OUT / f"description_{scene['id']}_{label}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))


FLUENCY_LISTS = [  # (lang, voice, category, spoken items); pauses go between items
    ("en", "Samantha", "animals", ["dog", "cat", "horse", "dog", "table", "lion"]),
    ("en", "Samantha", "animals", ["dog", "cat", "horse", "um", "dog", "table", "lion", "tigers", "the elephant",
                                   "let me think", "giraffe", "zebra", "a tiger", "polar bear", "chair"]),
    ("es", "Paulina", "animales", ["perro", "gato", "caballo", "perro", "mesa", "león"]),
    ("es", "Paulina", "animales", ["perro", "gato", "caballo", "eh", "perro", "mesa", "león", "tigres",
                                   "el elefante", "a ver", "jirafa", "cebra", "un tigre", "oso polar", "silla"]),
]


def run_fluency(api: MetaAPI) -> None:
    results = []
    for lang, voice, category, items in FLUENCY_LISTS:
        spoken = " [[slnc 700]] ".join(items)
        recording = synth(spoken, voice, fmt="webm")  # the browser path: webm/Opus -> to_wav16k
        wav = to_wav16k(recording, ".webm")
        transcript = api.transcribe(wav, language=lang)["transcript"]
        scores = score_fluency(api, transcript, category, lang)
        results.append({"lang": lang, "category": category, "spoken": items, "duration_s": round(duration_s(wav), 2),
                        "transcript": transcript, "scores": scores})
        print(f"\n{lang} spoken: {', '.join(items)}\n   transcript: {transcript!r}")
        print(f"   count={scores['count']} valid={scores['valid']}\n   repetitions={scores['repetitions']} "
              f"intrusions={scores['intrusions']}")
    (OUT / "fluency.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=["rater", "scenes", "describe", "fluency"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--images", type=Path)
    ap.add_argument("--label", default="full")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    api, t0, cost0 = MetaAPI(), time.time(), spent()
    if a.task == "rater":
        run_rater(api, a.images)
    elif a.task == "scenes":
        run_scenes(api)
    elif a.task == "describe":
        run_describe(api, Path(a.args[0]), a.args[1], a.args[2], a.label)
    else:
        run_fluency(api)
    print(f"\n{a.task}: {time.time() - t0:.0f}s, ${spent() - cost0:.4f}")


if __name__ == "__main__":
    main()
