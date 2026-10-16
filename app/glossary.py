"""Per-restaurant dish glossaries.

A glossary is the restaurant's own knowledge about its dishes: how a name is
written on their menu, how they want it rendered for guests, and a one-line
explanation. The translator treats glossary entries as hard rules, and owner
corrections are written back here so the next menu gets them right.
"""
import json
import re
import unicodedata

from rapidfuzz import fuzz

from . import config

FUZZY_THRESHOLD = 88


def _slug(s: str) -> str:
    s = re.sub(r"[^\w]+", "-", s.lower(), flags=re.UNICODE).strip("-")
    return s or "glossary"


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFC", s).lower()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def _path(glossary_id: str):
    return config.GLOSSARY_DIR / f"{_slug(glossary_id)}.json"


def list_glossaries() -> list[dict]:
    out = []
    for p in sorted(config.GLOSSARY_DIR.glob("*.json")):
        g = json.loads(p.read_text())
        out.append({"id": p.stem, "name": g.get("name", p.stem), "entries": len(g.get("entries", []))})
    return out


def load(glossary_id: str) -> dict:
    p = _path(glossary_id)
    if not p.exists():
        return {"name": glossary_id, "entries": []}
    return json.loads(p.read_text())


def save(glossary_id: str, glossary: dict) -> None:
    _path(glossary_id).write_text(json.dumps(glossary, ensure_ascii=False, indent=2) + "\n")


def match(glossary: dict, text: str) -> list[dict]:
    """Return glossary entries whose source forms appear in `text`, best first."""
    hay = normalize(text)
    if not hay:
        return []
    scored = []
    for entry in glossary.get("entries", []):
        best = 0
        for form in entry.get("match", []):
            needle = normalize(form)
            if not needle:
                continue
            # Armenian and Russian inflect with suffixes (խորիզ-ով, лаваш-ом), so longer forms may be
            # followed by more letters; short ones (Խաշ vs Խաշլամա) must be whole words.
            tail = "" if len(needle) >= 4 else r"(?!\w)"
            if re.search(rf"(?<!\w){re.escape(needle)}{tail}", hay):
                score = 100 + len(needle)  # exact phrase: prefer the longest form
            elif len(needle) >= 4:
                score = _window_ratio(needle, hay)  # tolerate OCR typos, but word-aligned
            else:
                score = 0
            best = max(best, score)
        if best >= FUZZY_THRESHOLD:
            scored.append((best, entry))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored]


def _window_ratio(needle: str, hay: str) -> float:
    """Best fuzzy ratio of `needle` against same-length word windows of `hay`."""
    n = len(needle.split())
    words = hay.split()
    windows = (" ".join(words[i:i + n]) for i in range(max(1, len(words) - n + 1)))
    return max((fuzz.ratio(needle, w) for w in windows), default=0)


SNAP_THRESHOLD = 75


def snap_words(glossary: dict, text: str) -> tuple[str, list[tuple[str, str]]]:
    """Fix OCR letter swaps in a dish name by snapping words to near-identical glossary spellings.

    Returns the corrected text and the (was, now) pairs so the owner can see what changed.
    """
    forms = {}
    for entry in glossary.get("entries", []):
        for form in entry.get("match", []):
            if " " not in form and len(form) >= 4:
                forms[normalize(form)] = form
    def snap(word: str) -> str | None:
        key = normalize(word).replace(" ", "")
        if len(key) < 4 or key in forms:
            return None
        best = max(forms, key=lambda f: fuzz.ratio(key, f), default=None)
        if best and fuzz.ratio(key, best) >= SNAP_THRESHOLD and best[0] == key[0]:
            fixed = forms[best]
            return fixed if word[:1].isupper() else fixed.lower()
        return None

    words, out, changes, i = text.split(), [], [], 0
    while i < len(words):
        # OCR sometimes splits a word in two ("Բ ատուրմո"); try the joined pair first.
        if i + 1 < len(words) and normalize(words[i + 1]) not in forms:
            pair = words[i] + words[i + 1]
            fixed = snap(pair)
            if fixed and len(words[i]) <= 2:
                changes.append((f"{words[i]} {words[i + 1]}", fixed))
                out.append(fixed)
                i += 2
                continue
        fixed = snap(words[i])
        if fixed:
            changes.append((words[i], fixed))
        out.append(fixed or words[i])
        i += 1
    return " ".join(out), changes


def upsert_correction(glossary_id: str, source_name: str, lang: str, name: str,
                      description: str, transliteration: str | None = None) -> dict:
    """Store an owner's correction for one dish in one target language."""
    g = load(glossary_id)
    entries = g.setdefault("entries", [])
    key = normalize(source_name)
    entry = next((e for e in entries if key in {normalize(m) for m in e.get("match", [])}), None)
    if entry is None:
        entry = {"id": _slug(transliteration or source_name), "match": [source_name], "translations": {}}
        entries.append(entry)
    if transliteration:
        entry["transliteration"] = transliteration
    entry.setdefault("translations", {})[lang] = {"name": name, "description": description, "owner": True}
    save(glossary_id, g)
    return entry


def owner_override(entries: list[dict], dish_name: str, lang: str) -> dict | None:
    """The owner's saved translation for exactly this dish, if there is one. It beats the model."""
    key = normalize(dish_name)
    for e in entries:
        t = e.get("translations", {}).get(lang)
        if t and t.get("owner") and key in {normalize(m) for m in e.get("match", [])}:
            return t
    return None


def prompt_block(entries: list[dict], lang: str, with_about: bool = True) -> str:
    """Render matched entries as rules for the translation prompt."""
    lines = []
    for e in entries:
        t = e.get("translations", {}).get(lang) or e.get("translations", {}).get("en")
        if not t:
            continue
        pivot = "" if lang in e.get("translations", {}) else " (English reference; translate it)"
        translit = f' | transliteration: "{e["transliteration"]}"' if e.get("transliteration") else ""
        note = f" | note: {e['notes']}" if e.get("notes") else ""
        about = f' | about: "{t.get("description", "")}"' if with_about and t.get("description") else ""
        lines.append(f'- "{e["match"][0]}" -> name: "{t["name"]}"{translit}{about}{pivot}{note}')
    return "\n".join(lines)
