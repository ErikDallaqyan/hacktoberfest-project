from datetime import date

import pytest

from slothsort import naming


@pytest.mark.parametrize("name", [
    "Screenshot 2026-10-21 at 3.14.07 PM.png",
    "Screen Shot 2020-01-02 at 10.00.00.png",
    "CleanShot 2026-10-21 at 15.14.07@2x.png",
    "IMG_4821.jpg",
    "IMG_4821 (1).jpg",
    "PXL_20261021_141502123.jpg",
    "image (3).png",
    "image.png",
    "download.pdf",
    "download (2).pdf",
    "document (1).pdf",
    "Scan 2026-10-12.pdf",
    "Untitled.png",
    "WhatsApp Image 2026-10-21 at 14.15.02.jpeg",
    "8f14e45fceea167a5a36dedd4bea2543.png",
    "3f2a9c1e-7b4d-4e8a-9c1f-2b3d4e5f6a7b.pdf",
    "20261021_141502.jpg",
    "invoice.pdf",
])
def test_throwaway_names_are_generic(name):
    assert naming.is_generic(name)


@pytest.mark.parametrize("name", [
    "taxes 2025 notes.pdf",
    "resume-jordan-rivers.pdf",
    "wedding seating chart.png",
    "Acme Cloud invoice October.pdf",
    "IMG of the grand canyon.jpg",
])
def test_names_people_chose_are_left_alone(name):
    assert not naming.is_generic(name)


def test_build_filename():
    assert naming.build_filename("Stripe invoice, Acme Corp", ".PDF", date(2026, 10, 2)) == \
        "2026-10-02-stripe-invoice-acme-corp.pdf"
    assert naming.build_filename("", ".png", None) == "untitled.png"


def test_dates_are_not_repeated_in_the_title():
    d = date(2026, 10, 2)
    assert naming.build_filename("Acme invoice October 2, 2026", ".pdf", d) == "2026-10-02-acme-invoice.pdf"
    assert naming.build_filename("receipt 10/12/2026 corner hardware", ".pdf", d) == "2026-10-02-receipt-corner-hardware.pdf"
    assert naming.build_filename("signups Q3 2026", ".png", d) == "2026-10-02-signups-q3-2026.png"


def test_slug_drops_screenshot_and_leading_filler():
    assert naming.slugify("A screenshot of the Skyline Air boarding pass") == "skyline-air-boarding-pass"
    assert naming.slugify("meme about desktop screenshots") == "meme-about-desktop"


def test_slug_is_ascii_and_capped():
    assert naming.slugify("Café crème brûlée receipt") == "cafe-creme-brulee-receipt"
    long = naming.slugify("word " * 40)
    assert len(long) <= naming.MAX_SLUG and not long.endswith("-")


@pytest.mark.parametrize("title", [
    "chase statement account 7730 2219 5541",
    "card 4111-1111-1111-1111 receipt",
    "email from jordan@example.com",
    "call 510 555 0199 back",
])
def test_numbers_and_emails_never_reach_the_filename(title):
    slug = naming.slugify(title)
    assert not any(ch.isdigit() for ch in slug.replace("2026", "")), slug
    assert "example" not in slug


def test_short_numbers_and_years_survive():
    assert naming.slugify("flight SK 418 october 2026") == "flight-sk-418-october-2026"


@pytest.mark.parametrize("text,expected", [
    ("October 2, 2026", True), ("Oct 24, 2026", True), ("2 Oct 2026", True), ("10/12/2026", True),
    ("2026-09-28", True), ("10/12/26", True), ("Date: September 28th, 2026", True),
    ("Thu, Oct 29", False), ("", False), ("Oct 24", False), ("Q3 2026", False), ("October 2026", False),
])
def test_is_full_date(text, expected):
    assert naming.is_full_date(text) is expected


def test_dates():
    assert naming.date_from_name("Screenshot 2026-10-14 at 9.41.22 AM.png") == date(2026, 10, 14)
    assert naming.date_from_name("PXL_20261021_141502123.jpg") == date(2026, 10, 21)
    assert naming.date_from_name("download.pdf") is None
    assert naming.parse_date("1850-01-01") is None
    assert naming.parse_date("not a date") is None


def test_unique_path_never_overwrites(tmp_path):
    (tmp_path / "a.png").write_bytes(b"1")
    (tmp_path / "a-2.png").write_bytes(b"2")
    assert naming.unique_path(tmp_path, "a.png").name == "a-3.png"
    assert naming.unique_path(tmp_path, "a.png", ignore=tmp_path / "a.png").name == "a.png"
    assert naming.unique_path(tmp_path, "b.png").name == "b.png"
