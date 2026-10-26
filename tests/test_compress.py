"""CPU tests for compress.py on tiny random models (Glimmer's own modeling code, and Llama)."""
import math
from types import SimpleNamespace

import pytest
import torch

from metalesionlab import compress as C

transformers = pytest.importorskip("transformers")


@pytest.fixture(scope="module")
def tiny_glimmer():
    from transformers import MuseGlimmerConfig, MuseGlimmerForConditionalGeneration

    cfg = MuseGlimmerConfig(
        text_config=dict(hidden_size=32, intermediate_size=64, num_hidden_layers=8, num_attention_heads=4,
                         num_key_value_heads=2, head_dim=8, vocab_size=128, sliding_window=4,
                         max_position_embeddings=64, bos_token_id=1, eos_token_id=2, pad_token_id=0),
        vision_config=dict(hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2),
        out_hidden_size=16, projector_hidden_size=16)
    torch.manual_seed(0)
    return MuseGlimmerForConditionalGeneration(cfg).eval()


def fresh(model):
    import copy
    return copy.deepcopy(model)


def logits(model, ids):
    with torch.no_grad():
        return model(**C.left_pad(ids, 0)).logits


def nocache_greedy(model, seq, n):
    out = []
    for _ in range(n):
        b = C.left_pad([torch.cat([seq, torch.tensor(out, dtype=torch.long)])], 0)
        with torch.no_grad():
            out.append(int(model(**b, use_cache=False).logits[0, -1].argmax()))
    return out


SEQS = [torch.tensor([5, 9, 14, 3, 77, 21, 40, 8, 6]), torch.tensor([11, 12, 13, 99, 3, 4])]


def test_prune_layer_fields_shortens_every_per_layer_list():
    cfg = SimpleNamespace(num_hidden_layers=4, layer_types=["s", "s", "s", "f"], layer_rope_theta=[1e4, 1e4, 1e4, 0],
                          architectures=["X"], hidden_size=4, _private=[1, 2, 3, 4], other=(1, 2, 3, 4))
    changed = C.prune_layer_fields(cfg, [3, 0])
    assert cfg.num_hidden_layers == 2
    assert cfg.layer_types == ["s", "f"] and cfg.layer_rope_theta == [1e4, 0] and cfg.other == (1, 4)
    assert cfg.architectures == ["X"] and cfg._private == [1, 2, 3, 4]
    assert set(changed) == {"num_hidden_layers", "layer_types", "layer_rope_theta", "other"}
    with pytest.raises(ValueError):
        C.prune_layer_fields(cfg, [0, 0])
    with pytest.raises(ValueError):
        C.prune_layer_fields(cfg, [5])


def test_skip_is_reversible_and_skipped_layer_passes_input(tiny_glimmer):
    m = tiny_glimmer
    base = logits(m, SEQS)
    with C.SkipLayers(m, [2, 5]):
        skipped = logits(m, SEQS)
        with C.BlockInfluence(m, last_only=False) as bi:
            logits(m, SEQS)
        assert bi.values()[2] == 0 and bi.values()[5] == 0 and bi.values()[0] > 0
    assert not torch.allclose(base, skipped)
    assert torch.equal(base, logits(m, SEQS))
    assert all("forward" not in layer.__dict__ for layer in C.decoder_layers(m))


def test_cached_decoding_with_skipped_first_sliding_and_full_layer(tiny_glimmer):
    # Layer 0 is the first sliding layer and layer 3 the first full one: masks read their caches.
    # A left-padded batch makes the masks real; a skip that leaves those caches empty decodes wrong.
    m = tiny_glimmer
    with C.SkipLayers(m, [0, 3]):
        cached = C.greedy_decode(m, C.left_pad(SEQS, 0), set(), 7)
        assert cached == [nocache_greedy(m, s, 7) for s in SEQS]


def test_removal_matches_skip_and_edits_config(tiny_glimmer):
    m = fresh(tiny_glimmer)
    cut = [0, 3, 6]
    with C.SkipLayers(m, cut):
        want = logits(m, SEQS)
        want_gen = C.greedy_decode(m, C.left_pad(SEQS, 0), set(), 6)
    n_before = C.count_params(m)["decoder_params"]
    info = C.remove_layers(m, cut)
    cfg = m.config.get_text_config()
    assert info["kept"] == [1, 2, 4, 5, 7]
    assert cfg.num_hidden_layers == 5 and len(C.decoder_layers(m)) == 5
    assert cfg.layer_types == ["sliding_attention", "sliding_attention", "sliding_attention", "sliding_attention",
                               "full_attention"]
    assert cfg.layer_rope_theta[-1] == 0 and len(cfg.layer_rope_theta) == 5
    assert [layer.self_attn.layer_idx for layer in C.decoder_layers(m)] == list(range(5))
    assert {"num_hidden_layers", "layer_types", "layer_rope_theta"} <= set(info["fields"])
    assert torch.allclose(logits(m, SEQS), want, atol=1e-5)
    assert C.greedy_decode(m, C.left_pad(SEQS, 0), set(), 6) == want_gen
    assert C.count_params(m)["decoder_params"] == n_before * 5 // 8


def test_pruned_model_saves_and_reloads(tiny_glimmer, tmp_path):
    from transformers import MuseGlimmerForConditionalGeneration

    m = fresh(tiny_glimmer)
    C.remove_layers(m, [1, 4])
    want = logits(m, SEQS)
    m.save_pretrained(tmp_path)
    again = MuseGlimmerForConditionalGeneration.from_pretrained(tmp_path).eval()
    assert again.config.get_text_config().num_hidden_layers == 6
    assert torch.allclose(logits(again, SEQS), want, atol=1e-5)


def test_llama_style_model():
    from transformers import LlamaConfig, LlamaForCausalLM

    torch.manual_seed(0)
    m = LlamaForCausalLM(LlamaConfig(hidden_size=32, intermediate_size=64, num_hidden_layers=6, num_attention_heads=4,
                                     num_key_value_heads=2, vocab_size=128, max_position_embeddings=64)).eval()
    with C.SkipLayers(m, [0, 2]):
        want = logits(m, SEQS)
        assert C.greedy_decode(m, C.left_pad([SEQS[0]], 0), set(), 5)[0] == nocache_greedy(m, SEQS[0], 5)
    C.remove_layers(m, [0, 2])
    assert m.config.num_hidden_layers == 4
    assert torch.allclose(logits(m, SEQS), want, atol=1e-5)


def test_text_guard_perplexity_ignores_padding(tiny_glimmer):
    seqs = [torch.tensor([1, 5, 9, 14, 3, 77]), torch.tensor([1, 11, 12]), torch.tensor([1, 40, 41, 42, 43])]
    guard = C.TextGuard(["en", "es", "en"], seqs, 0)
    batched = guard.run(tiny_glimmer, batch_size=3)
    single = guard.run(tiny_glimmer, batch_size=1)
    assert batched["ppl"] == pytest.approx(single["ppl"], rel=1e-4)
    assert batched["tokens"] == 5 + 2 + 4 and set(batched) >= {"ppl_en", "ppl_es"}
    with torch.no_grad():
        lg = tiny_glimmer(input_ids=seqs[1][None]).logits[0, :-1]
    nll = torch.nn.functional.cross_entropy(lg, seqs[1][1:]).item()
    assert batched["ppl_es"] == pytest.approx(math.exp(nll), rel=1e-3)


def test_left_pad_positions():
    b = C.left_pad([torch.tensor([7, 8, 9]), torch.tensor([4])], pad_id=0)
    assert b["input_ids"].tolist() == [[7, 8, 9], [0, 0, 4]]
    assert b["attention_mask"].tolist() == [[1, 1, 1], [0, 0, 1]]
    assert b["position_ids"].tolist() == [[0, 1, 2], [0, 0, 0]]


@pytest.mark.parametrize("raw,expected", [
    ("Umbrella<|eot|>", "Umbrella"), ("**cat**.", "cat"), ("Kettle\nIt is a kettle", "Kettle"), ("", ""),
])
def test_answer_text(raw, expected):
    assert C.answer_text(raw) == expected


def test_guards_and_path_selection():
    intact = {"correct": 37, "ppl": 10.0}
    assert C.within_guard({"correct": 36, "ppl": 11.0}, intact)["within_guard"]
    assert not C.within_guard({"correct": 35, "ppl": 10.0}, intact)["acc_ok"]
    assert not C.within_guard({"correct": 37, "ppl": 11.01}, intact)["ppl_ok"]
    steps = [{"removed": [1], "within_guard": True}, {"removed": [1, 2], "within_guard": False},
             {"removed": [1, 2, 3], "within_guard": True}]
    assert C.last_within_guard(steps)["removed"] == [1]
    assert C.last_within_guard(steps[1:]) is None
    for s, (en, es) in zip(steps, [(19, 17), (18, 17), (17, 16)]):
        s["heldout_by_lang"] = {"en": {"correct": en}, "es": {"correct": es}}
    C.mark_heldout(steps, intact_heldout_correct=36)  # floor: 0.95 x 36 = 34.2
    assert [s["heldout_ok"] for s in steps] == [True, True, False]
    assert [s["confirmed"] for s in steps] == [True, False, False]


def test_stats_helpers():
    assert C.wilson(37, 39)[0] < 37 / 39 < C.wilson(37, 39)[1] and C.wilson(20, 20)[1] == 1.0
    assert C.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert C.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert C._ranks([5, 1, 5, 2]) == [3.5, 1, 3.5, 2]
    assert C.rank_permutation_test([10, 11, 12, 13, 14], [0, 1, 2, 3, 4], n_perm=2000) < 0.02
    assert C.rank_permutation_test([0, 2, 4], [1, 3, 5], n_perm=2000) > 0.3


def test_compare_layer_types():
    layers = [{"type": "full_attention" if i % 4 == 3 else "sliding_attention", "skip_d_ppl_rel": 1.0 if i % 4 == 3
               else 0.01 * i, "skip_d_acc": -0.05 if i % 4 == 3 else 0.0, "block_influence": 0.2} for i in range(16)]
    out = C.compare_layer_types(layers)
    assert out["full_attention"]["n"] == 4 and out["sliding_attention"]["n"] == 12
    assert out["full_attention"]["layers_losing_naming"] == 4
    assert out["p_d_ppl"] < 0.01 and out["p_block_influence"] == 1.0


def test_summarize_naming():
    rows = [{"lang": "en", "code": "Correct"}, {"lang": "en", "code": "Semantic"}, {"lang": "es", "code": "Correct"}]
    s = C.summarize_naming(rows, keep_items=False)
    assert s["correct"] == 2 and s["by_lang"]["en"]["accuracy"] == 0.5 and "items" not in s
