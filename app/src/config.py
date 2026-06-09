import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _read_key_from_notepad(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in text.splitlines():
        m = re.search(r"(sk-or-v1-[a-zA-Z0-9_-]+)", line)
        if m:
            return m.group(1).strip()
    return ""


_key = os.getenv("OPENROUTER_API_KEY", "").strip()
if not _key:
    _key = _read_key_from_notepad(BASE_DIR / "MI_OPENROUTER_KEY.txt")
OPENROUTER_API_KEY = (_key or "").strip()
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
SCHEMAS_DIR = BASE_DIR / "schemas"
SAMPLES_DIR = BASE_DIR / "samples"
RUNS_DIR = BASE_DIR / "runs"

# Modelo único expuesto al cliente. El ID queda centralizado para poder
# actualizarlo en un solo lugar si OpenRouter cambia la disponibilidad.
MODEL_PROFILES = {
    "Estándar": "google/gemini-3.1-flash-lite",
}
DEFAULT_MODEL_PROFILE = "Estándar"
DEFAULT_PRIMARY_MODEL = MODEL_PROFILES[DEFAULT_MODEL_PROFILE]

# Compatibilidad con la interfaz CLI local.
AVAILABLE_MODELS = list(MODEL_PROFILES.values())
