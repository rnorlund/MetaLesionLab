"""The portraits of Plato, Socrates and Aristotle (web/portraits.py): their Muse Image prompts, and how the chosen
candidates were cut into the WebPs in metalesionlab/web/static/img/portraits/.

    python scripts/portraits_make.py draw POSE [--n 4] [--out DIR]   # n candidates of one pose (paid: Muse Image)
    python scripts/portraits_make.py cut DIR                           # the chosen ones -> static/img/portraits/

Every prompt follows the template of the Socrates doodles the tour uses ("A quick simple doodle sketch of the
marble bust of the philosopher …, black marker on plain white, no text, no shading."), so all the portraits look
like one hand drew them. Four candidates per pose were drawn and one picked by eye, for its likeness to the
classical busts (Plato: full beard, broad brow; Aristotle: a shorter beard) and to Raphael's School of Athens
(Plato pointing up, Aristotle's palm to the earth). Calls go through meta_api, so they land in the cost ledger.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
OUT = REPO / "metalesionlab" / "web" / "static" / "img" / "portraits"
TAIL = "black marker on plain white, no text, no shading."
PLATO = "with a long full beard, wavy hair and a broad brow"
PROMPTS = {
    "socrates": f"A quick simple doodle sketch of the marble bust of the philosopher Socrates, bearded, {TAIL}",
    "plato": f"A quick simple doodle sketch of the marble bust of the philosopher Plato, {PLATO}, wearing a toga, {TAIL}",
    "plato-thinking": ("A quick simple doodle sketch of the philosopher Plato, head and shoulders like his marble bust, "
                       f"{PLATO}, wearing a toga, one hand raised to his beard, deep in thought, {TAIL}"),
    "plato-up": ("A quick simple doodle sketch of the philosopher Plato as in Raphael's School of Athens, an old man with "
                 "a long full beard, long wavy hair and a broad brow, wearing a toga, seen from the waist up, one arm "
                 f"raised high with the index finger pointing straight up to the sky, {TAIL}"),
    "aristotle": ("A quick simple doodle sketch of the marble bust of the philosopher Aristotle, with a short neat beard, "
                  f"short hair and a calm look, wearing a toga, {TAIL}"),
    "aristotle-earth": ("A quick simple doodle sketch of the philosopher Aristotle as in Raphael's School of Athens, a man "
                        "with a short neat beard and short curly hair, wearing a toga, seen from the waist up, one arm held "
                        f"out in front of him with the palm turned flat down toward the earth, {TAIL}"),
    "together": ("A quick simple doodle sketch of the philosophers Socrates and Plato in conversation, head and shoulders, "
                 "facing each other: Socrates old and bald with curly hair at the sides and a curly beard, Plato with a "
                 f"long full beard, wavy hair and a broad brow, both wearing togas, {TAIL}"),
}
# name: (chosen candidate, crop box in its pixels, width, mode, fades). "white": on white paper, for a round frame;
# "alpha": the paper made transparent, ink #111, fading out where the crop cuts the figure.
CUTS = {
    "plato-neutral": ("plato_3.png", (-130, 110, 1250, 1490), 256, "white", {}),
    "plato-thinking": ("plato-thinking_3.png", (230, 40, 1450, 1260), 256, "white", {}),
    "aristotle-neutral": ("aristotle_2.png", (230, 10, 1370, 1150), 256, "white", {}),
    "plato-pointing-up": ("plato-up_0.png", (40, 40, 1120, 1760), 720, "alpha", {"bottom": 0.16, "right": 0.05}),
    "plato-pointing-up-420": ("plato-up_0.png", (40, 40, 1120, 1760), 420, "alpha", {"bottom": 0.16, "right": 0.05}),
    "aristotle-earth": ("aristotle-earth_0.png", (40, 230, 1250, 1580), 600, "alpha", {"bottom": 0.08}),
    "socrates-and-plato": ("together_2.png", (0, 70, 1920, 1240), 900, "alpha", {"bottom": 0.1}),
}


def draw(pose: str, n: int, out: Path) -> None:
    from metalesionlab import meta_api
    out.mkdir(parents=True, exist_ok=True)
    for i, png in enumerate(meta_api.MetaAPI().generate_images(PROMPTS[pose], n=n)):
        (out / f"{pose}_{i}.png").write_bytes(png)
        print(out / f"{pose}_{i}.png")


def cut(src: Path) -> None:
    for name, (f, box, width, mode, fades) in CUTS.items():
        im = Image.open(src / f).convert("L")
        paper = Image.new("L", (im.width + 800, im.height + 800), 255)  # a crop past the edge stays white paper
        paper.paste(im, (400, 400))
        im = paper.crop(tuple(v + 400 for v in box))
        a = np.clip((np.asarray(im, dtype=float) - 60) / (215 - 60), 0, 1) * 255  # paper to white, ink to black
        im = Image.fromarray(a.astype("uint8"))
        im = im.resize((width, round(width * im.height / im.width)), Image.LANCZOS)
        if mode == "alpha":
            alpha = 255 - np.asarray(im, dtype=float)
            for side, frac in fades.items():
                k = max(1, round(frac * (alpha.shape[0] if side == "bottom" else alpha.shape[1])))
                ramp = np.linspace(1, 0, k) ** 1.5
                if side == "bottom":
                    alpha[-k:, :] *= ramp[:, None]
                else:
                    alpha[:, -k:] *= ramp[None, :]
            rgba = np.zeros(alpha.shape + (4,), dtype="uint8")
            rgba[..., :3] = 17
            rgba[..., 3] = alpha.astype("uint8")
            im = Image.fromarray(rgba, "RGBA")
        im.save(OUT / f"{name}.webp", "WEBP", quality=82, method=6)
        print(OUT / f"{name}.webp", im.size)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("pose", choices=sorted(PROMPTS))
    d.add_argument("--n", type=int, default=4)
    d.add_argument("--out", type=Path, default=REPO / "runs" / "portraits")
    c = sub.add_parser("cut")
    c.add_argument("src", type=Path)
    args = ap.parse_args()
    draw(args.pose, args.n, args.out) if args.cmd == "draw" else cut(args.src)
