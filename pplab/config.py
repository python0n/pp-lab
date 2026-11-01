"""Settings from the .env file next to the project (or from environment variables)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()

DB = dict(
    host=os.environ.get("DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USER", "bancho"),
    password=os.environ.get("DB_PASS", ""),
    database=os.environ.get("DB_NAME", "banchopy"),
)
CALC_BIN = os.environ.get("CALC_BIN", str(ROOT / "calc" / "target" / "release" / "pp_lab"))
MAPS_DIR = Path(os.environ.get("MAPS_DIR", str(ROOT / "maps")))
# .osu files of maps the server doesn't have, downloaded once by the calculator
MAPS_CACHE_DIR = Path(os.environ.get("MAPS_CACHE_DIR", str(ROOT / "cache" / "osu")))
# wariant, z którym porównujemy (wzór, którego dziś używa serwer)
BASE_VARIANT = os.environ.get("BASE_VARIANT", "tsg")
# ile wyników na jedno wywołanie kalkulatora
CHUNK = int(os.environ.get("CHUNK", "20000"))

# ---- calculator and its web page ----
# no database: only the calculator works (reworks need bancho's database)
DB_ENABLED = bool(os.environ.get("DB_NAME", "banchopy").strip())
# header with the client's address set by your reverse proxy (nginx: proxy_set_header X-Real-IP $remote_addr);
# empty = the address of the connection itself (use this when nothing sits in front of pp-lab)
RATE_LIMIT_IP_HEADER = os.environ.get("RATE_LIMIT_IP_HEADER", "X-Real-IP").strip()
CALC_RATE_PER_MINUTE = int(os.environ.get("CALC_RATE_PER_MINUTE", "40"))
# calculations running at the same time (each one starts the calculator once per formula)
CALC_CONCURRENCY = int(os.environ.get("CALC_CONCURRENCY", "2"))
# downloaded .osu files kept in MAPS_CACHE_DIR (oldest removed first)
MAPS_CACHE_MAX_FILES = int(os.environ.get("MAPS_CACHE_MAX_FILES", "5000"))
# web page: name in the header, optional logo URL and an extra CSS file loaded after the default one
SITE_NAME = os.environ.get("SITE_NAME", "pp-lab")
SITE_LOGO = os.environ.get("SITE_LOGO", "")
THEME_CSS = os.environ.get("THEME_CSS", "")
# beatmap covers; {set_id} is replaced, empty = no cover
COVER_URL = os.environ.get("COVER_URL", "https://assets.ppy.sh/beatmaps/{set_id}/covers/cover.jpg")
