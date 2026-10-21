"""Rename, undo and edit end to end, with the model replaced by a stub."""
import pytest
from PIL import Image

from slothsort import config, journal, namer, worker


@pytest.fixture(autouse=True)
def fresh_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "journal.db")


@pytest.fixture
def stub_model(monkeypatch):
    def fake(path, model=None):
        return namer.Suggestion(what="A boarding pass.", title="Skyline Air boarding pass SFO to JFK",
                                category="travel", document_date="2026-10-24", contains_secrets=False,
                                seconds=1.0, model="stub")
    monkeypatch.setattr(namer, "suggest", fake)


@pytest.fixture
def desktop(tmp_path):
    d = tmp_path / "Desktop"
    d.mkdir()
    Image.new("RGB", (10, 10)).save(d / "Screenshot 2026-10-14 at 9.41.22 AM.png")
    (d / "taxes 2025 notes.pdf").write_bytes(b"%PDF-1.4")
    (d / "notes.txt").write_text("hi")
    return d


def test_backlog_only_picks_throwaway_images_and_pdfs(desktop):
    assert [p.name for p in worker.backlog([desktop])] == ["Screenshot 2026-10-14 at 9.41.22 AM.png"]


def test_rename_then_undo(desktop, stub_model):
    original = desktop / "Screenshot 2026-10-14 at 9.41.22 AM.png"
    row = worker.Worker(sort_into_folders=False).process(original)
    assert row["status"] == "renamed"
    renamed = desktop / "2026-10-24-skyline-air-boarding-pass-sfo-to-jfk.png"
    assert renamed.exists() and not original.exists()

    worker.undo(row["id"])
    assert original.exists() and not renamed.exists()
    # The watcher sees the file come back; it must not rename it again.
    assert journal.should_skip(original)
    assert worker.backlog([desktop]) == []


def test_sort_into_folders_and_undo_cleans_up(desktop, stub_model):
    row = worker.Worker(sort_into_folders=True).process(desktop / "Screenshot 2026-10-14 at 9.41.22 AM.png")
    assert (desktop / "travel" / "2026-10-24-skyline-air-boarding-pass-sfo-to-jfk.png").exists()
    worker.undo(row["id"])
    assert not (desktop / "travel").exists()


def test_never_overwrites_an_existing_file(desktop, stub_model):
    (desktop / "2026-10-24-skyline-air-boarding-pass-sfo-to-jfk.png").write_bytes(b"mine")
    worker.Worker().process(desktop / "Screenshot 2026-10-14 at 9.41.22 AM.png")
    assert (desktop / "2026-10-24-skyline-air-boarding-pass-sfo-to-jfk.png").read_bytes() == b"mine"
    assert (desktop / "2026-10-24-skyline-air-boarding-pass-sfo-to-jfk-2.png").exists()


def test_rename_to_custom_name(desktop, stub_model):
    row = worker.Worker().process(desktop / "Screenshot 2026-10-14 at 9.41.22 AM.png")
    row = worker.rename_to(row["id"], "NYC trip boarding pass.png")
    assert (desktop / "nyc-trip-boarding-pass.png").exists()
    assert row["status"] == "edited"
    row = worker.rename_to(row["id"], "2026-10-24 boarding pass gate B12")
    assert (desktop / "2026-10-24-boarding-pass-gate-b12.png").exists()
    worker.undo(row["id"])
    assert (desktop / "Screenshot 2026-10-14 at 9.41.22 AM.png").exists()


def test_model_failure_is_recorded_and_file_untouched(desktop, monkeypatch):
    def boom(path, model=None):
        raise RuntimeError("Ollama is not running")
    monkeypatch.setattr(namer, "suggest", boom)
    original = desktop / "Screenshot 2026-10-14 at 9.41.22 AM.png"
    row = worker.Worker().process(original)
    assert row["status"] == "error" and "Ollama" in row["error"]
    assert original.exists()


def test_partial_downloads_are_ignored(tmp_path):
    assert not worker.wants(tmp_path / "download.pdf.crdownload")
    assert not worker.wants(tmp_path / ".Screenshot 2026-10-14 at 9.41.22 AM.png")
    assert worker.wants(tmp_path / "download.pdf")
