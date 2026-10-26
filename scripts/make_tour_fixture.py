"""Record the guided tour's Scorer mini-session with the real pipeline.

Three spoken answers are synthesized with macOS `say`, converted to 16 kHz WAV with `afconvert`
and sent to a running app's POST /api/score/naming: Muse Voice Transcribe, the naming-error
classifier and the Muse Spark second rater, exactly as for a visitor. The replies are saved as
the fixture the tour replays, so the tour itself makes no API calls. No audio is committed.

Usage: python scripts/make_tour_fixture.py [--url http://127.0.0.1:8000] [--set demo_en]
"""
import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

ANSWERS = [("cat", "dog"), ("anchor", "ankle"), ("umbrella", "umbrella")]  # (target, what the speaker says)
VOICE = "Samantha"
OUT = Path(__file__).resolve().parents[1] / "metalesionlab" / "web" / "static" / "tour" / "scorer_demo.json"
KEEP = ("transcript", "scored_response", "code", "head", "lexical", "semantic", "phonological", "second",
        "second_status", "agree", "duration_s", "alternates")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--set", default="demo_en")
    args = ap.parse_args()

    manifest = httpx.get(f"{args.url}/api/sets/{args.set}").raise_for_status().json()["manifest"]
    index = {it["word"]: i for i, it in enumerate(manifest["items"])}
    items = []
    with tempfile.TemporaryDirectory() as tmp:
        for target, said in ANSWERS:
            aiff, wav = Path(tmp) / f"{said}.aiff", Path(tmp) / f"{said}.wav"
            subprocess.run(["say", "-v", VOICE, "-o", str(aiff), said], check=True)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav)], check=True)
            i = index[target]
            reply = httpx.post(f"{args.url}/api/score/naming", timeout=120, files={"audio": (wav.name, wav.read_bytes(), "audio/wav")},
                               data={"target": target, "lang": manifest["lang"], "set_id": args.set, "item": str(i)})
            reply.raise_for_status()
            body = reply.json()
            items.append({"item": i, "target": body["target"], "image": manifest["items"][i]["image"], "said": said,
                          **{k: body.get(k) for k in KEEP}})
            print(f"{target:10s} said {said!r:12s} heard {body['transcript']!r:14s} {body['code']:10s} "
                  f"second rater: {(body.get('second') or {}).get('code')}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "about": ("Recorded once with the real pipeline for the guided tour: answers synthesized with macOS say "
                  f"({VOICE}), sent to POST /api/score/naming (Muse Voice Transcribe, the naming-error classifier "
                  "and the Muse Spark second rater). The tour replays these replies and makes no API calls."),
        "recorded": time.strftime("%Y-%m-%d"), "set": args.set, "lang": manifest["lang"], "items": items,
    }, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
