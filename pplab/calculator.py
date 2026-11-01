"""pp calculator: pp of any map for a chosen accuracy or hit counts, mods and formula.

GET /pp-lab/api/calc?map=129891&mods=HDDT&acc=98.5
GET /pp-lab/api/calc?map=129891&mods=72&n100=12&n50=0&miss=1&combo=1200&mode=0

The .osu file is taken from MAPS_DIR (bancho's folder) or downloaded once from
osu.ppy.sh into MAPS_CACHE_DIR. Map details come from bancho's maps table when the
map is there, otherwise from the .osu file itself.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
import urllib.request
from collections import OrderedDict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from . import config, db

router = APIRouter()

# formulas the calculator offers (all of them support every mode)
CALC_VARIANTS = ["tsg", "osu_2026_07", "osu_2025_10"]

MODS = {
    "NF": 1, "EZ": 2, "TD": 4, "HD": 8, "HR": 16, "SD": 32, "DT": 64, "RX": 128,
    "HT": 256, "NC": 512 | 64, "FL": 1024, "SO": 4096, "PF": 16384 | 32,
}
MOD_ORDER = ["NF", "EZ", "TD", "HD", "HR", "SD", "PF", "DT", "NC", "HT", "FL", "SO", "RX"]
# mods that change pp (the others only matter for the client)
PP_MODS = 1 | 2 | 8 | 16 | 64 | 256 | 512 | 1024 | 4096

ACC_PRESETS = [100.0, 99.0, 98.0, 97.0, 95.0]
MOD_PRESETS = {
    0: ["", "HD", "HR", "DT", "HDHR", "HDDT", "HDDTHR", "FL"],
    1: ["", "HD", "HR", "DT", "HDDT", "HDDTHR"],
    2: ["", "HD", "HR", "DT", "HDHR", "HDDT"],
    3: ["", "EZ", "HT", "DT", "EZDT"],
}

_cache: OrderedDict[str, dict] = OrderedDict()
_cache_lock = threading.Lock()
_hits: dict[str, list[float]] = {}
_hits_lock = threading.Lock()
_busy = threading.BoundedSemaphore(max(1, config.CALC_CONCURRENCY))
_download_lock = threading.Lock()
# every mod bit osu! stable knows; anything above is rejected
_ALL_MODS = (1 << 31) - 1


def parse_mods(raw: str | None) -> int:
    if not raw:
        return 0
    raw = raw.strip().upper().replace("+", "").replace(",", "").replace(" ", "")
    if raw.isdigit():
        if len(raw) > 10 or int(raw) > _ALL_MODS:
            raise HTTPException(400, "invalid mods")
        return int(raw)
    if len(raw) % 2:
        raise HTTPException(400, "invalid mods")
    mods = 0
    for i in range(0, len(raw), 2):
        code = raw[i:i + 2]
        if code not in MODS:
            raise HTTPException(400, f"unknown mod {code}")
        mods |= MODS[code]
    return mods


def mods_name(mods: int) -> str:
    out = []
    for code in MOD_ORDER:
        bit = MODS[code]
        if code == "DT" and mods & 512:
            continue  # NC shows instead of DT
        if code == "SD" and mods & 16384:
            continue
        if mods & bit == bit:
            out.append(code)
    return "".join(out) or "NM"


def client_ip(request: Request) -> str:
    """The client's address: from the header your proxy sets, else the connection itself.

    Only trust a header that the proxy overwrites (nginx: proxy_set_header X-Real-IP $remote_addr),
    otherwise anyone can send a different address with every request."""
    if config.RATE_LIMIT_IP_HEADER:
        value = request.headers.get(config.RATE_LIMIT_IP_HEADER)
        if value:
            return value.split(",")[0].strip()[:64]
    return request.client.host if request.client else "?"


def _rate_limit(request: Request) -> None:
    ip = client_ip(request)
    now = time.time()
    with _hits_lock:
        window = [t for t in _hits.get(ip, []) if now - t < 60]
        if len(window) >= config.CALC_RATE_PER_MINUTE:
            raise HTTPException(429, "too many requests, try again in a minute")
        window.append(now)
        _hits[ip] = window
        if len(_hits) > 10000:
            for key in [k for k, v in _hits.items() if not v or now - v[-1] >= 60]:
                del _hits[key]


def _trim_cache(cache_dir: Path) -> None:
    files = sorted(cache_dir.glob("*.osu"), key=lambda f: f.stat().st_mtime)
    for f in files[: max(0, len(files) - config.MAPS_CACHE_MAX_FILES)]:
        try:
            f.unlink()
        except OSError:
            pass


def _map_path(map_id: int) -> Path:
    local = config.MAPS_DIR / f"{map_id}.osu"
    if local.exists() and local.stat().st_size > 0:
        return local
    cache_dir = config.MAPS_CACHE_DIR
    cached = cache_dir / f"{map_id}.osu"
    if cached.exists() and cached.stat().st_size > 0:
        return cached
    # only this fixed address with a numeric id is ever requested (no user-given URLs)
    with _download_lock:
        if cached.exists() and cached.stat().st_size > 0:
            return cached
        try:
            req = urllib.request.Request(f"https://osu.ppy.sh/osu/{int(map_id)}", headers={"User-Agent": "pp-lab"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read(5_000_001)
        except Exception:
            raise HTTPException(404, "map not found")
        if not data or len(data) > 5_000_000 or not data.lstrip(b"\xef\xbb\xbf").startswith(b"osu file format") \
                or b"[HitObjects]" not in data:
            raise HTTPException(404, "map not found")
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(cached)
        _trim_cache(cache_dir)
    return cached


def _parse_osu(path: Path) -> dict:
    """Metadata, mode and hit object count from the .osu file."""
    info = {"artist": "", "title": "", "version": "", "creator": "", "mode": 0, "set_id": 0, "objects": 0}
    section = ""
    keys = {"Artist": "artist", "Title": "title", "Version": "version", "Creator": "creator"}
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                continue
            if section == "HitObjects":
                if line:
                    info["objects"] += 1
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key, value = key.strip(), value.strip()
            if section == "General" and key == "Mode" and value.isdigit():
                info["mode"] = int(value)
            elif section == "Metadata" and key in keys:
                info[keys[key]] = value
            elif section == "Metadata" and key == "BeatmapSetID":
                try:
                    info["set_id"] = int(value)
                except ValueError:
                    pass
    return info


def _db_map(map_id: int) -> dict | None:
    if not config.DB_ENABLED:
        return None
    try:
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, set_id, artist, title, version, creator, mode, status, bpm, cs, ar, od, hp, "
                    "total_length FROM maps WHERE id = %s",
                    (map_id,),
                )
                return cur.fetchone()
        finally:
            conn.close()
    except Exception:
        return None


def _run(variant: str, scores: list[dict]) -> list[dict]:
    proc = subprocess.run(
        [config.CALC_BIN], input=json.dumps({"variant": variant, "scores": scores}),
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise HTTPException(500, "calculator error")
    return json.loads(proc.stdout)


def _f(x: float) -> float:
    return round(float(x), 2)


@router.get("/calc")
def calc(
    request: Request,
    map: str = Query(..., max_length=200),
    mods: str | None = Query(None, max_length=40),
    mode: int | None = Query(None, ge=0, le=3),
    acc: float | None = Query(None, ge=0, le=100),
    n100: int = Query(0, ge=0, le=100000),
    n50: int = Query(0, ge=0, le=100000),
    miss: int = Query(0, ge=0, le=100000),
    combo: int | None = Query(None, ge=0, le=100000),
):
    """pp of one play in every calculator formula, plus accuracy and mod tables."""
    m = re.search(r"(\d+)\s*$", map) or re.search(r"/b(?:eatmaps)?/(\d+)", map) or re.search(r"#\w+/(\d+)", map)
    if not m:
        raise HTTPException(400, "map id expected")
    map_id = int(m.group(1))
    if not 0 < map_id < 2_147_483_647:
        raise HTTPException(400, "map id expected")
    mod_bits = parse_mods(mods) & ~128  # relax has no pp formula here

    key = json.dumps([map_id, mod_bits, mode, acc, n100, n50, miss, combo])
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]

    _rate_limit(request)
    if not _busy.acquire(timeout=15):
        raise HTTPException(503, "busy, try again in a moment")
    try:
        body = _calculate(map_id, mod_bits, mode, acc, n100, n50, miss, combo)
    finally:
        _busy.release()
    with _cache_lock:
        _cache[key] = body
        if len(_cache) > 3000:
            _cache.popitem(last=False)
    return body


def _calculate(map_id: int, mod_bits: int, mode: int | None, acc: float | None,
               n100: int, n50: int, miss: int, combo: int | None) -> dict:
    path = _map_path(map_id)
    osu = _parse_osu(path)
    row = _db_map(map_id)
    map_mode = int(row["mode"]) if row else osu["mode"]
    play_mode = map_mode if mode is None else mode
    if map_mode != 0 and play_mode != map_mode:
        raise HTTPException(400, "only osu!standard maps can be converted to other modes")

    base = {"map": str(path), "mode": play_mode, "mods": mod_bits}
    play = dict(base, id=0)
    shown_acc = acc
    if acc is not None:
        play.update(acc=acc, nmiss=miss)
    else:
        play.update(n100=n100, n50=n50, nmiss=miss)
        if play_mode == 0 and osu["objects"]:
            n300 = max(osu["objects"] - n100 - n50 - miss, 0)
            total = n300 + n100 + n50 + miss
            shown_acc = round(100 * (300 * n300 + 100 * n100 + 50 * n50) / (300 * total), 2) if total else 100.0
    if combo is not None and combo > 0:
        play["combo"] = combo

    scores = [play]
    for i, a in enumerate(ACC_PRESETS):
        scores.append(dict(base, id=100 + i, acc=a))
    presets = MOD_PRESETS.get(play_mode, [""])
    for i, name in enumerate(presets):
        scores.append(dict(base, id=200 + i, acc=100.0, mods=parse_mods(name)))

    results: dict[str, dict] = {}
    stars = max_combo = 0.0
    for variant in CALC_VARIANTS:
        out = {r["id"]: r for r in _run(variant, scores)}
        p = out[0]
        if variant == config.BASE_VARIANT:
            stars, max_combo = p["stars"], p["max_combo"]
        results[variant] = {
            "pp": _f(p["pp"]), "stars": _f(p["stars"]), "error": p["error"],
            "parts": {"aim": _f(p["aim"]), "speed": _f(p["speed"]), "acc": _f(p["acc"]),
                      "fl": _f(p["fl"]), "reading": _f(p["reading"])},
            "acc_table": [{"acc": a, "pp": _f(out[100 + i]["pp"])} for i, a in enumerate(ACC_PRESETS)],
            "mod_table": [{"mods": mods_name(parse_mods(n)), "pp": _f(out[200 + i]["pp"]),
                           "stars": _f(out[200 + i]["stars"])} for i, n in enumerate(presets)],
        }

    info = {
        "id": map_id,
        "set_id": int(row["set_id"]) if row else osu["set_id"],
        "artist": row["artist"] if row else osu["artist"],
        "title": row["title"] if row else osu["title"],
        "version": row["version"] if row else osu["version"],
        "creator": row["creator"] if row else osu["creator"],
        "mode": map_mode,
        "status": int(row["status"]) if row else None,
        "on_server": row is not None,
        "objects": osu["objects"],
        "max_combo": int(max_combo),
        "stars": _f(stars),
    }
    if row:
        info.update(bpm=_f(row["bpm"]), cs=_f(row["cs"]), ar=_f(row["ar"]), od=_f(row["od"]),
                    hp=_f(row["hp"]), length=int(row["total_length"]))
    body = {
        "map": info,
        "play": {"mode": play_mode, "mods": mods_name(mod_bits), "mods_int": mod_bits, "acc": shown_acc,
                 "n100": n100, "n50": n50, "miss": miss, "combo": combo if combo else int(max_combo)},
        "base": config.BASE_VARIANT,
        "variants": CALC_VARIANTS,
        "results": results,
    }
    return body


@router.get("/calc/variants")
def calc_variants():
    """Names and descriptions of the calculator's formulas (no database needed)."""
    meta = {v["id"]: v for v in json.loads((config.ROOT / "variants.json").read_text(encoding="utf-8"))}
    return {
        "base": config.BASE_VARIANT,
        "variants": [
            {"id": v, "name": meta.get(v, {}).get("name", {"en": v}), "period": meta.get(v, {}).get("period", {})}
            for v in CALC_VARIANTS
        ],
    }
