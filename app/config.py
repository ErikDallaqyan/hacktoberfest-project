import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("HYUR_DATA_DIR", ROOT / "data"))
GLOSSARY_DIR = DATA_DIR / "glossaries"
MENU_DIR = DATA_DIR / "menus"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
VISION_MODEL = os.getenv("HYUR_VISION_MODEL", "gemma3:12b")
TEXT_MODEL = os.getenv("HYUR_TEXT_MODEL", VISION_MODEL)
OLLAMA_TIMEOUT = float(os.getenv("HYUR_OLLAMA_TIMEOUT", "900"))

LANGUAGES = {
    "hy": "Armenian",
    "ru": "Russian",
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "fa": "Persian (Farsi)",
    "ar": "Arabic",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "ka": "Georgian",
}

for d in (GLOSSARY_DIR, MENU_DIR):
    d.mkdir(parents=True, exist_ok=True)
