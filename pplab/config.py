"""Ustawienia z pliku .env obok projektu (albo ze zmiennych środowiskowych)."""
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
