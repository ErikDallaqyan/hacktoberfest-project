"""Local review page: see what got renamed, undo or fix anything with one click."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, config, journal, ollama_client, reader, worker

state: dict = {}


def _pretty(folder: Path) -> str:
    """~/Desktop for folders under home; just the folder name otherwise."""
    try:
        return "~/" + str(folder.relative_to(Path.home()))
    except ValueError:
        return folder.name


@asynccontextmanager
async def lifespan(app: FastAPI):
    w = worker.Worker()
    w.start()
    state["worker"] = w
    state["observer"] = worker.watch(w, config.WATCH_DIRS)
    yield
    state["observer"].stop()


app = FastAPI(title="Sloth Sort", version=__version__, lifespan=lifespan)


def _row(r: dict) -> dict:
    old, new = Path(r["old_path"]), Path(r["new_path"]) if r["new_path"] else None
    return {
        "id": r["id"],
        "created_at": r["created_at"],
        "folder": _pretty(old.parent),
        "old_name": old.name,
        "new_name": new.name if new else None,
        "subfolder": new.parent.name if new and new.parent != old.parent else None,
        "what": r["what"],
        "category": r["category"],
        "secrets": bool(r["secrets"]),
        "seconds": r["seconds"],
        "model": r["model"],
        "status": r["status"],
        "error": r["error"],
    }


@app.get("/api/status")
def status():
    w: worker.Worker = state["worker"]
    models = ollama_client.list_models()
    return {
        "model": config.MODEL,
        "model_ready": config.MODEL in models,
        "ollama_up": bool(models),
        "watching": [_pretty(d) for d in config.WATCH_DIRS if d.is_dir()],
        "paused": w.paused,
        "current": w.current,
        "queued": w.queued(),
        "sort_into_folders": w.sort_into_folders,
        "backlog": len(worker.backlog(config.WATCH_DIRS, w.rename_all)),
        "totals": journal.totals(),
    }


@app.get("/api/renames")
def renames(limit: int = 200):
    return [_row(r) for r in journal.recent(limit)]


class Name(BaseModel):
    name: str


def _act(fn, *args):
    try:
        return _row(fn(*args))
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post("/api/renames/{row_id}/undo")
def undo(row_id: int):
    return _act(worker.undo, row_id)


@app.post("/api/renames/{row_id}/rename")
def rename(row_id: int, body: Name):
    return _act(worker.rename_to, row_id, body.name)


class Toggle(BaseModel):
    on: bool


@app.post("/api/pause")
def pause(body: Toggle):
    state["worker"].paused = body.on
    return {"paused": body.on}


@app.post("/api/folders")
def folders(body: Toggle):
    state["worker"].sort_into_folders = body.on
    return {"sort_into_folders": body.on}


@app.post("/api/backlog")
def tidy_backlog():
    w: worker.Worker = state["worker"]
    files = worker.backlog(config.WATCH_DIRS, w.rename_all)
    return {"queued": sum(w.submit(p) for p in files)}


@app.get("/api/renames/{row_id}/thumb")
def thumb(row_id: int):
    # Only files in the journal can be previewed; the page can't ask for arbitrary paths.
    r = journal.get(row_id)
    if not r:
        raise HTTPException(404)
    for p in (r["new_path"], r["old_path"]):
        if p and Path(p).exists():
            try:
                return Response(reader.thumbnail(Path(p)), media_type="image/jpeg",
                                headers={"Cache-Control": "max-age=60"})
            except Exception:
                break
    raise HTTPException(404)


app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
