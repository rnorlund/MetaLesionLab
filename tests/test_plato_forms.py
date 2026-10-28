"""Plato's Forms: the Platonic clock's time arithmetic and reader parsing, the bed/table concepts, and /plato/forms."""
import json
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient

from metalesionlab.plato import BY_KEY, CONCEPTS, prompt_for
from metalesionlab.plato_forms import (CLOCK_TIMES, FORMS_CONCEPTS, PHOTO_TIMES, clock_prompt, chance_ten_ten,
                                       dial_distance, draw_test_clock, fmt_time, hand_marks, is_ten_ten,
                                       is_ten_ten_hour_slack, parse_reading, parse_time, rank_among, slug, swap_hands,
                                       time_distance, time_distance_hour_slack, time_from_hands, unslug,
                                       validation_set, wilson_ci, with_hour)
from metalesionlab.web import app as web
from metalesionlab.web import plato_forms_routes

IMG = web.HERE / "static" / "img" / "plato_forms"


def test_parse_time_accepts_clock_strings_on_a_12_hour_dial():
    assert parse_time("10:10") == (10, 10)
    assert parse_time(" 3:05 ") == (3, 5)
    assert parse_time("12:00") == (12, 0)
    assert parse_time("0:15") == (12, 15)
    assert parse_time("15:40") == (3, 40)
    assert parse_time("10.10") == (10, 10)
    for bad in (None, "", "ten past ten", "10:61", "25:00", "10"):
        assert parse_time(bad) is None
    assert fmt_time((1, 5)) == "1:05" and fmt_time(None) is None


def test_dial_distance_wraps_around_twelve():
    assert dial_distance(5, 715) == 10
    assert time_distance((12, 5), (11, 55)) == 10
    assert time_distance((6, 0), (12, 0)) == 360  # the farthest two times can be


def test_hands_and_times_round_trip():
    assert hand_marks(3, 0) == (3, 0)
    assert hand_marks(12, 30) == (0.5, 6)
    for h in range(1, 13):
        for m in range(0, 60, 5):
            assert time_from_hands(*hand_marks(h, m)) == (h, m)
    # a hand drawn exactly on the 2 with the minute hand on the 10 is 1:50 (at 2:50 it would be near the 3)
    assert time_from_hands(2, 10) == (1, 50)
    assert time_from_hands(0, 0) == (12, 0)


def test_swapping_the_hands():
    assert swap_hands(10, 10) == (1, 51)
    assert swap_hands(3, 0) == (12, 15)
    assert swap_hands(12, 0) == (12, 0)  # both hands on the 12
    # swapping twice gets back within a few minutes (the hour hand carries the minutes along)
    for t in [(1, 20), (4, 55), (8, 15), (11, 5)]:
        assert time_distance(swap_hands(*swap_hands(*t)), t) <= 5


def test_ten_ten_window_takes_the_hands_either_way_round():
    for t in [(10, 10), (10, 0), (10, 20), (10, 8), (1, 50), (2, 50), (1, 51)]:
        assert is_ten_ten(t), t
    for t in [(9, 58), (10, 22), (3, 0), (8, 20), (11, 5), (12, 0), (2, 30)]:
        assert not is_ten_ten(t), t
    assert not is_ten_ten(None)
    assert is_ten_ten((10, 25), window=15) and not is_ten_ten((10, 25))


def test_chance_level_is_two_twenty_minute_windows():
    # 21 minute-times around 10:10 and 20 around its swapped twin (one overlaps), out of 720
    assert chance_ten_ten() == pytest.approx(41 / 720)
    assert chance_ten_ten(0) == pytest.approx(1 / 720)  # 1:51 swapped back is 10:09, not 10:10


def test_requested_times_cover_the_dial_and_avoid_ten_ten():
    ts = [parse_time(t) for t in CLOCK_TIMES]
    assert len(ts) == 12
    assert sorted(h for h, _ in ts) == list(range(1, 13))
    assert sorted(m for _, m in ts) == list(range(0, 60, 5))
    assert all(time_distance(t, (10, 10), either_order=True) >= 25 for t in ts)
    assert set(PHOTO_TIMES) <= set(CLOCK_TIMES) and len(PHOTO_TIMES) == 6


def test_prompts_and_folder_names():
    # no time asked = exactly the core Plato's Chair clock prompt, so the core's 12 clocks can be reused
    assert clock_prompt("doodle") == prompt_for(BY_KEY["clock"], "doodle")
    assert "a simple clock face showing 3:00" in clock_prompt("doodle", "3:00")
    assert clock_prompt("photo", "9:45") == "A photo of a wall clock showing 9:45."
    assert clock_prompt("photo") == "A photo of a wall clock."
    with pytest.raises(ValueError):
        clock_prompt("oil painting")
    assert slug(None) == "any" and slug("1:20") == "t0120" and slug("12:25") == "t1225"
    assert all(unslug(slug(t)) == t for t in CLOCK_TIMES) and unslug("any") is None


def test_parse_reading_statuses():
    r = parse_reading('{"hands": 2, "time": "10:10"}')
    assert r["status"] == "time" and r["time"] == (10, 10) and r["hands"] == 2
    r = parse_reading('```json\n{"hands": 2, "time": "3:00"}\n```')
    assert r["time"] == (3, 0)
    r = parse_reading('Sure! {"hands": 0, "time": null}')
    assert r["status"] == "no_hands" and r["time"] is None
    assert parse_reading('{"hands": 1, "time": null}')["status"] == "no_hands"
    assert parse_reading('{"hands": 2, "time": null}')["status"] == "unreadable"
    assert parse_reading("I can't see a clock.")["status"] == "unparsed"
    assert parse_reading('{"hands": "two", "time": "4:15"}')["hands"] is None


def test_parse_reading_prefers_the_hand_directions():
    r = parse_reading('{"hands": 2, "short_hand_points_to": 10.2, "long_hand_points_to": 2, "time": "10:12"}')
    assert r["from_hands"] == (10, 10) and r["time_said"] == (10, 12) and r["time"] == (10, 10)
    r = parse_reading('{"hands": 2, "short_hand_points_to": 12, "long_hand_points_to": 3, "time": null}')
    assert r["time"] == (12, 15)
    r = parse_reading('{"hands": 2, "short_hand_points_to": true, "long_hand_points_to": 3, "time": "4:00"}')
    assert r["from_hands"] is None and r["time"] == (4, 0)


def test_validation_set_has_known_times_and_no_hand_clocks():
    vs = validation_set()
    timed = [v for v in vs if v["time"]]
    assert len(timed) == 24 and len(vs) == 28
    assert {"10:10", "1:50"} <= {v["time"] for v in timed}
    others = [parse_time(v["time"]) for v in timed if v["time"] not in ("10:10", "1:50")]
    assert len(set(others)) == 22 and all(time_distance(t, (10, 10), either_order=True) >= 30 for t in others)
    assert validation_set() == vs  # seeded


def test_test_clock_has_ink_and_hands_change_it():
    a = np.asarray(draw_test_clock("3:00", "marker", seed=1).convert("L"))
    b = np.asarray(draw_test_clock(None, "marker", seed=1).convert("L"))
    assert a.min() == 0 and (a < 128).sum() > (b < 128).sum()


def test_wilson_interval():
    lo, hi = wilson_ci(0, 22)
    assert lo == 0 and 0.13 < hi < 0.16
    lo, hi = wilson_ci(10, 12)
    assert lo < 10 / 12 < hi
    assert all(np.isnan(wilson_ci(0, 0)))


def test_bed_and_table_stay_out_of_the_core_list():
    assert len(CONCEPTS) == 35
    assert {c.key for c in FORMS_CONCEPTS} == {"bed", "table"}
    assert not {c.key for c in FORMS_CONCEPTS} & {c.key for c in CONCEPTS}
    assert all(c.n_ai == 16 and c.quickdraw == c.key for c in FORMS_CONCEPTS)


def test_rank_among():
    assert rank_among(0.1, [0.2, 0.3]) == 1
    assert rank_among(0.25, [0.2, 0.3]) == 2
    assert rank_among(0.2, [0.2, 0.3]) == 1


def test_hour_slack_forgives_an_hour_off_but_not_the_minute():
    assert with_hour((12, 5), 1) == (1, 5) and with_hour((1, 5), -1) == (12, 5)
    assert is_ten_ten_hour_slack((11, 10)) and is_ten_ten_hour_slack((9, 10)) and is_ten_ten_hour_slack((10, 10))
    assert not is_ten_ten_hour_slack((8, 10)) and not is_ten_ten_hour_slack((11, 30)) and not is_ten_ten_hour_slack(None)
    assert time_distance_hour_slack((2, 22), (1, 20)) == 2
    assert time_distance_hour_slack((7, 30), (6, 30)) == 0
    assert time_distance_hour_slack((8, 30), (6, 30)) == 60
    assert chance_ten_ten(hour_slack=True) > 2 * chance_ten_ten()


# ---------- the /plato/forms page ----------

@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(web, "DATA_DIR", tmp_path)
    plato_forms_routes._cache.clear()
    return TestClient(web.app)


def test_forms_page_renders_with_credit(client):
    r = client.get("/plato/forms")
    assert r.status_code == 200
    assert "What time does an AI draw?" in r.text and "Quick, Draw!" in r.text and "CC BY 4.0" in r.text
    assert "/static/js/plato_forms.js" in r.text and "/static/css/plato_forms.css" in r.text


def test_forms_data_is_statistics_only(client):
    d = client.get("/api/plato/forms").json()
    groups = d["clock"]["groups"]
    for name in ("muse_doodle_default", "muse_doodle_asked", "sdxl_doodle_default", "people"):
        assert name in groups and groups[name]["n"] > 0
        assert 0 <= groups[name]["ten_ten"]["share"] <= 1
    assert d["clock"]["chance_ten_ten"] == pytest.approx(41 / 720, abs=1e-3)
    assert set(d["concepts"]["items"]) == {"bed", "table"}
    assert len(d["concepts"]["core_concepts"]) == 35
    assert "CC BY 4.0" in d["attribution"]
    text = json.dumps(d)
    assert '"drawing"' not in text and "ndjson" not in text and "key_id" not in text  # no Quick, Draw! stroke records


def test_forms_api_reports_missing_data(client, monkeypatch, tmp_path):
    monkeypatch.setattr(plato_forms_routes, "DATA", tmp_path / "missing.json")
    assert client.get("/api/plato/forms").status_code == 503
    (tmp_path / "bad.json").write_text(json.dumps({"clock": {"groups": {}}}))
    monkeypatch.setattr(plato_forms_routes, "DATA", tmp_path / "bad.json")
    assert client.get("/api/plato/forms").status_code == 503


def test_forms_page_images_exist_and_are_small():
    html = (web.HERE / "pages" / "plato_forms.html").read_text()
    for name in re.findall(r"plato_forms/(\w+\.webp)", html):
        assert (IMG / name).exists(), name
    for stem in ("wall_muse", "wall_sdxl", "wall_people", "grid_bed_ai", "grid_bed_people", "grid_table_ai",
                 "grid_table_people", "kinds_bed_ai", "kinds_table_ai"):  # swapped in by plato_forms.js
        assert (IMG / f"{stem}.webp").exists(), stem
    added = sum(p.stat().st_size for p in IMG.iterdir()) + sum(
        (web.HERE / rel).stat().st_size for rel in ("static/js/plato_forms.js", "static/css/plato_forms.css",
                                                   "pages/plato_forms.html", "data/plato_forms.json"))
    assert added < 1.5 * 1024 * 1024


def test_app_includes_the_forms_router_once():
    assert web.SITE_ROUTERS["plato"].count("plato_forms_routes") == 1  # on the Plato site only
    assert "plato_forms_routes" not in web.SITE_ROUTERS["lingua"]
