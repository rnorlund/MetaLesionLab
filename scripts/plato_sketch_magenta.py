"""A ceiling reference for the sketch models: Magenta's own pretrained Sketch-RNN chair (Apache-2.0).

Magenta publishes unconditional Sketch-RNN decoders ("gen" models) for about 100 Quick, Draw! classes, chair
among them, as JSON for sketch-rnn-js: models/chair.gen.json (LSTM 512) and large_models/chair.gen.json
(LSTM 1024), at https://storage.googleapis.com/quickdraw-models/sketchRNN/. This script decodes them exactly as
sketch_rnn.js does (int16 weights / 32767 * 10; a plain LSTM with gates i, g, f, o and forget bias 1; a zero first
input) and draws 200 chairs per temperature with our fixed noise and inverse-CDF sampling (plato_sketch), so it
can be measured like our own models. It has no training trajectory, so it can't be the animation; it shows how
good a published Sketch-RNN chair gets.

Usage: python -I scripts/plato_sketch_magenta.py [--out DIR]   (default $PLATO_LIFESPAN_DIR/sketch/magenta)
Writes <size>/samples/t<T>.json and model.json (the downloaded weights stay outside the repository).
Model: Ha & Eck (2017); Magenta (Google), Apache-2.0. Trained on Quick, Draw! (Google Creative Lab, CC BY 4.0).
"""
import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

from metalesionlab.plato_lifespan import LIFESPAN_DIR  # noqa: E402
from metalesionlab.plato_sketch import BIG, N_SAMPLES, categorical_from_uniform, make_noise, offset_from_noise  # noqa: E402

URL = "https://storage.googleapis.com/quickdraw-models/sketchRNN/{kind}/chair.gen.json"
KINDS = {"magenta512": "models", "magenta1024": "large_models"}
SEED = 1


def decode_weights(raw: list) -> tuple[dict, list[np.ndarray]]:
    """sketch_rnn.js load_model: each blob is base64 int16, divided by 32767 and multiplied by 10."""
    info, dims, blobs = raw
    ws = []
    for d, b in zip(dims, blobs):
        a = np.frombuffer(base64.b64decode(b), dtype="<i2").astype(np.float64) / 32767 * 10.0
        ws.append(a.reshape(d) if len(d) == 2 else a)
    return info, ws


class MagentaGen:
    """The 'gen' decoder: weights[0..4] = output W, output b, LSTM W_xh, W_hh, bias."""

    def __init__(self, raw: list):
        self.info, w = decode_weights(raw)
        assert self.info.get("mode") in (2, "gen"), "not a gen (decoder-only) model"
        self.wo, self.bo, wxh, whh, self.b = w[:5]
        self.W = np.concatenate([wxh, whh], 0)  # [input + H, 4H], as Wfull in sketch_rnn.js
        self.H = whh.shape[0]
        self.max_len = int(self.info["max_seq_len"])

    def step(self, x, h, c):
        z = np.concatenate([x, h], 1) @ self.W + self.b
        H = self.H
        i, g, f, o = (z[:, k * H:(k + 1) * H] for k in range(4))
        sig = lambda v: 0.5 * (1 + np.tanh(0.5 * v))  # noqa: E731  (the logistic, without overflow)
        c = c * sig(f + 1.0) + sig(i) * np.tanh(g)
        h = np.tanh(c) * sig(o)
        return h, c

    def params(self, h):
        """[pen logits 3 | pi 20 | mu1 | mu2 | log sigma1 | log sigma2 | corr], as sketch_rnn.js get_pdf."""
        z = h @ self.wo + self.bo
        pen, rest = z[:, :3], z[:, 3:]
        pi, mx, my, sx, sy, r = np.split(rest, 6, axis=1)
        return pi, mx, my, np.exp(sx), np.exp(sy), np.tanh(r), pen

    def sample(self, noise: dict, temp: float) -> list:
        """Drawings from fixed noise, with our temperature convention (logits / T, variances x T), so they compare
        with our models' samples. Offsets are in the model's normalized units; to_quickdraw rescales anyway."""
        from plato_lifespan_sketch import from_stroke5

        n = noise["e1"].shape[0]
        T = min(self.max_len, noise["e1"].shape[1])
        h = np.zeros((n, self.H))
        c = np.zeros((n, self.H))
        x = np.zeros((n, 5))  # sketch_rnn.js: the first input of a gen model is all zeros
        out = np.zeros((n, T, 5))
        done = np.zeros(n, bool)
        for t in range(T):
            h, c = self.step(x, h, c)
            pi, mx, my, sx, sy, r, pen = self.params(h)
            k = categorical_from_uniform(pi, noise["u_mix"][:, t], temp)[:, None]
            g = lambda a: np.take_along_axis(a, k, 1)[:, 0]  # noqa: E731
            dx, dy = offset_from_noise(g(mx), g(my), g(sx), g(sy), g(r), noise["e1"][:, t], noise["e2"][:, t], temp)
            p = categorical_from_uniform(pen, noise["u_pen"][:, t], temp)
            x = np.zeros((n, 5))
            x[:, 0], x[:, 1] = dx, dy
            x[np.arange(n), 2 + p] = 1
            out[:, t] = x
            done |= p == 2
            if done.all():
                break
        drawings = []
        for s5 in out:
            d = from_stroke5(s5)
            drawings.append(d if d else None)
        return drawings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=LIFESPAN_DIR / "sketch" / "magenta")
    args = ap.parse_args()
    for name, kind in KINDS.items():
        d = args.out / name
        (d / "samples").mkdir(parents=True, exist_ok=True)
        f = d / "model.json"
        if not f.exists():
            f.write_bytes(urllib.request.urlopen(URL.format(kind=kind), timeout=120).read())
        m = MagentaGen(json.loads(f.read_text()))
        print(f"{name}: LSTM {m.H}, max length {m.max_len}, info {m.info}", flush=True)
        noise = make_noise(SEED, N_SAMPLES, max(m.max_len, 250))
        for temp in BIG["temps"]:
            dr = m.sample(noise, temp)
            (d / "samples" / f"t{temp:.1f}.json").write_text(json.dumps(dr))
            print(f"  T={temp}: {sum(1 for v in dr if v)} drawings", flush=True)


if __name__ == "__main__":
    main()
