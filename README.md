# pp-lab

pp calculator and pp rework lab for osu! private servers running
[bancho.py](https://github.com/osuAkatsuki/bancho.py) (or a fork of it).

- **Calculator** (works on its own, no server or database needed): pp of any map by ID or link,
  with mods, for an accuracy or for hit counts (100s, 50s, misses) and combo. Shows the result in
  several formulas next to each other, plus SS/99/98/97/95% and SS-with-mods tables. Comes with a
  web page and a JSON API.
- **Reworks** (needs the server's database): recalculates the server's scores with other pp formulas
  (current osu!, older osu! versions, proposals) and gives player rankings and top plays for each one.

Used on [taksiegra](https://osu.taksiegra.ovh/pp). Polish notes: [README.pl.md](README.pl.md).

## Formulas

| id | what it is |
| --- | --- |
| `tsg` | akatsuki-pp, the formula bancho.py uses by default (osu! autumn 2022 with a later miss fix) |
| `osu_2026_07` | current osu! formula (rosu-pp, pp-update branch) |
| `osu_2025_10` | osu! October 2025 - July 2026 (rosu-pp 4.0) |
| `osu_2025_03` ... `osu_2014_may` | older osu!standard versions (rosu-pp-older, reworks only) |

Names and descriptions shown on the pages are in `variants.json`. The calculator uses the first three.

## Requirements

- Rust (stable) to build the calculator binary
- Python 3.11+
- MySQL/MariaDB with bancho.py's database, only for the reworks

## Running

    cd calc && cargo build --release && cd ..
    python -m venv venv && venv/bin/pip install -r requirements.txt
    cp .env.example .env        # edit it
    venv/bin/uvicorn pplab.api:app --host 127.0.0.1 --port 8766

Then open http://127.0.0.1:8766/pp-lab/. For the calculator alone set `DB_NAME=` (empty) in `.env`.

Reworks: `venv/bin/python -m pplab.recalc --default` fills the `pplab_*` tables (once a night is
enough, see `pp-lab-recalc.timer`). `pp-lab.service` runs the API with systemd.

## Settings (`.env`)

| setting | default | meaning |
| --- | --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME` | | bancho.py's database; empty `DB_NAME` = calculator only |
| `MAPS_DIR` | | folder with `<map id>.osu` files (bancho.py: `.data/osu`) |
| `MAPS_CACHE_DIR` | `cache/osu` | maps the calculator downloaded from osu.ppy.sh |
| `MAPS_CACHE_MAX_FILES` | `5000` | oldest downloaded maps are removed above this |
| `RATE_LIMIT_IP_HEADER` | `X-Real-IP` | header with the client address set by your proxy, empty = no proxy |
| `CALC_RATE_PER_MINUTE` | `40` | calculator requests per minute from one address |
| `CALC_CONCURRENCY` | `2` | calculations running at the same time |
| `SITE_NAME`, `SITE_LOGO` | `pp-lab` | name and logo URL in the page header |
| `THEME_CSS` | | your own CSS file loaded after the default one (see Customizing) |
| `COVER_URL` | osu! covers | cover image address, `{set_id}` is replaced; empty = no cover |
| `BASE_VARIANT` | `tsg` | the formula other ones are compared with |

## API

    GET /pp-lab/api/calc?map=129891&mods=HDDT&acc=98.5
    GET /pp-lab/api/calc?map=https://osu.ppy.sh/b/129891&n100=12&n50=0&miss=1&combo=1200&mode=0
    GET /pp-lab/api/calc/variants

`mods` is acronyms (`HDDT`) or the number. Without `combo` a full combo is calculated. `mode`
converts osu!standard maps to other modes. Reworks: `/pp-lab/api/variants`, `/players`, `/player`,
`/scores`, `/stars` (see `pplab/api.py`).

## Customizing

You are free to change everything: the page, its look, the texts and the code (MIT licence).

- **Colours, corners, fonts:** the page uses CSS variables (`--pl-accent`, `--pl-bg`, `--pl-radius`,
  ...) defined at the top of `pplab/web/app.css`. Put your values in your own file, for example by
  copying `themes/example.css`, and set `THEME_CSS=themes/my-theme.css`. Your file is loaded after the
  default one, so you can keep pulling updates of pp-lab without conflicts.
- **Name and logo:** `SITE_NAME` and `SITE_LOGO` in `.env`.
- **Languages:** the texts are in `TEXT` at the top of `pplab/web/app.js` (English and Polish);
  copy a block and add an `<option>` in `pplab/web/index.html`.
- **The page itself:** `pplab/web/index.html`, `app.css`, `app.js` are plain files, no build step.
- **Own formula:** add a crate and a `match` arm in `calc/src/main.rs` (and an entry in `VARIANTS`),
  a description in `variants.json`, rebuild, then `python -m pplab.recalc --variant <id>`.

## Testing

    venv/bin/pip install pytest httpx
    venv/bin/python -m pytest -q tests

The tests generate a small map, so they need neither a database nor internet. They check the
calculator (accuracy, mods, hit counts, links, converts), wrong input, the page, its security headers
and the rate limit.

## Security notes

- The calculator only downloads `https://osu.ppy.sh/osu/<number>`, never an address given by a user,
  and keeps at most `MAPS_CACHE_MAX_FILES` files.
- Requests are limited per address and the number of calculations at the same time is limited.
  Put pp-lab behind a proxy that overwrites the header from `RATE_LIMIT_IP_HEADER`
  (nginx: `proxy_set_header X-Real-IP $remote_addr;`), otherwise clients could send any address.
- The page sends a strict Content-Security-Policy (scripts and styles only from pp-lab itself) and
  escapes everything that comes from map files.
- The API only reads from the database. Bind it to 127.0.0.1 and expose only the paths you need.

## Credits

- [rosu-pp](https://github.com/MaxOhn/rosu-pp) and [rosu-pp-older](https://github.com/MaxOhn/rosu-pp-older) by MaxOhn
- [akatsuki-pp-rs](https://github.com/osuAkatsuki/akatsuki-pp-rs) by the osu!Akatsuki team

## Licence

MIT, see [LICENSE](LICENSE).
