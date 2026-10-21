"""Filename rules. The model suggests words; this module decides what a filename is allowed to be."""
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

# Names a person never chose on purpose. Anything else is left alone unless SLOTH_RENAME_ALL=1.
GENERIC_PATTERNS = [
    r"screen ?shot.*",
    r"cleanshot.*",
    r"screenshot_\d.*",
    r"whatsapp image.*",
    r"photo \d{4}-\d\d-\d\d.*",
    r"(img|pxl|dsc|dscn|dcim|mvimg|pict)[_ -]?\d.*",
    r"(image|img|photo|picture|pic|scan|scanned document|document|doc|file|download|"
    r"attachment|untitled|unnamed|export|print|receipt|invoice|statement|ticket)"
    r"[ _-]?\d*",
    r"scan[ _-]?\d{4}.*",
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",  # uuid
    r"[0-9a-f]{16,}",  # hash
    r"[\d _.-]{6,}",  # timestamps and other digit soup
]
_GENERIC = re.compile(r"^(?:%s)$" % "|".join(GENERIC_PATTERNS), re.IGNORECASE)
_COPY_SUFFIX = re.compile(r"\s*(\(\d+\)|copy( \d+)?|-\d)$", re.IGNORECASE)

FILLER = {"a", "an", "the", "of", "image", "picture", "photo", "file", "showing", "shows"}
NEVER = {"screenshot", "screenshots", "jpg", "png", "pdf"}  # says nothing the extension doesn't
MAX_SLUG = 60

# Matches the dates macOS, Android and WhatsApp put in throwaway names.
_NAME_DATE = re.compile(r"(20\d\d)[-_.]?(\d\d)[-_.]?(\d\d)")


def is_generic(filename: str) -> bool:
    stem = Path(filename).stem.strip()
    stem = _COPY_SUFFIX.sub("", stem)
    return bool(_GENERIC.match(stem))


def scrub(text: str) -> str:
    """Drop anything that should never end up in a filename, whatever the model says.

    Filenames show up in Spotlight, cloud sync logs, email attachments and shared screens,
    so account numbers, card numbers, phone numbers and emails stay out of them.
    """
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"\b(?:\d[ -]?){5,}\b", " ", text)  # 5+ digits, with or without separators
    return text


def slugify(text: str, scrub_numbers: bool = True) -> str:
    if scrub_numbers:
        text = scrub(text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in NEVER]
    while words and words[0] in FILLER:
        words.pop(0)
    slug = ""
    for w in words:
        nxt = f"{slug}-{w}" if slug else w
        if len(nxt) > MAX_SLUG:
            break
        slug = nxt
    return slug


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        d = datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return d if 1990 <= d.year <= date.today().year + 1 else None


_MONTH = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"


def is_full_date(text: str) -> bool:
    """True only for a printed day, month and year: 'October 2, 2026', '2 Oct 2026', '10/12/2026', '2026-09-28'.

    'Thu, Oct 29' (no year) and 'Q3 2026' (no day) are not, so the model can't fill in the gaps.
    """
    t = text.lower()
    return bool(
        re.search(r"\b\d{1,2}[/.-]\d{1,2}[/.-](\d{4}|\d{2})\b|\b(19|20)\d\d-\d\d-\d\d\b", t)
        or re.search(_MONTH + r"\s+\d{1,2}(st|nd|rd|th)?,?\s+(19|20)\d\d\b", t)
        or re.search(r"\b\d{1,2}\s+" + _MONTH + r",?\s+(19|20)\d\d\b", t)
    )


def date_from_name(filename: str) -> date | None:
    m = _NAME_DATE.search(filename)
    return parse_date(f"{m[1]}-{m[2]}-{m[3]}") if m else None


def strip_dates(text: str) -> str:
    """The date already leads the filename, so 'invoice October 2, 2026' doesn't need to say it again."""
    text = re.sub(r"\b" + _MONTH + r"\s+\d{1,2}(st|nd|rd|th)?(,?\s+(19|20)\d\d)?\b", " ", text, flags=re.I)
    text = re.sub(r"\b\d{1,2}[/.-]\d{1,2}[/.-](\d{4}|\d{2})\b|\b(19|20)\d\d-\d\d-\d\d\b", " ", text)
    return text


def build_filename(title: str, ext: str, when: date | None) -> str:
    """'Stripe invoice, Acme Corp' + '.PDF' + 2026-10-02 -> '2026-10-02-stripe-invoice-acme-corp.pdf'."""
    slug = slugify(strip_dates(title)) or "untitled"
    prefix = f"{when.isoformat()}-" if when else ""
    return f"{prefix}{slug}{ext.lower()}"


def unique_path(folder: Path, filename: str, ignore: Path | None = None) -> Path:
    """Never overwrite: add -2, -3, ... until the name is free."""
    candidate = folder / filename
    stem, ext = Path(filename).stem, Path(filename).suffix
    n = 2
    while candidate.exists() and candidate != ignore:
        candidate = folder / f"{stem}-{n}{ext}"
        n += 1
    return candidate
