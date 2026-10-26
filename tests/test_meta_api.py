import pytest

from metalesionlab import meta_api
from metalesionlab.meta_api import BudgetExceeded, parse_sam_output, token_cost

# Shape of a real sam-3.1 reply (mask payload shortened).
SAM_TEXT = ("<0f>0<|box;x1=462;y1=261;x2=1252;y2=1364;w=1600;h=1600;c=0.93|>"
            "<|mask;x=0;y=0;c=0.93;data=1024,734,~!!4'{#K|>,"
            "2<|box;x1=0;y1=0;x2=160;y2=160;w=1600;h=1600|><|mask;x=0;y=0;data=8,8,~!!|>")


def test_parse_sam_output_reads_boxes_ids_and_confidence():
    first, second = parse_sam_output(SAM_TEXT)
    assert first.obj_id == 0 and first.box == (462, 261, 1252, 1364)
    assert first.image_size == (1600, 1600) and first.confidence == pytest.approx(0.93)
    assert second.obj_id == 2 and second.confidence is None
    assert second.area_fraction == pytest.approx(0.01)


def test_parse_sam_output_empty_means_no_match():
    assert parse_sam_output("") == []


def test_token_cost_uses_cached_and_output_prices():
    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000,
             "prompt_tokens_details": {"cached_tokens": 500_000}}
    assert token_cost("muse-spark-1.3", usage) == pytest.approx(0.5 * 1.25 + 0.5 * 0.15 + 4.25)


def test_token_cost_rejects_unpriced_models():
    with pytest.raises(KeyError):
        token_cost("muse-spark-1.3-contributor", {"prompt_tokens": 1})


def test_budget_cap_blocks_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(meta_api, "LEDGER", tmp_path / "costs.jsonl")
    monkeypatch.setattr(meta_api, "BUDGET_USD", 1.0)
    meta_api._record("chat", "muse-spark-1.3", 0.99)
    meta_api._check_budget(0.005)
    with pytest.raises(BudgetExceeded):
        meta_api._check_budget(0.02)
