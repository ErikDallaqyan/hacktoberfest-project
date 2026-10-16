"""Menu photo -> structured menu -> glossary-grounded translation."""
import tempfile
import time
from pathlib import Path

from . import config, glossary, ocr
from .ollama_client import chat_json

DIETARY = ["vegetarian", "contains-pork", "contains-nuts", "contains-dairy", "spicy"]

# Word stems that mean a dish is not vegetarian / contains pork, across the menu languages we see most.
# Dietary tags are checked against these because a wrong "vegetarian" label is worse than none.
MEAT_STEMS = ("միս", "մսով", "մսի", "խոզ", "գառ", "տավար", "հավ", "ձուկ", "ձկ", "իշխան", "լյարդ",
              "мяс", "свин", "говя", "баран", "куриц", "рыб", "форел", "печен",
              "meat", "beef", "pork", "lamb", "chicken", "fish", "trout", "liver", "sausage", "offal")
PORK_STEMS = ("խոզ", "свин", "pork")


CURRENCY_CODES = {"դր": "AMD", "դրամ": "AMD", "֏": "AMD", "руб": "RUB", "₽": "RUB", "лари": "GEL", "₾": "GEL"}


def guest_currency(printed: str) -> str:
    """Show prices in a currency code a tourist can read (դր. -> AMD)."""
    key = printed.strip().rstrip(".").lower()
    return CURRENCY_CODES.get(key, printed)


def check_dietary(tags: list[str], *texts: str) -> list[str]:
    hay = " ".join(texts).lower()
    tags = [t for t in dict.fromkeys(tags) if t in DIETARY]
    if any(stem in hay for stem in MEAT_STEMS):
        tags = [t for t in tags if t != "vegetarian"]
    # Pork is decided by the text alone: models both miss it and invent it.
    tags = [t for t in tags if t != "contains-pork"]
    if any(stem in hay for stem in PORK_STEMS):
        tags.append("contains-pork")
    return tags


EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "currency": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "price": {"type": "string"},
                            },
                            "required": ["name", "description", "price"],
                        },
                    },
                },
                "required": ["name", "items"],
            },
        },
    },
    "required": ["title", "currency", "sections"],
}

TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "dietary": {"type": "array", "items": {"type": "string", "enum": DIETARY}},
                            },
                            "required": ["id", "name", "description", "dietary"],
                        },
                    },
                },
                "required": ["name", "items"],
            },
        },
    },
    "required": ["title", "sections"],
}


def extract_from_image(image: bytes, source_lang: str, model: str | None = None, reader: str = "auto",
                       glossary_id: str | None = None) -> tuple[dict, dict]:
    """Read a menu photo. reader: "ocr" (Tesseract + LLM structuring), "vision" (LLM reads the image), "auto"."""
    use_ocr = reader == "ocr" or (reader == "auto" and ocr.available(source_lang))
    if use_ocr:
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            f.write(image)
            f.flush()
            t0 = time.perf_counter()
            text = ocr.read(Path(f.name), source_lang)
            ocr_seconds = round(time.perf_counter() - t0, 1)
        menu, stats = extract_from_text(text, source_lang, model, glossary_id, from_ocr=True)
        stats.update(reader="tesseract+llm", ocr_seconds=ocr_seconds, seconds=round(stats["seconds"] + ocr_seconds, 1))
        return menu, stats

    lang = config.LANGUAGES.get(source_lang, source_lang)
    prompt = (
        f"This is a photo of a restaurant menu written in {lang}. "
        f"Transcribe it exactly, in the original {lang} script. Do not translate or transliterate.\n"
        "Group dishes under the section headings shown on the menu. For each dish give its name, "
        "the description line under it (empty string if none) and the price printed on the same line as the name. "
        "Each dish appears exactly once. If there are no headings, use one section named after the menu title."
    )
    data, stats = chat_json(model or config.VISION_MODEL, prompt, EXTRACT_SCHEMA, images=[image])
    stats["reader"] = "vision"
    return _clean(data, glossary_id), stats


def extract_from_text(text: str, source_lang: str, model: str | None = None, glossary_id: str | None = None,
                      from_ocr: bool = False) -> tuple[dict, dict]:
    lang = config.LANGUAGES.get(source_lang, source_lang)
    ocr_note = ("The text comes from OCR: a dish line usually ends with its price, and the line below it is its "
                "description. Drop stray OCR junk, but otherwise keep the words as they are.\n") if from_ocr else ""
    prompt = (
        f"Below is the text of a restaurant menu written in {lang}. Structure it into sections and dishes. "
        "Keep every name and description exactly as written; do not translate. Prices: digits only.\n"
        f"{ocr_note}\nMENU TEXT:\n{text}"
    )
    data, stats = chat_json(model or config.TEXT_MODEL, prompt, EXTRACT_SCHEMA)
    stats["reader"] = "text"
    return _clean(data, glossary_id), stats


def _clean(menu: dict, glossary_id: str | None) -> dict:
    """Merge duplicate dishes, snap OCR typos in dish names to the glossary, and assign ids."""
    g = glossary.load(glossary_id) if glossary_id else None
    for section in menu.get("sections", []):
        merged: dict[str, dict] = {}
        for item in section.get("items", []):
            key = glossary.normalize(item["name"])
            if key in merged:
                prev = merged[key]
                prev["price"] = prev["price"] or item.get("price", "")
                prev["description"] = prev["description"] or item.get("description", "")
                continue
            merged[key] = item
        section["items"] = [i for i in merged.values() if i["name"].strip()]
        if g:
            for item in section["items"]:
                fixed, changes = glossary.snap_words(g, item["name"])
                if changes:
                    item["ocr_name"] = item["name"]
                    item["name"] = fixed
    menu["sections"] = [s for s in menu.get("sections", []) if s.get("items")]
    return _with_ids(menu)


def _with_ids(menu: dict) -> dict:
    n = 0
    for section in menu.get("sections", []):
        for item in section.get("items", []):
            n += 1
            item["id"] = f"d{n}"
    return menu


def _indent(block: str) -> str:
    return "\n".join("      " + line for line in block.splitlines())


def translate(menu: dict, source_lang: str, target_lang: str, glossary_id: str,
              model: str | None = None, dietary_guard: bool = True) -> tuple[dict, dict]:
    g = glossary.load(glossary_id)
    src = config.LANGUAGES.get(source_lang, source_lang)
    tgt = config.LANGUAGES.get(target_lang, target_lang)

    # Glossary hits per dish, split into "this dish is X" (name) and "mentions X" (description),
    # and written right under the dish so small models apply the right rule to the right line.
    hits: dict[str, list[str]] = {}
    entries: dict[str, list[dict]] = {}
    lines = []
    for section in menu["sections"]:
        lines.append(f"## {section['name']}")
        for item in section["items"]:
            name_hits = glossary.match(g, item["name"])
            desc_hits = [e for e in glossary.match(g, item.get("description", "")) if e not in name_hits]
            hits[item["id"]] = [e["id"] for e in name_hits + desc_hits]
            entries[item["id"]] = name_hits + desc_hits
            desc = f" — {item['description']}" if item.get("description") else ""
            lines.append(f"[{item['id']}] {item['name']}{desc}")
            if name_hits:
                block = glossary.prompt_block(name_hits, target_lang, with_about=not item.get("description"))
                lines.append("    dish name glossary:\n" + _indent(block))
            if desc_hits:
                lines.append("    ingredient glossary:\n" + _indent(glossary.prompt_block(desc_hits, target_lang, with_about=False)))
    menu_text = "\n".join(lines)

    prompt = (
        f"Translate this {src} restaurant menu into {tgt} for foreign guests. Write only in {tgt}.\n\n"
        "Rules:\n"
        f"1. Every dish keeps its id. Translate every section name and the title into {tgt}.\n"
        "2. Dish name: if a 'dish name glossary' entry is given, start from that glossary name (translate it into "
        f"{tgt} if it is an English reference) and add only qualifiers that are literally in the {src} dish name "
        "(e.g. the meat used). Otherwise transliterate traditional names and add a short plain explanation in "
        "parentheses. Keep names short.\n"
        f"3. Description: translate the menu's own description faithfully into {tgt}, word for word in meaning. "
        "Use 'ingredient glossary' entries to render the ingredient words. Do not add ingredients, sides or "
        "adjectives that are not in the source line. Only if the menu line has no description, write one short "
        "sentence from the glossary 'about' text.\n"
        "4. dietary: only tags that are certain from the source line or glossary, from [vegetarian, "
        "contains-pork, contains-nuts, contains-dairy, spicy]. A dish with any meat or fish is never vegetarian. "
        "Empty list if unsure.\n"
        "5. Follow every glossary note.\n\n"
        f"MENU TITLE: {menu.get('title', '')}\n\nMENU:\n{menu_text}"
    )
    data, stats = chat_json(model or config.TEXT_MODEL, prompt, TRANSLATE_SCHEMA)

    # Merge back onto the source structure by id so prices and order are never touched by the model.
    by_id = {it["id"]: it for s in data.get("sections", []) for it in s.get("items", [])}
    sec_names = [s.get("name", "") for s in data.get("sections", [])]
    out_sections = []
    for i, section in enumerate(menu["sections"]):
        items = []
        for item in section["items"]:
            t = by_id.get(item["id"], {})
            owner = glossary.owner_override(entries[item["id"]], item["name"], target_lang)
            if owner:
                t = {**t, "name": owner["name"], "description": owner.get("description") or t.get("description", "")}
            if not t.get("name", "").strip():
                # Never print a blank dish: fall back to the original and flag it for the owner.
                t = {**t, "name": item["name"], "needs_review": True}
            items.append({
                "id": item["id"],
                "source_name": item["name"],
                "source_description": item.get("description", ""),
                "price": item.get("price", ""),
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "dietary": check_dietary(
                    t.get("dietary", []), item["name"], item.get("description", ""), t.get("name", ""),
                    t.get("description", ""),
                    *(e.get("translations", {}).get("en", {}).get("description", "") for e in entries[item["id"]]),
                ) if dietary_guard else t.get("dietary", []),
                "glossary_hits": hits[item["id"]],
                "needs_review": t.get("needs_review", False),
            })
        out_sections.append({
            "source_name": section["name"],
            "name": sec_names[i] if i < len(sec_names) else section["name"],
            "items": items,
        })
    result = {
        "title": data.get("title", menu.get("title", "")),
        "source_title": menu.get("title", ""),
        "currency": guest_currency(menu.get("currency", "")),
        "target_lang": target_lang,
        "sections": out_sections,
    }
    return result, stats
