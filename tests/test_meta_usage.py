"""The home page's "Built on Meta" band (pages/index.html #built): its counts come from public_data/meta_usage.json,
which scripts/meta_usage.py sums from the spend ledger. The page and the file must agree, and the file holds counts
only."""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import meta_usage  # noqa: E402

USAGE = json.loads((REPO / "public_data" / "meta_usage.json").read_text())
PAGE = (REPO / "metalesionlab" / "web" / "pages" / "index.html").read_text()


def test_the_ledger_is_counted_by_model_with_pictures_as_items():
    lines = [json.dumps({"kind": "image", "model": "muse-image-1.0", "n": 4}),
             json.dumps({"kind": "image", "model": "muse-image-1.0", "n": 2}),
             json.dumps({"kind": "chat", "model": "muse-spark-1.3"}),
             "not json", json.dumps({"kind": "note"})]
    assert meta_usage.ledger_counts(lines) == {"muse-image-1.0": {"calls": 2, "items": 6},
                                               "muse-spark-1.3": {"calls": 1, "items": 1}}
    assert [meta_usage.about(n) for n in (41, 526, 2113, 11700, 16568)] == ["41", "526", "2,100", "11,700", "16,600"]


def test_the_band_shows_the_files_numbers():
    band = PAGE[PAGE.index('id="built"'):PAGE.index("</section>", PAGE.index('id="built"'))]
    shown = USAGE["shown"]
    for key in ("muse_spark_calls", "muse_image_pictures", "glimmer_labels", "dinov2_drawings"):
        num = shown[key].replace("+", "<small>+</small>")  # the "+" small and muted, like "of 35" above
        assert f'<p class="find-num">{num}</p>' in band, key
    for key in ("voice_clips", "sam_checks", "wonder_drawings"):
        assert f"<b data-count>{shown[key]}</b>" in band, key
    assert f"about {shown['api_calls']} calls" in band
    assert re.search(r"seven models", band) and len(USAGE["api_models"]) + len(USAGE["open_models"]) == 7


def test_the_file_holds_counts_only():
    for model in USAGE["api_models"].values():
        assert set(model) == {"calls", "items"} and all(isinstance(v, int) for v in model.values())
    assert USAGE["open_models"]["dinov2"]["atlas_drawings_compared"] == meta_usage.atlas_drawings()
