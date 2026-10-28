"""Plato's Chair: the kinds Muse Spark named for each of the 35 things, for Ask Socrates' counterexamples.

Usage: python -I scripts/plato_named_kinds_export.py
Reads $PLATO_DIR/ai/doodle_listed/<thing>/kinds.json (Spark's list, as Muse Image drew it: one doodle per
kind; docs/plato.md, "Can you prompt it out of the Platonic chair?") and writes
- public_data/plato_named_kinds.json   the lists only: names of kinds, as Spark wrote them; no pictures
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato import CONCEPTS, PLATO_DIR  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    things = []
    for c in CONCEPTS:
        folder = PLATO_DIR / "ai" / "doodle_listed" / c.key
        kinds = json.loads((folder / "kinds.json").read_text())
        prompt = json.loads((folder / "kinds_prompt.json").read_text()) if (folder / "kinds_prompt.json").exists() else {}
        things.append({"key": c.key, "label": c.label, "kinds": kinds, "n": len(kinds),
                       **({"prompt": prompt["prompt"]} if prompt.get("prompt") else {})})
    out = {
        "about": "The kinds Meta's Muse Spark listed for each of the 35 things of Plato's Chair, as it wrote them. "
                 "Muse Image then drew one doodle of each kind (the 'named kinds' prompt; docs/plato.md, 'Can you "
                 "prompt it out of the Platonic chair?'). Ask Socrates uses them as counterexamples.",
        "model": "muse-spark-1.3, reasoning effort low",
        "made_by": "scripts/plato_named_kinds_export.py, from the Plato's Chair data folder",
        "link": "/plato#variety",
        "things": things,
    }
    path = REPO / "public_data" / "plato_named_kinds.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"{path}: {len(things)} things, {sum(len(t['kinds']) for t in things)} kinds")


if __name__ == "__main__":
    main()
