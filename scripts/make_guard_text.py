"""Write the general-language guard text for "What can I cut?" with Muse Spark, once.

150 short, plain sentences (100 English, 50 Spanish) across everyday topics, saved to
public_data/general_text_guard.json. compress.py measures next-token perplexity on them so a cut
that keeps picture naming but breaks ordinary language is caught. The text is model-written, so
it carries no third-party rights and no data from people.

Usage: python scripts/make_guard_text.py [--force]
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

from metalesionlab.meta_api import CHAT_MODEL, REPO_ROOT, MetaAPI

OUT = REPO_ROOT / "public_data" / "general_text_guard.json"
TOPICS = ["daily routines", "weather and seasons", "food and cooking", "travel and transport", "work and school",
          "nature and animals", "health and the body", "home and family", "shopping and money",
          "science and how things work"]
PER_TOPIC = {"en": 10, "es": 5}
LANGS = {"en": "English", "es": "Spanish"}
PROMPT = ("Write {n} short, plain sentences in {language} about {topic}. Rules: each sentence has 6 to 18 words; "
          "use everyday vocabulary; vary the structure (statements, at least one question, one with a number); "
          "no names of real people, brands or specific places; no quotations. Output one sentence per line, "
          "with no numbering and nothing else.")


def parse_lines(text: str) -> list[str]:
    lines = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines if len(ln.split()) >= 4]


def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        sys.exit(f"{OUT} exists; pass --force to rewrite it")
    api = MetaAPI()
    sentences = []
    for lang, n in PER_TOPIC.items():
        for topic in TOPICS:
            prompt = PROMPT.format(n=n, language=LANGS[lang], topic=topic)
            reply = api.chat([{"role": "user", "content": prompt}]).choices[0].message.content
            got = parse_lines(reply)[:n]
            print(f"{lang} {topic}: {len(got)}")
            sentences += [{"lang": lang, "topic": topic, "text": s} for s in got]
    OUT.write_text(json.dumps({
        "description": "General-language guard text for compress.py: next-token perplexity on plain sentences.",
        "generated_by": f"Muse Spark ({CHAT_MODEL}) via the Meta Model API, {date.today().isoformat()}",
        "prompt": PROMPT,
        "license": "Model-generated for this project; Apache 2.0 with the repository",
        "n": len(sentences),
        "sentences": sentences,
    }, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {len(sentences)} sentences to {OUT}")


if __name__ == "__main__":
    main()
