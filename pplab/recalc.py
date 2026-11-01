"""Przeliczenie wyników serwera wybranym wzorem.

    python -m pplab.recalc --variant osu_2026_07          # wszystkie tryby, które wariant obsługuje
    python -m pplab.recalc --variant osu_2026_07 --mode 0
    python -m pplab.recalc --all                           # każdy wariant z variants.json
    python -m pplab.recalc --default                       # wzór serwera + warianty osu! (bez starych er)

Liczone są wszystkie zaliczone wyniki (status 1, 2, 3) graczy bez restrykcji
na mapach rankingowych i zatwierdzonych, w trybach zwykłych (0-3).
pp gracza: najlepszy wynik na każdej mapie, ważenie 0.95^n po wszystkich mapach
i bonus 416.6667 * (1 - 0.9994^liczba_map), dokładnie jak w bancho.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

from . import config, db
from .variants import load_variants, variant_modes

SCORES_SQL = """
SELECT s.id, s.userid, s.map_md5, s.mode, s.mods, s.n300, s.n100, s.n50,
       s.ngeki, s.nkatu, s.nmiss, s.max_combo, s.score, m.id AS map_id
FROM scores s
JOIN maps m ON m.md5 = s.map_md5
JOIN users u ON u.id = s.userid
WHERE s.mode = %s AND s.status IN (1, 2, 3) AND m.status IN (2, 3) AND u.priv & 1
"""


def weighted_total(pps: list[float]) -> float:
    pps = sorted(pps, reverse=True)
    weighted = sum(pp * 0.95**i for i, pp in enumerate(pps))
    bonus = 416.6667 * (1 - 0.9994 ** len(pps))
    return weighted + bonus


def run_calc(variant: str, scores: list[dict]) -> list[dict]:
    payload = json.dumps({"variant": variant, "scores": scores})
    proc = subprocess.run([config.CALC_BIN], input=payload, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"kalkulator zakończył się błędem: {proc.stderr.strip()[:500]}")
    return json.loads(proc.stdout)


def recalc_mode(conn, variant: str, mode: int) -> None:
    started = time.time()
    with conn.cursor() as cur:
        cur.execute(
            "REPLACE INTO pplab_runs (variant, mode, started_at, finished_at, scores, errors) "
            "VALUES (%s, %s, %s, NULL, 0, 0)",
            (variant, mode, datetime.now(timezone.utc).replace(tzinfo=None)),
        )
        cur.execute(SCORES_SQL, (mode,))
        rows = cur.fetchall()

    inputs, meta, missing = [], {}, 0
    for r in rows:
        path = config.MAPS_DIR / f"{r['map_id']}.osu"
        if not path.exists():
            missing += 1
            continue
        inputs.append({
            "id": r["id"], "map": str(path), "mode": mode, "mods": r["mods"],
            "n300": r["n300"], "n100": r["n100"], "n50": r["n50"],
            "ngeki": r["ngeki"], "nkatu": r["nkatu"], "nmiss": r["nmiss"],
            "combo": r["max_combo"], "score": max(int(r["score"]), 0),
        })
        meta[r["id"]] = (r["userid"], r["map_md5"])

    results, errors, samples = [], 0, []
    for i in range(0, len(inputs), config.CHUNK):
        for res in run_calc(variant, inputs[i : i + config.CHUNK]):
            if res["error"]:
                errors += 1
                if len(samples) < 5:
                    samples.append(f"wynik {res['id']}: {res['error']}")
                continue
            uid, md5 = meta[res["id"]]
            results.append((
                variant, res["id"], uid, md5, mode, res["pp"], res["stars"],
                res["aim"], res["speed"], res["acc"], res["fl"], res["reading"],
            ))

    # pp graczy: najlepszy wynik na mapę, ważenie jak w bancho
    best: dict[int, dict[str, float]] = {}
    for row in results:
        uid, md5, pp = row[2], row[3], row[5]
        maps = best.setdefault(uid, {})
        if pp > maps.get(md5, -1.0):
            maps[md5] = pp
    players = [(uid, weighted_total(list(m.values())), len(m)) for uid, m in best.items()]
    players.sort(key=lambda p: p[1], reverse=True)

    with conn.cursor() as cur:
        conn.begin()
        try:
            cur.execute("DELETE FROM pplab_scores WHERE variant = %s AND mode = %s", (variant, mode))
            cur.execute("DELETE FROM pplab_players WHERE variant = %s AND mode = %s", (variant, mode))
            for i in range(0, len(results), 5000):
                cur.executemany(
                    "INSERT INTO pplab_scores (variant, score_id, user_id, map_md5, mode, pp, stars, "
                    "aim, speed, acc_pp, fl, reading) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    results[i : i + 5000],
                )
            cur.executemany(
                "INSERT INTO pplab_players (variant, mode, user_id, pp, plays, `rank`) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                [(variant, mode, uid, round(pp, 3), n, rank) for rank, (uid, pp, n) in enumerate(players, 1)],
            )
            cur.execute(
                "UPDATE pplab_runs SET finished_at = %s, scores = %s, errors = %s "
                "WHERE variant = %s AND mode = %s",
                (datetime.now(timezone.utc).replace(tzinfo=None), len(results), errors + missing, variant, mode),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    took = time.time() - started
    print(
        f"{variant} tryb {mode}: {len(results)} wyników, {len(players)} graczy, "
        f"bez pliku mapy {missing}, błędy {errors}, {took:.1f} s"
    )
    for s in samples:
        print("  ", s)


def main() -> None:
    ap = argparse.ArgumentParser(description="Przeliczenie wyników wzorem pp")
    ap.add_argument("--variant")
    ap.add_argument("--mode", type=int, choices=[0, 1, 2, 3])
    ap.add_argument("--all", action="store_true", help="wszystkie warianty")
    ap.add_argument("--default", action="store_true", help="wzór serwera, warianty osu! i propozycje")
    args = ap.parse_args()

    variants = load_variants()
    if args.all:
        chosen = [v["id"] for v in variants]
    elif args.default:
        chosen = [v["id"] for v in variants if v["group"] in ("server", "osu", "proposal")]
    elif args.variant:
        chosen = [args.variant]
    else:
        ap.error("podaj --variant, --default albo --all")

    modes_by_variant = variant_modes()
    conn = db.connect()
    db.ensure_schema(conn)
    for variant in chosen:
        if variant not in modes_by_variant:
            sys.exit(f"nieznany wariant: {variant}")
        modes = modes_by_variant[variant]
        if args.mode is not None:
            if args.mode not in modes:
                print(f"{variant}: tryb {args.mode} nieobsługiwany, pomijam")
                continue
            modes = [args.mode]
        for mode in modes:
            recalc_mode(conn, variant, mode)


if __name__ == "__main__":
    main()
