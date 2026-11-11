# pp-lab

Kalkulator pp i laboratorium reworków pp dla prywatnych serwerów osu! działających na
[bancho.py](https://github.com/osuAkatsuki/bancho.py) (albo jego forku).

- **Kalkulator** (działa samodzielnie, bez serwera i bazy danych): pp dowolnej mapy po ID lub linku,
  z modami, dla podanej celności albo liczby trafień (100, 50, missy) i combo. Pokazuje wynik w kilku
  formułach obok siebie oraz tabele SS/99/98/97/95% i SS z różnymi modami. Ma stronę WWW i API JSON.
- **Reworki** (wymagają bazy danych serwera): przelicza wyniki z serwera innymi formułami pp
  (obecne osu!, starsze wersje osu!, propozycje) i pokazuje ranking graczy oraz najlepsze wyniki dla każdej z nich.

**Demo:** https://osu.taksiegra.ovh/pp-lab/ - strona z tego repozytorium bez zmian, do wypróbowania.
Właściwy kalkulator taksiegra, wbudowany w stronę serwera, jest pod https://osu.taksiegra.ovh/pp.
English version: [README.md](README.md).

## Formuły

| id | co to jest |
| --- | --- |
| `tsg` | akatsuki-pp, formuła domyślnie używana przez bancho.py (osu! z jesieni 2022 z późniejszą poprawką missów) |
| `osu_2026_07` | obecna formuła osu! (rosu-pp, gałąź pp-update) |
| `osu_2025_10` | osu! od października 2025 do lipca 2026 (rosu-pp 4.0) |
| `osu_2025_03` ... `osu_2014_may` | starsze wersje osu!standard (rosu-pp-older, tylko reworki) |

Nazwy i opisy widoczne na stronach są w `variants.json`. Kalkulator używa pierwszych trzech.

## Wymagania

- Rust (stable) do zbudowania programu liczącego
- Python 3.11+
- MySQL/MariaDB z bazą bancho.py, tylko do reworków

## Uruchomienie

    cd calc && cargo build --release && cd ..
    python -m venv venv && venv/bin/pip install -r requirements.txt
    cp .env.example .env        # uzupełnij
    venv/bin/uvicorn pplab.api:app --host 127.0.0.1 --port 8766

Potem otwórz http://127.0.0.1:8766/pp-lab/. Dla samego kalkulatora ustaw w `.env` puste `DB_NAME=`.

Reworki: `venv/bin/python -m pplab.recalc --default` wypełnia tabele `pplab_*` (wystarczy raz na noc,
zobacz `pp-lab-recalc.timer`). `pp-lab.service` uruchamia API przez systemd.

## Ustawienia (`.env`)

| ustawienie | domyślnie | znaczenie |
| --- | --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME` | | baza bancho.py; puste `DB_NAME` = tylko kalkulator |
| `MAPS_DIR` | | folder z plikami `<id mapy>.osu` (bancho.py: `.data/osu`) |
| `MAPS_CACHE_DIR` | `cache/osu` | mapy pobrane przez kalkulator z osu.ppy.sh |
| `MAPS_CACHE_MAX_FILES` | `5000` | powyżej tej liczby najstarsze pobrane mapy są usuwane |
| `RATE_LIMIT_IP_HEADER` | `X-Real-IP` | nagłówek z adresem klienta ustawiany przez proxy, puste = bez proxy |
| `CALC_RATE_PER_MINUTE` | `40` | zapytania do kalkulatora na minutę z jednego adresu |
| `CALC_CONCURRENCY` | `2` | ile obliczeń może trwać jednocześnie |
| `SITE_NAME`, `SITE_LOGO` | `pp-lab` | nazwa i adres logo w nagłówku strony |
| `THEME_CSS` | | własny plik CSS ładowany po domyślnym (zobacz Własny wygląd) |
| `COVER_URL` | okładki osu! | adres okładki, `{set_id}` jest podmieniane; puste = bez okładki |
| `BASE_VARIANT` | `tsg` | formuła, z którą porównywane są pozostałe |
| `API_EXTRA_PREFIX` | | API dostępne też pod tą ścieżką, np. starą, której używa jeszcze twoja strona |
| `RELAX_PP` | `false` | `true` = RX w kalkulatorze, pp za relax z akatsuki-pp (tyle, ile bancho.py daje za wyniki na RX) |

## API

    GET /pp-lab/api/calc?map=129891&mods=HDDT&acc=98.5
    GET /pp-lab/api/calc?map=https://osu.ppy.sh/b/129891&n100=12&n50=0&miss=1&combo=1200&mode=0
    GET /pp-lab/api/calc/variants

`mods` to skróty (`HDDT`) albo liczba. Bez `combo` liczony jest full combo. `mode` konwertuje mapy
osu!standard na inne tryby. Przy `RELAX_PP=true` `RX` w `mods` daje pp za relax (osu!standard, taiko
i catch); wersję dla relaksu ma tylko formuła `tsg`, więc odpowiedź zawiera wtedy tylko ją. Reworki: `/pp-lab/api/variants`, `/players`, `/player`, `/scores`,
`/stars` (zobacz `pplab/api.py`).

## Własny wygląd

Możesz dowolnie zmieniać wszystko: stronę, jej wygląd, teksty i kod (licencja MIT).

- **Kolory, zaokrąglenia, czcionki:** strona używa zmiennych CSS (`--pl-accent`, `--pl-bg`, `--pl-radius`,
  ...) zdefiniowanych na początku `pplab/web/app.css`. Wpisz swoje wartości we własnym pliku, np. kopiując
  `themes/example.css`, i ustaw `THEME_CSS=themes/moj-motyw.css`. Twój plik ładuje się po domyślnym,
  więc możesz dalej pobierać aktualizacje pp-lab bez konfliktów.
- **Nazwa i logo:** `SITE_NAME` i `SITE_LOGO` w `.env`.
- **Języki:** teksty są w `TEXT` na początku `pplab/web/app.js` (angielski i polski);
  skopiuj blok i dodaj `<option>` w `pplab/web/index.html`.
- **Sama strona:** `pplab/web/index.html`, `app.css`, `app.js` to zwykłe pliki, bez budowania.
- **Własna formuła:** dodaj crate i gałąź `match` w `calc/src/main.rs` (oraz wpis w `VARIANTS`),
  opis w `variants.json`, przebuduj, potem `python -m pplab.recalc --variant <id>`.

## Testy

    venv/bin/pip install pytest httpx
    venv/bin/python -m pytest -q tests

Testy generują małą mapę, więc nie potrzebują ani bazy danych, ani internetu. Sprawdzają kalkulator
(celność, mody, liczby trafień, linki, konwersje), błędne dane, stronę, jej nagłówki bezpieczeństwa
i limit zapytań.

## Bezpieczeństwo

- Kalkulator pobiera tylko `https://osu.ppy.sh/osu/<liczba>`, nigdy adresu podanego przez użytkownika,
  i trzyma najwyżej `MAPS_CACHE_MAX_FILES` plików.
- Zapytania są limitowane na adres, a liczba jednoczesnych obliczeń jest ograniczona.
  Postaw pp-lab za proxy, które nadpisuje nagłówek z `RATE_LIMIT_IP_HEADER`
  (nginx: `proxy_set_header X-Real-IP $remote_addr;`), inaczej klient mógłby podać dowolny adres.
- Strona wysyła ścisłą Content-Security-Policy (skrypty i style tylko z samego pp-lab) i escapuje
  wszystko, co pochodzi z plików map.
- API tylko czyta z bazy danych. Wystaw je na 127.0.0.1 i udostępniaj tylko potrzebne ścieżki.

## Podziękowania

- [rosu-pp](https://github.com/MaxOhn/rosu-pp) i [rosu-pp-older](https://github.com/MaxOhn/rosu-pp-older) od MaxOhn
- [akatsuki-pp-rs](https://github.com/osuAkatsuki/akatsuki-pp-rs) od zespołu osu!Akatsuki

## Licencja

MIT, zobacz [LICENSE](LICENSE).
