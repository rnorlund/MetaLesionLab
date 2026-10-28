"""An AI growing up, exploratory check (added after the plan): a second, zero-shot reader of "is it a chair?".

The pre-registered recognizability asks which of 35 Quick, Draw! centroids a drawing sits nearest in DINOv2. Clean
SVG line art differs in style from people's 20-second doodles, and a slat-back chair seen from the front sits
nearest people's ladders. So, as a check, Google SigLIP 2 (So400m/14, 384 px, Apache-2.0; not one of the models
being tested) reads every drawing zero-shot: which of the 35 concept names fits it best ("a simple line drawing of
a chair", ...). It reads people's 200 reference chairs and Muse Image's 16 chairs too, for calibration.

Usage: python -I scripts/plato_scale_reader.py      (Mac; writes $PLATO_SCALE_DIR/reader_siglip.json)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab import plato_scale as ps  # noqa: E402
from metalesionlab.plato import CONCEPTS, PLATO_DIR, ink_crop, load_dir, render_strokes  # noqa: E402
from metalesionlab.plato_sketch import STEPS, sample_name  # noqa: E402

MODEL = "google/siglip2-so400m-patch14-384"
TEMPLATE = "a simple line drawing of {article} {label}"
LABELS = [c.label for c in CONCEPTS]


class Reader:
    def __init__(self):
        import torch
        from transformers import AutoModel, AutoProcessor

        self.torch = torch
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.proc = AutoProcessor.from_pretrained(MODEL)
        self.model = AutoModel.from_pretrained(MODEL).to(self.device).eval()
        texts = [TEMPLATE.format(article="an" if lb[0] in "aeiou" else "a", label=lb) for lb in LABELS]
        with torch.no_grad():
            t = self.proc(text=texts, padding="max_length", max_length=64, return_tensors="pt").to(self.device)
            v = self.model.get_text_features(**t)
            v = v if torch.is_tensor(v) else v.pooler_output
        self.text = torch.nn.functional.normalize(v.float(), dim=-1)

    def __call__(self, images: list, batch: int = 32) -> list[str]:
        torch, out = self.torch, []
        with torch.no_grad():
            for i in range(0, len(images), batch):
                x = self.proc(images=images[i:i + batch], return_tensors="pt").to(self.device)
                v = self.model.get_image_features(**x)
                v = v if torch.is_tensor(v) else v.pooler_output
                v = torch.nn.functional.normalize(v.float(), dim=-1)
                out += [LABELS[k] for k in (v @ self.text.T).argmax(1).tolist()]
        return out


def main():
    out_path = ps.SCALE_DIR / "reader_siglip.json"
    res = json.loads(out_path.read_text()) if out_path.exists() else {"model": MODEL, "template": TEMPLATE,
                                                                       "arm_b": {}, "arm_a": {}}
    rd = Reader()
    if "people" not in res:
        res["people"] = rd([ink_crop(Image.open(p).convert("RGB")) for p in load_dir(PLATO_DIR / "human" / "chair")])
        res["muse_image"] = rd([ink_crop(Image.open(p).convert("RGB")) for p in load_dir(PLATO_DIR / "ai" / "doodle" / "chair")])
        print(f"people {np.mean([x == 'chair' for x in res['people']]):.2f}, "
              f"Muse Image {np.mean([x == 'chair' for x in res['muse_image']]):.2f}", flush=True)
    svg = ps.SCALE_DIR / "svg"
    meas = json.loads((svg / "measure.json").read_text())
    for name, v in meas.items():
        if name in res["arm_b"]:
            continue
        ok = [s["i"] for s in v["samples"] if s["reason"] is None]
        imgs = [ink_crop(Image.open(svg / "png" / f"{name}_{i}.png").convert("RGB")) for i in ok]
        labels = rd(imgs) if imgs else []
        res["arm_b"][name] = dict(zip(map(str, ok), labels))
        print(name, f"{sum(x == 'chair' for x in labels)}/{len(v['samples'])} chair", flush=True)
        out_path.write_text(json.dumps(res, indent=1))
    sk = ps.SCALE_DIR / "sketch" / "runs"
    for size in ps.SIZES:
        for seed in ps.SEEDS_A:
            run = sk / ps.run_name_a(size, seed)
            if not (run / "meta.json").exists():
                continue
            meta = json.loads((run / "meta.json").read_text())
            if "seconds" not in meta:
                continue
            for ck, step in (("final", STEPS[-1]), ("best", ps.best_checkpoint(meta["heldout_loss"]))):
                key = f"{run.name}|{ck}"
                if key in res["arm_a"]:
                    continue
                drawings = json.loads((run / "samples" / f"{sample_name(step, ps.PRIMARY_TEMP_A)}.json").read_text())
                kept = [d for d in drawings if d]
                labels = rd([ink_crop(render_strokes(d)) for d in kept])
                res["arm_a"][key] = {"step": step, "n_all": len(drawings), "labels": labels}
                print(key, f"{sum(x == 'chair' for x in labels)}/{len(drawings)} chair", flush=True)
                out_path.write_text(json.dumps(res, indent=1))
    out_path.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
