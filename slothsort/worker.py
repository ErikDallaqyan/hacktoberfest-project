"""Watch folders and rename new files, one at a time. Slow and steady."""
import logging
import os
import queue
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import config, journal, namer, naming

log = logging.getLogger("slothsort")

PARTIAL_EXTS = {".crdownload", ".part", ".download", ".tmp", ".partial"}


def wants(path: Path, rename_all: bool = False) -> bool:
    """Cheap checks before a file is worth a model call."""
    name = path.name
    if name.startswith(".") or path.suffix.lower() in PARTIAL_EXTS:
        return False
    if path.suffix.lower() not in config.SUPPORTED_EXTS:
        return False
    return rename_all or naming.is_generic(name)


def wait_until_settled(path: Path, timeout: float = 30) -> bool:
    """A file still being downloaded or written keeps growing. Wait for its size to hold still."""
    deadline = time.time() + timeout
    last = -1
    while time.time() < deadline:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        if size == last and size > 0:
            return True
        last = size
        time.sleep(1)
    return False


def plan_name(path: Path, s: namer.Suggestion, sort_into_folders: bool) -> Path:
    when = naming.parse_date(s.document_date) or naming.date_from_name(path.name)
    if when is None:
        when = time.localtime(path.stat().st_mtime)
        when = naming.parse_date(time.strftime("%Y-%m-%d", when))
    folder = path.parent / s.category if sort_into_folders else path.parent
    filename = naming.build_filename(s.title, path.suffix, when)
    return naming.unique_path(folder, filename, ignore=path)


@dataclass
class Worker:
    sort_into_folders: bool = config.SORT_INTO_FOLDERS
    rename_all: bool = config.RENAME_ALL
    paused: bool = False
    current: str | None = None
    q: "queue.Queue[Path]" = field(default_factory=queue.Queue)
    _queued: set = field(default_factory=set)
    _thread: threading.Thread | None = None

    def submit(self, path: Path) -> bool:
        path = Path(path)
        if path in self._queued or not wants(path, self.rename_all):
            return False
        self._queued.add(path)
        self.q.put(path)
        return True

    def queued(self) -> int:
        return len(self._queued)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True, name="slothsort-worker")
        self._thread.start()

    def _loop(self) -> None:
        while True:
            path = self.q.get()
            while self.paused:
                time.sleep(1)
            self.current = path.name
            try:
                self.process(path)
            except Exception:  # one bad file must not stop the sloth
                log.exception("failed on %s", path)
            finally:
                self._queued.discard(path)
                self.current = None

    def process(self, path: Path) -> dict | None:
        if not path.exists() or journal.should_skip(path):
            return None
        if not wait_until_settled(path):
            return None
        try:
            s = namer.suggest(path)
            target = plan_name(path, s, self.sort_into_folders)
        except Exception as e:
            row_id = journal.add(old_path=str(path), status="error", error=str(e)[:500])
            return journal.get(row_id)

        # Write the journal entry before touching the file, so undo always knows where it went.
        row_id = journal.add(
            old_path=str(path), new_path=str(target), what=s.what, category=s.category,
            secrets=int(s.contains_secrets), seconds=s.seconds, model=s.model, status="renamed",
        )
        target.parent.mkdir(exist_ok=True)
        os.rename(path, target)
        log.info("%s -> %s (%.1fs)", path.name, target.name, s.seconds)
        return journal.get(row_id)


def undo(row_id: int) -> dict:
    row = journal.get(row_id)
    if not row or row["status"] not in ("renamed", "edited"):
        raise ValueError("Nothing to undo for this file.")
    new, old = Path(row["new_path"]), Path(row["old_path"])
    if not new.exists():
        raise ValueError(f"{new.name} is no longer where Sloth Sort put it.")
    if old.exists():
        raise ValueError(f"Something else is already called {old.name}.")
    os.rename(new, old)
    journal.update(row_id, status="undone")
    _remove_if_empty(new.parent, old.parent)
    return journal.get(row_id)


def rename_to(row_id: int, name: str) -> dict:
    row = journal.get(row_id)
    if not row or row["status"] not in ("renamed", "edited"):
        raise ValueError("This file can't be renamed from here.")
    current = Path(row["new_path"])
    if not current.exists():
        raise ValueError(f"{current.name} is no longer where Sloth Sort put it.")
    # A name you typed yourself is kept as typed (digits included); only the model's words get scrubbed.
    typed = Path(name).stem if Path(name).suffix.lower() == current.suffix.lower() else name
    slug = naming.slugify(typed, scrub_numbers=False)
    if not slug:
        raise ValueError("That name has no letters or numbers in it.")
    target = naming.unique_path(current.parent, slug + current.suffix.lower(), ignore=current)
    os.rename(current, target)
    journal.update(row_id, new_path=str(target), status="edited")
    return journal.get(row_id)


def _current_path(row: dict) -> Path:
    return Path(row["old_path"] if row["status"] == "undone" else row["new_path"])


def delete(row_id: int) -> dict:
    """Move the file into Sloth Sort's trash. Nothing is erased, so Restore can always bring it back."""
    row = journal.get(row_id)
    if not row or row["status"] not in ("renamed", "edited", "undone"):
        raise ValueError("This file can't be deleted from here.")
    current = _current_path(row)
    if not current.exists():
        raise ValueError(f"{current.name} is no longer where Sloth Sort left it.")
    trash = config.DB_PATH.parent / "trash"
    trash.mkdir(parents=True, exist_ok=True)
    target = trash / f"{row_id}-{current.name}"
    shutil.move(current, target)  # the trash may be on another disk (a Docker volume), so not os.rename
    journal.update(row_id, status="deleted", prev_status=row["status"], trash_path=str(target))
    if row["status"] != "undone":
        _remove_if_empty(current.parent, Path(row["old_path"]).parent)
    return journal.get(row_id)


def restore(row_id: int) -> dict:
    row = journal.get(row_id)
    if not row or row["status"] != "deleted":
        raise ValueError("This file isn't in the trash.")
    trashed = Path(row["trash_path"])
    if not trashed.exists():
        raise ValueError("The trashed copy is gone, so this file can't be restored.")
    back = _current_path({**row, "status": row["prev_status"]})
    if back.exists():
        raise ValueError(f"Something else is already called {back.name}.")
    back.parent.mkdir(exist_ok=True)
    shutil.move(trashed, back)
    journal.update(row_id, status=row["prev_status"], trash_path="")
    return journal.get(row_id)


def _remove_if_empty(folder: Path, watched: Path) -> None:
    if folder != watched and folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()


def backlog(dirs: list[Path], rename_all: bool = False) -> list[Path]:
    """Files already sitting in the watched folders that still have throwaway names."""
    found = []
    for d in dirs:
        if d.is_dir():
            found += sorted(p for p in d.iterdir() if p.is_file() and wants(p, rename_all)
                            and not journal.should_skip(p))
    return found


class _Handler(FileSystemEventHandler):
    def __init__(self, worker: Worker):
        self.worker = worker

    def on_created(self, event):
        if not event.is_directory:
            self.worker.submit(Path(event.src_path))

    def on_moved(self, event):
        # macOS writes screenshots as a hidden temp file, then renames it into place.
        if not event.is_directory:
            self.worker.submit(Path(event.dest_path))


def watch(worker: Worker, dirs: list[Path]) -> Observer:
    observer = Observer()
    for d in dirs:
        if d.is_dir():
            observer.schedule(_Handler(worker), str(d), recursive=False)
    observer.start()
    return observer
