import json
import subprocess
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def load_variants() -> list[dict]:
    """Variant descriptions (variants.json) with the modes reported by the calculator."""
    meta = json.loads((config.ROOT / "variants.json").read_text(encoding="utf-8"))
    modes = variant_modes()
    return [dict(v, modes=modes.get(v["id"], [])) for v in meta if v["id"] in modes]


@lru_cache(maxsize=1)
def variant_modes() -> dict[str, list[int]]:
    out = subprocess.run([config.CALC_BIN, "--variants"], capture_output=True, text=True, check=True)
    return {v["id"]: v["modes"] for v in json.loads(out.stdout)}
