import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"

# Where the rename journal lives. Never inside a watched folder.
STATE_DIR = Path(os.getenv("SLOTH_STATE_DIR", Path.home() / ".slothsort"))
DB_PATH = STATE_DIR / "journal.db"

# Comma-separated folders to watch. Defaults to where clutter actually lands on a Mac.
WATCH_DIRS = [
    Path(p).expanduser()
    for p in os.getenv("SLOTH_WATCH", "~/Desktop,~/Downloads").split(",")
    if p.strip()
]

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# 4B is light enough to run in the background on a 16 GB laptop. gemma3:12b names a bit better, slower.
MODEL = os.getenv("SLOTH_MODEL", "gemma3:4b")
OLLAMA_TIMEOUT = float(os.getenv("SLOTH_OLLAMA_TIMEOUT", "300"))

# 1 = also move files into category subfolders (receipts/, tickets/, ...). Off by default.
SORT_INTO_FOLDERS = os.getenv("SLOTH_SORT_FOLDERS", "0") == "1"
# 1 = rename every file, not just ones with throwaway names like "Screenshot ... .png".
RENAME_ALL = os.getenv("SLOTH_RENAME_ALL", "0") == "1"

HOST = "127.0.0.1"  # the review page is for you only, never the network
PORT = int(os.getenv("SLOTH_PORT", "8765"))

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".heic", ".webp", ".gif", ".tiff", ".bmp"}
PDF_EXTS = {".pdf"}
SUPPORTED_EXTS = IMAGE_EXTS | PDF_EXTS

STATE_DIR.mkdir(parents=True, exist_ok=True)
