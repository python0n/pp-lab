# pp-lab

Następca PP Era Hypo. Przelicza wyniki serwera taksiegra innymi wzorami pp
i udostępnia wyniki stronie `/reworks` w Shiinie.

- `calc/` - kalkulator w Ruście (`pp_lab`). Warianty: `tsg` (dokładnie wzór serwera,
  akatsuki-pp), `osu_2026_07` (rosu-pp pp-update), `osu_2025_10` (rosu-pp 4.0)
  i stare ery osu!std z rosu-pp-older. `pp_lab --variants` wypisuje listę.
- `pplab/recalc.py` - przeliczenie do tabel `pplab_runs`, `pplab_scores`, `pplab_players`
  w bazie bancho (tworzone automatycznie). pp gracza liczone jak w bancho:
  najlepszy wynik na mapę, ważenie 0.95^n, bonus 416.6667 * (1 - 0.9994^n).
- `pplab/api.py` - API tylko do odczytu pod `/hypo/api/...` i `/pp-lab/api/...`.
- `pplab/calculator.py` - kalkulator pp pod `/pp-lab/api/calc` (strona `/pp` w Shiinie): dowolna mapa
  po ID, mody, celność albo liczba 100/50/missów, combo; wynik we wzorze serwera i wzorach osu!
  plus tabele SS/99/98/97/95% i SS z popularnymi modami. Mapy spoza serwera pobiera raz z osu.ppy.sh
  do `cache/osu`. Limit 40 zapytań na minutę z jednego IP.
- `variants.json` - nazwy i opisy wariantów (PL/EN) pokazywane na stronie.

## Nowy wariant (np. propozycja reworku)

1. Dodać zależność i gałąź `match` w `calc/src/main.rs` (oraz wpis w `VARIANTS`).
2. Dodać opis w `variants.json` (`group`: `server`, `osu`, `proposal` albo `era`).
3. `cargo build --release`, potem `python -m pplab.recalc --variant <id>`.

## Komendy

    venv/bin/python -m pplab.recalc --default       # wzór serwera + osu!
    venv/bin/python -m pplab.recalc --all           # wszystko, łącznie ze starymi erami
    venv/bin/python -m pplab.recalc --variant osu_2019 --mode 0

## Kalkulator

    GET /pp-lab/api/calc?map=129891&mods=HDDT&acc=98.5
    GET /pp-lab/api/calc?map=https://osu.ppy.sh/b/129891&n100=12&n50=0&miss=1&combo=1200&mode=0

`mods` to skróty (`HDDT`) albo liczba. Bez `combo` liczone jest pełne combo. Konwersje są możliwe
tylko z map osu!standard.
