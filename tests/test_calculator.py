"""Tests of the calculator API and the web page. No database and no internet needed:
a small map is generated into a temporary folder.

    pip install pytest httpx
    python -m pytest -q tests
(the calculator binary must be built first: cd calc && cargo build --release)
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAP_ID = 4242


def make_map(path: Path, circles: int = 200) -> None:
    lines = [
        "osu file format v14", "", "[General]", "AudioFilename: audio.mp3", "Mode: 0", "",
        "[Metadata]", "Title:Test Song", "Artist:pp-lab", "Creator:tester", "Version:Insane",
        "BeatmapID:4242", "BeatmapSetID:4200", "",
        "[Difficulty]", "HPDrainRate:5", "CircleSize:4", "OverallDifficulty:8", "ApproachRate:9",
        "SliderMultiplier:1.4", "SliderTickRate:1", "",
        "[TimingPoints]", "0,300,4,2,0,60,1,0", "", "[HitObjects]",
    ]
    for i in range(circles):
        x = 64 + (i * 97) % 384
        y = 48 + (i * 61) % 288
        lines.append(f"{x},{y},{1000 + i * 150},1,0,0:0:0:0:")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    maps = tmp_path_factory.mktemp("maps")
    make_map(maps / f"{MAP_ID}.osu")
    os.environ.update({
        "MAPS_DIR": str(maps), "MAPS_CACHE_DIR": str(tmp_path_factory.mktemp("cache")),
        "DB_NAME": "", "RATE_LIMIT_IP_HEADER": "", "CALC_RATE_PER_MINUTE": "1000",
        "SITE_NAME": "Test <Lab>", "THEME_CSS": "themes/example.css",
    })
    sys.path.insert(0, str(ROOT))
    for mod in [m for m in list(sys.modules) if m.startswith("pplab")]:
        del sys.modules[mod]
    import pplab.config  # noqa: F401
    api = importlib.import_module("pplab.api")
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def calc(client, **params):
    r = client.get("/pp-lab/api/calc", params=dict({"map": MAP_ID}, **params))
    assert r.status_code == 200, r.text
    return r.json()


def test_full_combo_ss(client):
    d = calc(client)
    assert d["map"]["title"] == "Test Song" and d["map"]["objects"] == 200 and d["map"]["max_combo"] == 200
    for v in d["variants"]:
        assert d["results"][v]["error"] is None and d["results"][v]["pp"] > 0


def test_accuracy_lowers_pp(client):
    table = calc(client)["results"]["tsg"]["acc_table"]
    pps = [row["pp"] for row in table]
    assert pps == sorted(pps, reverse=True)


def test_mods_change_pp(client):
    nm = calc(client)["results"]["tsg"]["pp"]
    hddt = calc(client, mods="HDDT")["results"]["tsg"]["pp"]
    nc = calc(client, mods="NC")["results"]["tsg"]["pp"]
    dt = calc(client, mods="DT")["results"]["tsg"]["pp"]
    assert hddt > nm and abs(nc - dt) < 0.01


def test_hits_give_accuracy(client):
    d = calc(client, n100=10, n50=2, miss=1)
    assert d["play"]["acc"] == pytest.approx(100 * (300 * 187 + 100 * 10 + 50 * 2) / (300 * 200), abs=0.01)
    assert d["results"]["tsg"]["pp"] < calc(client)["results"]["tsg"]["pp"]


def test_links_and_combo(client):
    a = calc(client, map=f"https://osu.ppy.sh/beatmapsets/4200#osu/{MAP_ID}")
    b = calc(client, map=f"https://osu.ppy.sh/b/{MAP_ID}")
    assert a["map"]["id"] == b["map"]["id"] == MAP_ID
    # circles only: current formulas don't scale pp by combo without sliders, only the value is passed on
    assert calc(client, combo=50)["play"]["combo"] == 50


def test_convert_to_mania(client):
    d = calc(client, mode=3, acc=97)
    assert d["play"]["mode"] == 3 and d["results"]["tsg"]["pp"] > 0


@pytest.mark.parametrize("params,status", [
    ({"map": "abc"}, 400), ({"mods": "XYZ"}, 400), ({"mods": "HDX"}, 400), ({"mods": "99999999999"}, 400),
    ({"acc": "101"}, 422), ({"acc": "nan"}, 422), ({"miss": "-1"}, 422), ({"map": "0"}, 400),
])
def test_bad_input(client, params, status):
    r = client.get("/pp-lab/api/calc", params=dict({"map": MAP_ID}, **params))
    assert r.status_code == status, r.text


def test_page_and_security_headers(client):
    r = client.get("/pp-lab/")
    assert r.status_code == 200
    assert "Test &lt;Lab&gt;" in r.text and "<Lab>" not in r.text  # site name is escaped
    assert "assets/theme.css" in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/pp-lab/assets/app.js").status_code == 200
    assert client.get("/pp-lab/assets/theme.css").status_code == 200
    assert client.get("/pp-lab/assets/../config.py").status_code == 404
    assert client.get("/pp-lab/assets/index.html").status_code == 404


def test_rate_limit(client):
    from pplab import calculator, config
    config.CALC_RATE_PER_MINUTE = 3
    calculator._hits.clear()
    calculator._cache.clear()
    codes = [client.get("/pp-lab/api/calc", params={"map": MAP_ID, "acc": 90 + i}).status_code for i in range(5)]
    config.CALC_RATE_PER_MINUTE = 1000
    assert codes[:3] == [200, 200, 200] and 429 in codes[3:]


def test_relax_off_ignores_rx(client, monkeypatch):
    import pplab.config as cfg
    monkeypatch.setattr(cfg, "RELAX_PP", False)
    d = calc(client, mods="RX")
    assert d["play"]["mods"] == "NM" and not d["play"]["relax"]
    assert d["variants"] == ["tsg", "osu_2026_07", "osu_2025_10"]
    assert client.get("/pp-lab/api/calc/variants").json()["relax"] is False


def test_relax_on(client, monkeypatch):
    import pplab.config as cfg
    monkeypatch.setattr(cfg, "RELAX_PP", True)
    assert client.get("/pp-lab/api/calc/variants").json()["relax"] is True
    nm = calc(client)["results"]["tsg"]["pp"]
    d = calc(client, mods="HDRX")
    assert d["play"]["relax"] and d["play"]["mods"] == "HDRX"
    # only the formula with a relax version, and it is the base one
    assert d["variants"] == ["tsg"] and d["base"] == "tsg"
    r = d["results"]["tsg"]
    assert r["error"] is None and r["pp"] > 0 and r["pp"] != nm
    assert all(row["mods"].endswith("RX") for row in r["mod_table"])
    # osu!mania has no relax: RX is dropped
    m = calc(client, mods="RX", mode=3)
    assert not m["play"]["relax"] and len(m["variants"]) == 3
