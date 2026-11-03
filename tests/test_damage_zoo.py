"""The damage zoo (scripts/damage_zoo.py): finding each image model's feed-forward neurons in its language and drawing
parts, zeroing a nested share of them reversibly, and laying the pictures out in sheets. Small stand-in modules with
the real models' layer names; no diffusers or GPU needed."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
nn = torch.nn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import damage_zoo as Z  # noqa: E402


class FeedForward(nn.Module):  # diffusers' FeedForward: the unit is the input of its last Linear
    def __init__(self):
        super().__init__()
        self.net = nn.ModuleList([nn.Linear(4, 8), nn.GELU(), nn.Linear(8, 4)])


class FluxSingleTransformerBlock(nn.Module):
    def __init__(self):
        super().__init__()
        self.proj_mlp = nn.Linear(4, 6)


class GLUMBConv(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv_point = nn.Conv2d(6, 4, 1)


class LuminaFeedForward(nn.Module):  # SwiGLU: linear_2(silu(linear_1(x)) * linear_3(x))
    def __init__(self):
        super().__init__()
        self.linear_1, self.linear_2, self.linear_3 = nn.Linear(4, 5), nn.Linear(5, 4), nn.Linear(4, 5)


def _nest(path: str, leaf: nn.Module) -> nn.Module:
    """A module tree in which `leaf` sits at `path` (dotted, digits become ModuleLists)."""
    root = node = nn.Module()
    parts = path.split(".")
    for i, p in enumerate(parts):
        child = leaf if i == len(parts) - 1 else (nn.ModuleList() if parts[i + 1].isdigit() else nn.Module())
        if isinstance(node, nn.ModuleList):
            node.append(child)
        else:
            setattr(node, p, child)
        node = child
    return root


def fake_pipe():
    den = nn.Module()
    den.blocks = nn.ModuleList([FeedForward(), FluxSingleTransformerBlock(), GLUMBConv(), LuminaFeedForward()])
    return SimpleNamespace(text_encoder=_nest("layers.0.mlp.fc2", nn.Linear(8, 4)),
                           text_encoder_2=_nest("encoder.block.0.DenseReluDense.wo", nn.Linear(10, 4)),
                           transformer=den)


def zeros_reaching(mod, where, run):
    """How many units arrive at the module as zero while `run()` executes."""
    seen = {}
    if where == "out":
        h = mod.register_forward_hook(lambda _m, _a, y: seen.setdefault("x", y.detach()))
    else:
        h = mod.register_forward_pre_hook(lambda _m, a: seen.setdefault("x", a[0].detach()))
    run()
    h.remove()
    x = seen["x"]
    return int((x[0, :, 0, 0] == 0).sum()) if where == "in_ch" else int((x[0] == 0).sum())


def call(mod, where):
    """Run the module on ones (a random Linear's outputs are never exactly 0 unless a lesion made them so)."""
    if where == "in_ch":
        return lambda: mod(torch.ones(1, mod.in_channels, 2, 2))
    return lambda: mod(torch.ones(1, mod.in_features))


def test_each_part_finds_the_feed_forward_neurons_of_every_architecture():
    pipe = fake_pipe()
    lang = [(n, Z.width(m, w), w) for n, m, w in Z.part_layers(pipe, "language")]
    assert lang == [("text_encoder.layers.0.mlp.fc2", 8, "in"), ("text_encoder_2.encoder.block.0.DenseReluDense.wo", 10, "in")]
    draw = [(n, Z.width(m, w), w) for n, m, w in Z.part_layers(pipe, "drawing")]
    assert draw == [("draw.blocks.0", 8, "in"), ("draw.blocks.1.proj_mlp", 6, "out"), ("draw.blocks.2.conv_point", 6, "in_ch"),
                    ("draw.blocks.3.linear_2", 5, "in")]


def test_text_encoders_of_every_family_but_not_attention_outputs():
    ok = ["layers.3.mlp.fc2", "block.0.layer.1.DenseReluDense.wo", "layers.0.mlp.down_proj",
          "encoder.layers.2.mlp.dense_4h_to_h", "encoder.layer.5.output.dense"]
    assert all(Z._text_down(n) for n in ok)
    assert not any(Z._text_down(n) for n in ["encoder.layer.5.attention.output.dense", "layers.0.mlp.up_proj"])


def test_the_fine_pass_spends_eleven_pictures_inside_each_parts_meaningful_range():
    assert Z.fine_doses("sdxl", "language") == [0.0, 0.04, 0.08, 0.12, 0.16, 0.2, 0.24, 0.28, 0.32, 0.36, 0.4]
    assert Z.fine_doses("pixart", "language")[-1] == 0.8 and Z.fine_doses("pixart", "drawing")[-1] == 0.4
    assert Z.doses_for("sdxl", "drawing", False) == Z.DOSES
    with pytest.raises(SystemExit):
        Z.cmd_run(SimpleNamespace(model="flux", out="unused", fine=True))  # no range chosen


@pytest.mark.parametrize("part", ["language", "drawing"])
def test_a_dose_zeroes_that_share_of_every_layer_and_is_undone_after(part):
    pipe = fake_pipe()
    layers = Z.part_layers(pipe, part)
    with Z.Lesion(pipe, part, 0.5):
        hit = [zeros_reaching(m, w, call(m, w)) for _, m, w in layers]
    assert hit == [round(0.5 * Z.width(m, w)) for _, m, w in layers]
    assert [zeros_reaching(m, w, call(m, w)) for _, m, w in layers] == [0] * len(layers)
    with Z.Lesion(pipe, part, 0.0) as lesion:
        assert lesion.hooks == []


def test_more_damage_keeps_every_neuron_less_damage_hit():
    pipe = fake_pipe()
    _, mod, where = Z.part_layers(pipe, "language")[1]

    def dead(dose):
        seen = {}
        with Z.Lesion(pipe, "language", dose):
            h = mod.register_forward_pre_hook(lambda _m, a: seen.setdefault("x", a[0].detach()))
            mod(torch.ones(1, mod.in_features))
            h.remove()
        return set((seen["x"][0] == 0).nonzero().flatten().tolist())

    assert dead(0.3) <= dead(0.6) and len(dead(0.3)) == 3 and len(dead(0.6)) == 6


def test_sheets_lay_out_every_model_and_dose(tmp_path):
    from PIL import Image

    meta = {"model": "sd15"}
    (tmp_path / "sd15").mkdir()
    (tmp_path / "sd15" / "meta.json").write_text(json.dumps(meta))
    for part in Z.PARTS:
        for dose in Z.DOSES[:3]:  # the rest missing: left blank
            folder = tmp_path / "sd15" / f"{part}@{dose:g}" / "chair"
            folder.mkdir(parents=True)
            Image.new("RGB", (64, 64), "gray").save(folder / "s0.png")
    Z.cmd_sheets(SimpleNamespace(out=str(tmp_path), fine=False))
    zoo = Image.open(tmp_path / "sheets" / "zoo_chair.png")
    assert zoo.size[0] == 230 + 160 * len(Z.DOSES) and (tmp_path / "sheets" / "sd15_god.png").exists()
    assert len({Z.seed_for(t, i) for t in Z.THINGS for i in range(Z.N_SEEDS)}) == len(Z.THINGS) * Z.N_SEEDS
