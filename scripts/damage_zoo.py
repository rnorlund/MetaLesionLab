"""The damage zoo: how pictures fall apart when other image models are damaged (for fun; not pre-registered).

Added Nov 3 at Roger's request: the chair, God and a few other things drawn by open image models while a growing share
of neurons is switched off, in the language part (the text encoders) or the drawing part (the denoiser), to show the
variety of ways a damaged image model degrades. GPU part runs on a lab GPU; `sheets` runs anywhere.

  probe  --model M                 unit counts per part, one intact picture, timing
  run    --model M --out DIR       the coarse pass: every thing x part x dose (0 to 90% in steps of 10) x seed
  run    --model M --out DIR --fine  the fine pass: 11 steps from intact to the part's end of meaningful damage
  sheets --out DIR [--fine]        contact sheets: one per model and thing, and one "zoo" sheet per thing
  web    --out DIR                 the /plato/zoo page's picture strips and data file, for models with a fine pass

Two passes. The coarse pass shows where each model's pictures stop meaning anything (noise, texture, a blank). That
end was chosen by eye from the coarse sheets, per model and part (MODELS[m]["ends"]; Roger, Nov 3: "I wouldn't show
anything after 40% as it is meaningless" for SDXL), and the fine pass spends its 11 steps inside it.

Same method as Stable Diffusion XL's damage (metalesionlab/sdxl_lesions.py), generalised: a unit is a neuron after the
activation of a feed-forward net, i.e. one input channel of its down-projection (CLIP mlp.fc2, T5 DenseReluDense.wo,
Gemma and GLM mlp.down_proj, ChatGLM mlp.dense_4h_to_h, BERT's FFN output.dense, a diffusers FeedForward's last Linear,
Lumina's linear_2, Sana's GLUMBConv conv_point), or one output channel of FLUX's single-block proj_mlp (zero before
GELU is zero after it). A lesion zeroes `dose` of every such layer's units, chosen at random with a fixed seed per
part, nested across doses (more damage keeps every unit a smaller dose hit). Weights are never edited. Picture i of a
thing has the same seed at every dose, so a row shows one picture degrading.

Pictures: <out>/<model>/<part>@<dose>/<thing>/s<i>.png (512 px), <out>/<model>/meta.json (and fine.json).
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato import STYLES  # noqa: E402

MODELS = {
    "sd15": {"repo": "stable-diffusion-v1-5/stable-diffusion-v1-5", "pipe": "StableDiffusionPipeline", "steps": 25,
             "guidance": 7.5, "size": 512, "dtype": "float16", "license": "CreativeML OpenRAIL-M",
             "ends": {"language": 0.5, "drawing": 0.5}},
    "sdxl": {"repo": "stabilityai/stable-diffusion-xl-base-1.0", "pipe": "StableDiffusionXLPipeline", "steps": 25,
             "guidance": 5.0, "size": 768, "dtype": "float16", "license": "CreativeML OpenRAIL++-M",
             "ends": {"language": 0.4, "drawing": 0.4}},
    "pixart": {"repo": "PixArt-alpha/PixArt-Sigma-XL-2-1024-MS", "pipe": "PixArtSigmaPipeline", "steps": 20,
               "guidance": 4.5, "size": 1024, "dtype": "float16", "license": "CreativeML OpenRAIL++-M",
               "ends": {"language": 0.8, "drawing": 0.4}},
    "sana": {"repo": "Efficient-Large-Model/Sana_1600M_1024px_BF16_diffusers", "pipe": "SanaPipeline", "steps": 20,
             "guidance": 4.5, "size": 1024, "dtype": "bfloat16", "license": "Apache-2.0",
             "ends": {"language": 0.9, "drawing": 0.9}},
    "kolors": {"repo": "Kwai-Kolors/Kolors-diffusers", "pipe": "KolorsPipeline", "steps": 25, "guidance": 5.0,
               "size": 1024, "dtype": "float16", "license": "Apache-2.0", "load": {"variant": "fp16"}},
    "hunyuan": {"repo": "Tencent-Hunyuan/HunyuanDiT-v1.2-Diffusers", "pipe": "HunyuanDiTPipeline", "steps": 25,
                "guidance": 5.0, "size": 1024, "dtype": "float16", "license": "Tencent Hunyuan Community"},
    "lumina": {"repo": "Alpha-VLLM/Lumina-Next-SFT-diffusers", "pipe": "LuminaPipeline", "steps": 30, "guidance": 4.0,
               "size": 1024, "dtype": "bfloat16", "license": "Apache-2.0"},
    "cogview4": {"repo": "THUDM/CogView4-6B", "pipe": "CogView4Pipeline", "steps": 25, "guidance": 3.5, "size": 1024,
                 "dtype": "bfloat16", "license": "Apache-2.0"},
    "playground": {"repo": "playgroundai/playground-v2.5-1024px-aesthetic", "pipe": "StableDiffusionXLPipeline",
                   "steps": 25, "guidance": 3.0, "size": 1024, "dtype": "float16",
                   "license": "Playground v2.5 Community", "load": {"variant": "fp16"}},
    "flux": {"repo": "black-forest-labs/FLUX.1-schnell", "pipe": "FluxPipeline", "steps": 4, "guidance": 0.0,
             "size": 768, "dtype": "bfloat16", "license": "Apache-2.0 (gated: accept the terms first)",
             "extra": {"max_sequence_length": 256}},
}
THINGS = {"chair": "a chair", "god": "God", "clock": "a clock", "bird": "a bird", "house": "a house", "love": "love"}
PARTS = {"language": 11, "drawing": 12}  # part -> seed of its unit choice
DOSES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
FINE_STEPS = 10  # 11 pictures: intact, then 10 equal steps to the part's end
N_SEEDS = 2
SAVE_SIDE = 512
TEXT_ENCODERS = ("text_encoder", "text_encoder_2", "text_encoder_3")
TEXT_DOWN = ("mlp.fc2", "DenseReluDense.wo", "mlp.down_proj", "mlp.dense_4h_to_h")


def prompt(thing: str) -> str:
    return STYLES["doodle"].format(phrase=THINGS[thing])


def seed_for(thing: str, i: int) -> int:
    return 20261103 + 1000 * list(THINGS).index(thing) + i


def fine_doses(model: str, part: str) -> list[float]:
    end = MODELS[model]["ends"][part]
    return [round(end * k / FINE_STEPS, 4) for k in range(FINE_STEPS + 1)]


def doses_for(model: str, part: str, fine: bool) -> list[float]:
    return fine_doses(model, part) if fine else DOSES


def load(name: str):
    import diffusers
    import torch

    m = MODELS[name]
    pipe = getattr(diffusers, m["pipe"]).from_pretrained(m["repo"], torch_dtype=getattr(torch, m["dtype"]),
                                                          **m.get("load", {}))
    if hasattr(pipe, "safety_checker"):
        pipe.safety_checker = None
    pipe.set_progress_bar_config(disable=True)
    return pipe.to("cuda")


def _text_down(name: str) -> bool:
    """A text encoder's feed-forward down-projection (BERT's is output.dense; its attention.output.dense is not)."""
    return name.endswith(TEXT_DOWN) or (name.endswith("output.dense") and "attention" not in name)


def part_layers(pipe, part: str) -> list[tuple[str, object, str]]:
    """(name, module, where) for every unit-carrying layer of a part, in depth order. where: "in" (the Linear's input,
    last dim), "in_ch" (a Conv2d's input channels, dim 1) or "out" (the Linear's output, last dim)."""
    import torch.nn as nn

    out = []
    if part == "language":
        for attr in TEXT_ENCODERS:
            enc = getattr(pipe, attr, None)
            if enc is None:
                continue
            for name, mod in enc.named_modules():
                if isinstance(mod, nn.Linear) and _text_down(name):
                    out.append((f"{attr}.{name}", mod, "in"))
    else:
        den = getattr(pipe, "unet", None) or pipe.transformer
        for name, mod in den.named_modules():
            kind = type(mod).__name__
            if kind == "FeedForward" and hasattr(mod, "net"):
                out.append((f"draw.{name}", [m for m in mod.net if isinstance(m, nn.Linear)][-1], "in"))
            elif kind == "LuminaFeedForward":
                out.append((f"draw.{name}.linear_2", mod.linear_2, "in"))
            elif kind == "FluxSingleTransformerBlock":
                out.append((f"draw.{name}.proj_mlp", mod.proj_mlp, "out"))
            elif kind == "GLUMBConv":
                out.append((f"draw.{name}.conv_point", mod.conv_point, "in_ch"))
    return out


def width(mod, where: str) -> int:
    return {"in": lambda: mod.in_features, "out": lambda: mod.out_features, "in_ch": lambda: mod.in_channels}[where]()


class Lesion:
    """`with Lesion(pipe, part, dose):` zeroes `dose` of every layer's units in the part, then undoes it."""

    def __init__(self, pipe, part: str, dose: float):
        self.pipe, self.part, self.dose, self.hooks = pipe, part, dose, []

    def __enter__(self):
        import torch

        from metalesionlab.sdxl_lesions import random_units

        if self.dose <= 0:
            return self
        layers = part_layers(self.pipe, self.part)
        chosen = random_units([width(m, w) for _, m, w in layers], self.dose, PARTS[self.part])
        for (_, mod, where), idx in zip(layers, chosen):
            dev = next(mod.parameters()).device
            keep = torch.ones(width(mod, where), device=dev)
            keep[torch.as_tensor(idx, device=dev, dtype=torch.long)] = 0
            if where == "out":
                self.hooks.append(mod.register_forward_hook(lambda _m, _a, y, k=keep: y * k.to(y.dtype)))
            else:
                k = keep.view(1, -1, 1, 1) if where == "in_ch" else keep
                self.hooks.append(mod.register_forward_pre_hook(
                    lambda _m, args, k=k: (args[0] * k.to(args[0].dtype),) + tuple(args[1:])))
        return self

    def __exit__(self, *exc):
        for h in self.hooks:
            h.remove()
        self.hooks.clear()


def draw(pipe, name: str, thing: str, i: int):
    import torch

    m = MODELS[name]
    gen = torch.Generator("cuda").manual_seed(seed_for(thing, i))
    img = pipe(prompt(thing), num_inference_steps=m["steps"], guidance_scale=m["guidance"], height=m["size"],
               width=m["size"], generator=gen, **m.get("extra", {})).images[0]
    img.thumbnail((SAVE_SIDE, SAVE_SIDE))
    return img


def cmd_probe(args):
    t0 = time.time()
    pipe = load(args.model)
    print(f"{args.model}: loaded in {time.time() - t0:.0f} s")
    for part in PARTS:
        layers = part_layers(pipe, part)
        kinds = sorted({n.rsplit(".", 1)[-1] for n, _, _ in layers})
        print(f"  {part} part: {len(layers)} layers, {sum(width(m, w) for _, m, w in layers):,} units ({', '.join(kinds)})")
    t0 = time.time()
    draw(pipe, args.model, "chair", 0).save(f"probe_{args.model}.png")
    with Lesion(pipe, "drawing", 0.5):
        draw(pipe, args.model, "chair", 0).save(f"probe_{args.model}_drawing50.png")
    print(f"  two pictures in {time.time() - t0:.1f} s: probe_{args.model}.png, probe_{args.model}_drawing50.png")


def cmd_run(args):
    m = MODELS[args.model]
    if args.fine and "ends" not in m:
        raise SystemExit(f"{args.model}: no fine range yet; run the coarse pass and choose its ends first")
    pipe = load(args.model)
    root = Path(args.out) / args.model
    root.mkdir(parents=True, exist_ok=True)
    empty = [p for p in PARTS if not part_layers(pipe, p)]
    if empty:  # an architecture this script doesn't know: refuse rather than draw 240 intact pictures
        raise SystemExit(f"{args.model}: no units found in the {' and '.join(empty)} part")
    meta = {**m, "model": args.model, "things": THINGS, "prompt": STYLES["doodle"], "doses": DOSES, "n_seeds": N_SEEDS,
            "parts": {p: {"layers": len(part_layers(pipe, p)),
                          "units": sum(width(mod, w) for _, mod, w in part_layers(pipe, p)), "seed": s}
                      for p, s in PARTS.items()}}
    (root / "meta.json").write_text(json.dumps(meta, indent=1))
    if args.fine:
        (root / "fine.json").write_text(json.dumps({p: fine_doses(args.model, p) for p in PARTS}, indent=1))
    t0, made = time.time(), 0
    for part in PARTS:
        for dose in doses_for(args.model, part, args.fine):
            with Lesion(pipe, part, dose):
                for thing in THINGS:
                    folder = root / f"{part}@{dose:g}" / thing
                    folder.mkdir(parents=True, exist_ok=True)
                    for i in range(N_SEEDS):
                        path = folder / f"s{i}.png"
                        if path.exists():
                            continue
                        draw(pipe, args.model, thing, i).save(path)
                        made += 1
            print(f"{args.model} {part}@{dose:g}: {made} pictures, {time.time() - t0:.0f} s", flush=True)
    print("done", flush=True)


def _font(size: int):
    from PIL import ImageFont

    for f in ("/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def grid(rows: list[tuple[str, list[tuple[Path, float]]]], title: str, cell: int = 160):
    """Rows of (picture, dose), each picture captioned with its dose; a missing picture is left blank."""
    from PIL import Image, ImageDraw

    left, top, cap = 230, 50, 24
    cols = max(len(r[1]) for r in rows)
    sheet = Image.new("RGB", (left + cell * cols, top + (cell + cap) * len(rows)), "white")
    d = ImageDraw.Draw(sheet)
    d.text((10, 8), title, fill="black", font=_font(26))
    for r, (label, cells) in enumerate(rows):
        y = top + r * (cell + cap)
        d.text((10, y + cell // 2 - 12), label, fill="black", font=_font(18))
        for j, (p, dose) in enumerate(cells):
            d.text((left + j * cell + 6, y + cell), "intact" if dose == 0 else f"{dose:.0%} off", fill="#555",
                   font=_font(16))
            if p.exists():
                sheet.paste(Image.open(p).convert("RGB").resize((cell - 4, cell - 4)), (left + j * cell + 2, y + 2))
    return sheet


def cmd_sheets(args):
    root = Path(args.out)
    done = "fine.json" if args.fine else "meta.json"
    models = [m for m in MODELS if (root / m / done).exists()]
    sheets = root / ("sheets_fine" if args.fine else "sheets")
    sheets.mkdir(exist_ok=True)

    def cells(model, part, thing, i):
        return [(root / model / f"{part}@{dose:g}" / thing / f"s{i}.png", dose)
                for dose in doses_for(model, part, args.fine)]

    for thing in THINGS:
        for model in models:
            rows = [(f"{part} part, seed {i + 1}", cells(model, part, thing, i)) for part in PARTS for i in range(N_SEEDS)]
            grid(rows, f"{model}: {THINGS[thing]}, damaged").save(sheets / f"{model}_{thing}.png")
        rows = [(f"{model}, {part}", cells(model, part, thing, 0)) for model in models for part in PARTS]
        grid(rows, f"The damage zoo: {THINGS[thing]}").save(sheets / f"zoo_{thing}.png")
    print(f"{len(models)} models: {', '.join(models)}; sheets in {sheets}")


# ---------- the web page (/plato/zoo): one strip of 11 pictures per model, part and thing, and a small data file ----------

REPO = Path(__file__).resolve().parents[1]
WEB_DATA = REPO / "metalesionlab" / "web" / "data" / "damage_zoo.json"
SPRITES = REPO / "metalesionlab" / "web" / "static" / "img" / "zoo"
FRAME = 200  # px per picture in a strip
# Who made each model and what reads the words (its language part), for the page's cards.
ABOUT = {
    "sd15": ("Stable Diffusion 1.5", "Stability AI and Runway, 2022", "OpenAI's CLIP"),
    "sdxl": ("Stable Diffusion XL", "Stability AI, 2023", "two CLIP readers"),
    "pixart": ("PixArt-Σ", "PixArt team, 2024", "Google's T5"),
    "sana": ("Sana", "NVIDIA, 2024", "Google's Gemma 2"),
    "kolors": ("Kolors", "Kuaishou, 2024", "ChatGLM3, a chat AI"),
    "hunyuan": ("Hunyuan-DiT", "Tencent, 2024", "a bilingual CLIP and mT5"),
    "lumina": ("Lumina-Next", "Shanghai AI Lab, 2024", "Google's Gemma"),
    "cogview4": ("CogView4", "Zhipu AI, 2025", "GLM-4, a chat AI"),
    "playground": ("Playground v2.5", "Playground, 2024", "two CLIP readers"),
    "flux": ("FLUX.1 schnell", "Black Forest Labs, 2024", "CLIP and Google's T5"),
}
# How each model's pictures fail, in a few words, from the fine sheets by eye (model, part) -> text.
CAPTIONS: dict[tuple[str, str], str] = {
    ("sd15", "language"): "Forgets the request: sketches of strangers, then a murky photo.",
    ("sd15", "drawing"): "Lines thicken into stripes, then into texture.",
    ("sdxl", "language"): "Loses the request: God becomes an ordinary man; a bird, a page of birds.",
    ("sdxl", "drawing"): "Shatters into bold black-and-white patterns.",
    ("pixart", "language"): "Holds on longest, then draws strangers in bright colour.",
    ("pixart", "drawing"): "Melts into a dark blur, then grey static.",
    ("sana", "language"): "Forgets the words and draws stock photos: smiling people, posters, skylines.",
    ("sana", "drawing"): "Falls apart stroke by stroke, like a drawing being rubbed out.",
}


HUB = REPO / "metalesionlab" / "web" / "static" / "img" / "plato" / "hub" / "damaged-zoo.webp"
# The Damaged AI hub's card: four AIs' chairs, intact on top and damaged below (never God: /draw's "Draw God" stays
# blind). (model, part, fine step) per column.
HUB_PICKS = [("sana", "drawing", 7), ("sdxl", "language", 7), ("pixart", "language", 9), ("sd15", "drawing", 4)]


def hub_card(root: Path, models: list[str]) -> None:
    from PIL import Image

    picks = [p for p in HUB_PICKS if p[0] in models]
    side, gap = 216, 16
    card = Image.new("RGB", (960, 540), (251, 250, 247))
    x0 = (960 - len(picks) * side - (len(picks) - 1) * gap) // 2
    for j, (model, part, k) in enumerate(picks):
        for row, step in enumerate((0, k)):
            dose = fine_doses(model, part)[step]
            pic = Image.open(root / model / f"{part}@{dose:g}" / "chair" / "s0.png").convert("RGB")
            card.paste(pic.resize((side, side), Image.LANCZOS), (x0 + j * (side + gap), 46 + row * (side + gap)))
    card.save(HUB, "WEBP", quality=82, method=6)


def cmd_web(args):
    """Strips (seed 1 of each thing) and web/data/damage_zoo.json for every model with a fine pass."""
    from PIL import Image

    root = Path(args.out)
    models = [m for m in MODELS if (root / m / "fine.json").exists()]
    SPRITES.mkdir(parents=True, exist_ok=True)
    for model in models:
        for part in PARTS:
            for thing in THINGS:
                strip = Image.new("RGB", (FRAME * (FINE_STEPS + 1), FRAME), "white")
                for k, dose in enumerate(fine_doses(model, part)):
                    p = root / model / f"{part}@{dose:g}" / thing / "s0.png"
                    strip.paste(Image.open(p).convert("RGB").resize((FRAME, FRAME), Image.LANCZOS), (k * FRAME, 0))
                strip.save(SPRITES / f"{model}-{part}-{thing}.webp", "WEBP", quality=78, method=6)
    data = {
        "about": "The damage zoo (/plato/zoo): open image models drawing with a growing share of their neurons switched "
                 "off, in the language part or the drawing part. Written by scripts/damage_zoo.py web.",
        "prompt": STYLES["doodle"], "things": THINGS, "parts": list(PARTS), "steps": FINE_STEPS + 1, "frame": FRAME,
        "models": [{"key": m, "name": ABOUT[m][0], "maker": ABOUT[m][1], "reads_with": ABOUT[m][2],
                    "license": MODELS[m]["license"], "repo": MODELS[m]["repo"],
                    "doses": {p: fine_doses(m, p) for p in PARTS},
                    "captions": {p: CAPTIONS.get((m, p), "") for p in PARTS}} for m in models],
    }
    WEB_DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    hub_card(root, models)
    size = sum(f.stat().st_size for f in SPRITES.glob("*.webp")) / 1e6
    print(f"{len(models)} models: {', '.join(models)}; {len(list(SPRITES.glob('*.webp')))} strips, {size:.1f} MB")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("probe", cmd_probe), ("run", cmd_run), ("sheets", cmd_sheets), ("web", cmd_web)):
        p = sub.add_parser(name)
        if name in ("probe", "run"):
            p.add_argument("--model", required=True, choices=list(MODELS))
        if name != "probe":
            p.add_argument("--out", required=True)
        if name in ("run", "sheets"):
            p.add_argument("--fine", action="store_true", help="the fine pass, inside each part's meaningful range")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
