"""Ask the local model what a file is and what it should be called."""
from dataclasses import dataclass
from pathlib import Path

from . import naming, ollama_client, reader

CATEGORIES = {
    "money": "receipts, invoices, bills, bank or payroll statements, tax forms",
    "travel": "boarding passes, tickets, hotel or rental bookings, maps, itineraries",
    "work": "documents, slides, spreadsheets, charts, meeting notes, contracts",
    "code": "code, terminal output, error messages, developer tools",
    "chats": "text messages, chat threads, emails, social media posts",
    "shopping": "products, carts, order confirmations, price comparisons",
    "photos": "camera photos of people, places, pets, food or things",
    "memes": "jokes, memes, funny screenshots",
    "other": "anything else",
}

SYSTEM = """You name files for someone who is too lazy to do it themselves.
You look at one file (a screenshot, photo or PDF) and describe it the way a tidy person would name it.

Rules for "title":
- 3 to 7 words, most specific first: who or what it is from, what it is, and what makes it different from similar files.
  Good: "stripe invoice acme corp october", "united boarding pass sfo to jfk", "python keyerror in billing script",
  "zillow listing 2br apartment oakland", "group chat dinner plans friday".
- Use names of companies, products, places and apps you can read. Do not use the word "screenshot".
- For an error, include the error's name. Leave dates out of the title; the date is added separately.
- Never include account numbers, card numbers, order or tracking numbers, phone numbers, emails, passwords or keys.

"what" is one full sentence, like "A Skyline Air boarding pass from SFO to JFK for October 24."

"document_date" is the date printed on the file as its own date (invoice date, statement date, travel date),
as YYYY-MM-DD, and "date_as_printed" is that date copied exactly as it appears on the file.
Delivery dates, due dates, quarters and dates without a day or year don't count. Leave both empty if there is no such date.

"contains_secrets" is true only if a password, API key, private key, full card number or Social Security number is visible.
The last 4 digits of a card or account are not a secret."""

SCHEMA = {
    "type": "object",
    "properties": {
        "what": {"type": "string", "description": "One full sentence a friend would say about the file."},
        "title": {"type": "string"},
        "category": {"type": "string", "enum": list(CATEGORIES)},
        "document_date": {"type": "string"},
        "date_as_printed": {"type": "string"},
        "contains_secrets": {"type": "boolean"},
    },
    "required": ["what", "title", "category", "document_date", "date_as_printed", "contains_secrets"],
}


@dataclass
class Suggestion:
    what: str
    title: str
    category: str
    document_date: str
    contains_secrets: bool
    seconds: float
    model: str


def suggest(path: Path, model: str | None = None) -> Suggestion:
    view = reader.read(path)
    cats = "\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items())
    prompt = f"Categories:\n{cats}\n\nThe file is a {'PDF' if view.pages else 'image'}"
    if view.pages:
        prompt += f" with {view.pages} page(s). The first page is attached."
        if view.text:
            prompt += f" Its text begins:\n\"\"\"\n{view.text}\n\"\"\""
    else:
        prompt += "; it is attached."
    prompt += "\n\nDescribe it and name it."

    out, stats = ollama_client.chat_json(prompt, SCHEMA, images=view.images, system=SYSTEM, model=model)
    return Suggestion(
        what=str(out.get("what", "")).strip(),
        title=str(out.get("title", "")).strip(),
        category=out.get("category") if out.get("category") in CATEGORIES else "other",
        # Never trust a year the model didn't actually read: "Thu, Oct 29" must not become 2023-10-29.
        document_date=(str(out.get("document_date", "")).strip()
                       if naming.is_full_date(str(out.get("date_as_printed", ""))) else ""),
        contains_secrets=bool(out.get("contains_secrets")),
        seconds=stats["seconds"],
        model=stats["model"],
    )
