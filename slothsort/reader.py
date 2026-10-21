"""Turn a file into what the model can look at: a downsized image, plus text for PDFs."""
import io
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps

from . import config

MAX_SIDE = 896  # Gemma 3 sees images at 896px anyway; sending more just costs time
PDF_TEXT_CHARS = 3000


@dataclass
class FileView:
    images: list[bytes] = field(default_factory=list)
    text: str = ""
    pages: int = 0


def _jpeg(img: Image.Image, max_side: int) -> bytes:
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.convert("RGBA").split()[-1])
        img = bg
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _pdf_first_page(path: Path, max_side: int) -> tuple[Image.Image, str, int]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        pages = len(pdf)
        text = ""
        for i in range(min(pages, 2)):
            text += pdf[i].get_textpage().get_text_range() + "\n"
        page = pdf[0]
        scale = max_side / max(page.get_size())
        img = page.render(scale=scale).to_pil()
        return img, text.strip(), pages
    finally:
        pdf.close()


def read(path: Path) -> FileView:
    ext = path.suffix.lower()
    if ext in config.PDF_EXTS:
        img, text, pages = _pdf_first_page(path, MAX_SIDE)
        return FileView(images=[_jpeg(img, MAX_SIDE)], text=text[:PDF_TEXT_CHARS], pages=pages)
    with Image.open(path) as img:
        img.seek(0)  # first frame of a GIF
        return FileView(images=[_jpeg(img.copy(), MAX_SIDE)])


def thumbnail(path: Path, size: int = 480) -> bytes:
    if path.suffix.lower() in config.PDF_EXTS:
        img, _, _ = _pdf_first_page(path, size)
        return _jpeg(img, size)
    with Image.open(path) as img:
        img.seek(0)
        return _jpeg(img.copy(), size)
