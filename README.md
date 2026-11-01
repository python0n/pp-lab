# pp-lab

Następca PP Era Hypo. Przelicza wyniki serwera taksiegra innymi wzorami pp
i udostępnia wyniki stronie `/reworks` w Shiinie.

- `calc/` – kalkulator w Ruście (`pp_lab`). Warianty: `tsg` (dokładnie wzór serwera,
  akatsuki-pp), `osu_2026_07` (rosu-pp pp-update), `osu_2025_10` (rosu-pp 4.0)
  i stare ery osu!std z rosu-pp-older. `pp_lab --variants` wypisuje listę.
- `pplab/recalc.py` – przeliczenie do tabel `pplab_runs`, `pplab_scores`, `pplab_players`
  w bazie bancho (tworzone automatycznie). pp gracza liczone jak w bancho:
  najlepszy wynik na mapę, ważenie 0.95^n, bonus 416.6667 * (1 - 0.9994^n).
- `pplab/api.py` – API tylko do odczytu pod `/hypo/api/...` i `/pp-lab/api/...`.
- `variants.json` – nazwy i opisy wariantów (PL/EN) pokazywane na stronie.

## Nowy wariant (np. propozycja reworku)

1. Dodać zależność i gałąź `match` w `calc/src/main.rs` (oraz wpis w `VARIANTS`).
2. Dodać opis w `variants.json` (`group`: `server`, `osu`, `proposal` albo `era`).
3. `cargo build --release`, potem `python -m pplab.recalc --variant <id>`.

## Komendy

    venv/bin/python -m pplab.recalc --default       # wzór serwera + osu!
    venv/bin/python -m pplab.recalc --all           # wszystko, łącznie ze starymi erami
    venv/bin/python -m pplab.recalc --variant osu_2019 --mode 0
