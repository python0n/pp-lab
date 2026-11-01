"""API tylko do odczytu dla strony reworków w Shiinie.

Dane pochodzą z tabel pplab_*, które wypełnia `python -m pplab.recalc`.
Te same trasy są pod /hypo/api (stara ścieżka, już przekierowana w nginx)
i /pp-lab/api.
"""
from __future__ import annotations

import json
import subprocess

from fastapi import APIRouter, FastAPI, HTTPException, Query

from . import config, db
from .variants import load_variants

app = FastAPI(title="pp-lab", docs_url=None, redoc_url=None, openapi_url=None)
router = APIRouter()


def _variant(vid: str, mode: int | None = None) -> dict:
    for v in load_variants():
        if v["id"] == vid:
            if mode is not None and mode not in v["modes"]:
                raise HTTPException(400, "ten wariant nie obsługuje wybranego trybu")
            return v
    raise HTTPException(404, "nieznany wariant")


def _query(sql: str, args: tuple = ()) -> list[dict]:
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return list(cur.fetchall())
    finally:
        conn.close()


def _f(x) -> float | None:
    return None if x is None else round(float(x), 2)


@router.get("/variants")
def variants():
    runs = _query("SELECT variant, mode, finished_at, scores FROM pplab_runs WHERE finished_at IS NOT NULL")
    by_variant: dict[str, dict] = {}
    for r in runs:
        by_variant.setdefault(r["variant"], {})[str(r["mode"])] = {
            "updated": r["finished_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scores": r["scores"],
        }
    return {
        "base": config.BASE_VARIANT,
        "variants": [dict(v, runs=by_variant.get(v["id"], {})) for v in load_variants()],
    }


@router.get("/players")
def players(
    variant: str,
    mode: int = Query(0, ge=0, le=3),
    q: str | None = Query(None, max_length=32),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    _variant(variant, mode)
    base = config.BASE_VARIANT
    where = "n.variant = %s AND n.mode = %s"
    args: list = [base, variant, mode]
    if q:
        where += " AND u.name LIKE %s"
        args.append(f"%{q}%")
    rows = _query(
        "SELECT n.user_id, u.name, u.country, n.pp AS new_pp, n.`rank` AS new_rank, n.plays, "
        "b.pp AS old_pp, b.`rank` AS old_rank "
        "FROM pplab_players n "
        "JOIN users u ON u.id = n.user_id AND u.priv & 1 "
        "LEFT JOIN pplab_players b ON b.variant = %s AND b.mode = n.mode AND b.user_id = n.user_id "
        f"WHERE {where} ORDER BY n.`rank` LIMIT %s OFFSET %s",
        tuple(args + [limit, offset]),
    )
    total = _query(
        "SELECT COUNT(*) AS c FROM pplab_players n JOIN users u ON u.id = n.user_id AND u.priv & 1 "
        f"WHERE {where}",
        tuple(args[1:]),
    )[0]["c"]
    return {
        "total": total,
        "players": [
            {
                "id": r["user_id"], "name": r["name"], "country": r["country"],
                "new_pp": _f(r["new_pp"]), "old_pp": _f(r["old_pp"]),
                "new_rank": r["new_rank"], "old_rank": r["old_rank"], "plays": r["plays"],
            }
            for r in rows
        ],
    }


@router.get("/player")
def player(variant: str, id: int, mode: int = Query(0, ge=0, le=3)):
    _variant(variant, mode)
    base = config.BASE_VARIANT
    info = _query(
        "SELECT u.id, u.name, u.country, n.pp AS new_pp, n.`rank` AS new_rank, n.plays, "
        "b.pp AS old_pp, b.`rank` AS old_rank "
        "FROM users u "
        "LEFT JOIN pplab_players n ON n.variant = %s AND n.mode = %s AND n.user_id = u.id "
        "LEFT JOIN pplab_players b ON b.variant = %s AND b.mode = %s AND b.user_id = u.id "
        "WHERE u.id = %s AND u.priv & 1",
        (variant, mode, base, mode, id),
    )
    if not info:
        raise HTTPException(404, "nie ma takiego gracza")
    rows = _query(
        "SELECT n.score_id, n.map_md5, n.pp, n.stars, n.aim, n.speed, n.acc_pp, n.fl, n.reading, "
        "b.pp AS old_pp, s.mods, s.acc, s.max_combo, s.nmiss, s.grade, s.play_time, "
        "m.id AS map_id, m.set_id, m.artist, m.title, m.version "
        "FROM pplab_scores n "
        "LEFT JOIN pplab_scores b ON b.variant = %s AND b.score_id = n.score_id "
        "JOIN scores s ON s.id = n.score_id "
        "JOIN maps m ON m.md5 = n.map_md5 "
        "WHERE n.variant = %s AND n.mode = %s AND n.user_id = %s "
        "ORDER BY n.pp DESC",
        (base, variant, mode, id),
    )
    seen, top = set(), []
    for r in rows:
        if r["map_md5"] in seen:
            continue
        seen.add(r["map_md5"])
        top.append(r)
        if len(top) == 100:
            break
    i = info[0]
    return {
        "player": {
            "id": i["id"], "name": i["name"], "country": i["country"],
            "new_pp": _f(i["new_pp"]), "old_pp": _f(i["old_pp"]),
            "new_rank": i["new_rank"], "old_rank": i["old_rank"], "plays": i["plays"],
        },
        "scores": [
            {
                "id": r["score_id"], "map_id": r["map_id"], "set_id": r["set_id"],
                "artist": r["artist"], "title": r["title"], "version": r["version"],
                "mods": r["mods"], "acc": _f(r["acc"]), "combo": r["max_combo"], "misses": r["nmiss"],
                "grade": r["grade"], "played": r["play_time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "stars": _f(r["stars"]), "new_pp": _f(r["pp"]), "old_pp": _f(r["old_pp"]),
                "weight": round(0.95**n, 4),
                "parts": {
                    "aim": _f(r["aim"]), "speed": _f(r["speed"]), "acc": _f(r["acc_pp"]),
                    "fl": _f(r["fl"]), "reading": _f(r["reading"]),
                },
            }
            for n, r in enumerate(top)
        ],
    }


@router.get("/scores")
def scores(
    variant: str,
    mode: int = Query(0, ge=0, le=3),
    order: str = Query("gain", pattern="^(gain|loss|top)$"),
    limit: int = Query(50, ge=1, le=100),
):
    """Wyniki (obecne najlepsze wyniki graczy na mapach), które najbardziej zyskują, tracą albo dają najwięcej pp."""
    _variant(variant, mode)
    sort = {
        "gain": "(n.pp - b.pp) DESC",
        "loss": "(n.pp - b.pp) ASC",
        "top": "n.pp DESC",
    }[order]
    rows = _query(
        "SELECT n.score_id, n.user_id, u.name, u.country, n.pp, b.pp AS old_pp, n.stars, s.mods, s.acc, "
        "s.nmiss, m.id AS map_id, m.set_id, m.artist, m.title, m.version "
        "FROM pplab_scores n "
        "JOIN pplab_scores b ON b.variant = %s AND b.score_id = n.score_id "
        "JOIN scores s ON s.id = n.score_id AND s.status = 2 "
        "JOIN users u ON u.id = n.user_id AND u.priv & 1 "
        "JOIN maps m ON m.md5 = n.map_md5 "
        f"WHERE n.variant = %s AND n.mode = %s ORDER BY {sort} LIMIT %s",
        (config.BASE_VARIANT, variant, mode, limit),
    )
    return {
        "scores": [
            {
                "id": r["score_id"], "user_id": r["user_id"], "name": r["name"], "country": r["country"],
                "map_id": r["map_id"], "set_id": r["set_id"], "artist": r["artist"], "title": r["title"],
                "version": r["version"], "mods": r["mods"], "acc": _f(r["acc"]), "misses": r["nmiss"],
                "stars": _f(r["stars"]), "new_pp": _f(r["pp"]), "old_pp": _f(r["old_pp"]),
            }
            for r in rows
        ]
    }


# mody, które zmieniają gwiazdki w osu!std: EZ, HR, DT, HT, NC, FL
_STAR_MODS = 2 | 16 | 64 | 256 | 512 | 1024
_stars_cache: dict[tuple[int, int], float] = {}


@router.get("/stars")
def stars(items: str = Query(..., max_length=2000)):
    """Gwiazdki osu!std wzorem serwera dla par map_id:mods, np. ?items=129891:64,75:0."""
    wanted: list[tuple[int, int]] = []
    asked: dict[str, tuple[int, int]] = {}
    for part in items.split(","):
        try:
            map_id, mods = (int(x) for x in part.split(":", 1))
        except ValueError:
            raise HTTPException(400, "zły format, oczekiwane map_id:mods")
        key = (map_id, mods & _STAR_MODS)
        asked[f"{map_id}:{mods}"] = key
        if key not in wanted:
            wanted.append(key)
    if len(wanted) > 100:
        raise HTTPException(400, "najwyżej 100 map naraz")
    missing = [k for k in wanted if k not in _stars_cache]
    scores = []
    for i, (map_id, mods) in enumerate(missing):
        path = config.MAPS_DIR / f"{map_id}.osu"
        if path.exists():
            scores.append({"id": i, "map": str(path), "mode": 0, "mods": mods})
    if scores:
        proc = subprocess.run(
            [config.CALC_BIN], input=json.dumps({"variant": config.BASE_VARIANT, "scores": scores}),
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode == 0:
            for res in json.loads(proc.stdout):
                if not res["error"]:
                    _stars_cache[missing[res["id"]]] = round(res["stars"], 2)
    if len(_stars_cache) > 20000:
        _stars_cache.clear()
    return {name: _stars_cache[key] for name, key in asked.items() if key in _stars_cache}


from .calculator import router as calc_router  # noqa: E402

app.include_router(router, prefix="/hypo/api")
app.include_router(router, prefix="/pp-lab/api")
app.include_router(calc_router, prefix="/hypo/api")
app.include_router(calc_router, prefix="/pp-lab/api")
