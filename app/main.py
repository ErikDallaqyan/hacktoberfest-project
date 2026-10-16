import io
import json
import re
import time
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from pydantic import BaseModel

from . import config, glossary, ocr, pipeline
from .ollama_client import OllamaError, list_models

MAX_IMAGE_SIDE = 1600

app = FastAPI(title="Hyur — local menu translator")


@app.exception_handler(OllamaError)
async def ollama_error(_, exc: OllamaError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/api/meta")
def meta():
    return {
        "languages": config.LANGUAGES,
        "models": list_models(),
        "vision_model": config.VISION_MODEL,
        "text_model": config.TEXT_MODEL,
        "glossaries": glossary.list_glossaries(),
        "ocr_languages": [k for k in config.LANGUAGES if ocr.available(k)],
    }


def _prepare_image(raw: bytes) -> bytes:
    """Fix phone-photo rotation and shrink so the vision model stays fast."""
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    except Exception as e:
        raise HTTPException(400, f"Not an image: {e}")
    img = img.convert("RGB")
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@app.post("/api/extract")
async def extract(
    source_lang: str = Form("hy"),
    model: str = Form(""),
    reader: str = Form("auto"),
    glossary_id: str = Form("armenian-classics"),
    text: str = Form(""),
    file: UploadFile | None = File(None),
):
    if file is not None and file.filename:
        image = _prepare_image(await file.read())
        menu, stats = pipeline.extract_from_image(image, source_lang, model or None, reader, glossary_id)
    elif text.strip():
        menu, stats = pipeline.extract_from_text(text, source_lang, model or None, glossary_id)
    else:
        raise HTTPException(400, "Upload a menu photo or paste the menu text.")
    menu_id = uuid.uuid4().hex[:10]
    record = {"id": menu_id, "created": time.time(), "source_lang": source_lang, "menu": menu}
    (config.MENU_DIR / f"{menu_id}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    return {"menu_id": menu_id, "menu": menu, "stats": stats}


class TranslateRequest(BaseModel):
    menu: dict
    source_lang: str = "hy"
    target_lang: str = "en"
    glossary_id: str = "armenian-classics"
    model: str = ""


@app.post("/api/translate")
def translate(req: TranslateRequest):
    if not req.menu.get("sections"):
        raise HTTPException(400, "Menu has no sections.")
    result, stats = pipeline.translate(req.menu, req.source_lang, req.target_lang, req.glossary_id,
                                       req.model or None)
    return {"translation": result, "stats": stats}


@app.get("/api/glossaries")
def glossaries():
    return glossary.list_glossaries()


@app.get("/api/glossaries/{glossary_id}")
def get_glossary(glossary_id: str):
    return glossary.load(glossary_id)


class NewGlossary(BaseModel):
    name: str
    copy_from: str = "armenian-classics"


@app.post("/api/glossaries")
def create_glossary(req: NewGlossary):
    gid = re.sub(r"[^\w]+", "-", req.name.lower(), flags=re.UNICODE).strip("-")
    if not gid:
        raise HTTPException(400, "Give the glossary a name.")
    if any(g["id"] == gid for g in glossary.list_glossaries()):
        raise HTTPException(409, "A glossary with that name already exists.")
    base = glossary.load(req.copy_from) if req.copy_from else {"entries": []}
    glossary.save(gid, {"name": req.name, "copied_from": req.copy_from, "entries": base.get("entries", [])})
    return {"id": gid}


class Correction(BaseModel):
    source_name: str
    lang: str
    name: str
    description: str = ""
    transliteration: str | None = None


@app.post("/api/glossaries/{glossary_id}/corrections")
def add_correction(glossary_id: str, c: Correction):
    return glossary.upsert_correction(glossary_id, c.source_name, c.lang, c.name, c.description,
                                      c.transliteration)


@app.get("/api/sample")
def sample_menu():
    return FileResponse(config.ROOT / "samples" / "sample_menu_hy.png")


@app.get("/api/health")
def health():
    return {"ok": True}


# Local development: serve the frontend from the same process. In Docker the frontend is its own
# nginx image and the backend image doesn't contain it, so this mount is skipped there.
if config.FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
