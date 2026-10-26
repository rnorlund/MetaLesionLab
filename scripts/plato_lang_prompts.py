"""Write the doodle prompt in six languages with one Muse Spark call.

Output: $PLATO_LANG_DIR/prompts.json. Costs well under $0.05.
Usage: python scripts/plato_lang_prompts.py [--force]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.meta_api import MetaAPI, spent  # noqa: E402
from metalesionlab.plato_lang import LANGS, OUT, translate_prompts  # noqa: E402


def main():
    path = OUT / "prompts.json"
    before = spent()
    if path.exists() and "--force" not in sys.argv:
        prompts = json.loads(path.read_text())
    else:
        prompts = translate_prompts(MetaAPI(), tuple(LANGS))
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prompts, ensure_ascii=False, indent=1))
    for lang, items in prompts.items():
        print(f"\n== {lang}")
        for concept, it in items.items():
            print(f"  {concept:9s} {it['word']}: {it['prompt']}")
    print(f"\nwrote {path}; this run cost about ${spent() - before:.4f} (shared ledger delta)")


if __name__ == "__main__":
    main()
