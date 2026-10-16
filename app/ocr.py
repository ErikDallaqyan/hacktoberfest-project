"""Tesseract OCR: a small, fast, open-source reader with real Armenian support."""
import shutil
import subprocess
from pathlib import Path

from . import config

TESS_CODES = {
    "hy": "hye", "ru": "rus", "en": "eng", "fr": "fra", "de": "deu", "es": "spa", "it": "ita",
    "fa": "fas", "ar": "ara", "zh": "chi_sim", "ja": "jpn", "ka": "kat",
}
LOCAL_TESSDATA = config.DATA_DIR / "tessdata"


def _tessdata_dir(code: str) -> Path | None:
    for d in (LOCAL_TESSDATA, Path("/opt/homebrew/share/tessdata"), Path("/usr/share/tesseract-ocr/5/tessdata"),
              Path("/usr/share/tessdata")):
        if (d / f"{code}.traineddata").exists():
            return d
    return None


def available(source_lang: str) -> bool:
    code = TESS_CODES.get(source_lang)
    return bool(shutil.which("tesseract") and code and _tessdata_dir(code))


def read(image_path: Path, source_lang: str) -> str:
    code = TESS_CODES[source_lang]
    proc = subprocess.run(
        ["tesseract", str(image_path), "-", "--tessdata-dir", str(_tessdata_dir(code)), "-l", code, "--psm", "4"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract failed: {proc.stderr[:300]}")
    return "\n".join(line for line in proc.stdout.splitlines() if line.strip())
