---
title: "Hyur: a menu translator that knows what Tolma is (runs on a laptop, costs $0 per menu)"
published: false
tags: devchallenge, hf26challenge, ai, opensource
---

*This is a submission for the Hacktoberfest 2026 "Side Hustle" challenge.*

## What I built

**Hyur** (հյուր, Armenian for *guest*) turns a phone photo of a restaurant menu into a clean, printable
bilingual menu for tourists. It runs entirely on the restaurant's own laptop with open-weight models:
**Gemma 3 12B** through Ollama, plus **Tesseract** OCR.

**Who pays:** family restaurants and cafés in Yerevan. Tourism keeps growing, many menus are still
Armenian-only or run through a generic translator, and the owner pays a translator or a designer every time the
menu changes. Hyur is a one-time setup (or a small monthly fee for glossary packs and reprints), and after that
each menu costs nothing.

The insight that shaped the whole build: **the fix isn't a bigger model, it's the restaurant's own knowledge.**
Hyur keeps a *house glossary* of how each dish should be named and explained. The model has to follow it, and
every correction the owner makes is saved back to the glossary, so the menu gets better every time they use it.

🔗 **Live showcase:** <!-- TODO: https://<your-domain>.tech -->
💻 **Code (MIT):** https://github.com/ErikDallaqyan/hacktoberfest-project

## Demo

<!-- TODO: upload docs/img/*.png here -->

![Reading the menu and fixing OCR misreads](docs/img/01-review.jpg)
![Bilingual menu with glossary hits and dietary tags](docs/img/02-result.jpg)
![Correct a dish once, saved to the house glossary](docs/img/03-correct.jpg)

## How it works

1. **Read.** Tesseract, with its Armenian model, OCRs the photo in **0.3 s**. Gemma 3 then structures the text
   into sections, dishes, descriptions and prices.
2. **Fix.** OCR letter swaps in dish names snap to the glossary's spelling: *Մանքի → Մանթի*, *Գաքա → Գաթա*,
   and even a word OCR split in two, *Բ ատուրմո → Բաստուրմա*. The owner then reviews every line, with
   auto-fixes highlighted, before anything is translated.
3. **Ground.** Every dish is fuzzy-matched against the house glossary. Armenian is inflected (*խորիզ* →
   *խորիզ**ով***, "with khoriz"), so matching tolerates suffixes and typos but stays word-aligned, which keeps
   *pakhlava* from matching *lavash*. The matching rules go into the prompt **right under each dish**, split into
   "this dish is…" and "this ingredient is…".
4. **Translate.** Gemma 3 translates into any of 12 languages. Prices and dish order never pass through the
   model's output; translations are merged back by dish id.
5. **Guard.** Dietary tags are checked in code: a dish whose text mentions meat can never be "vegetarian", and
   "contains-pork" appears only when pork is actually mentioned.
6. **Learn.** *Correct → Save to house glossary* writes the fix back, per language.

## What I found (measured, not vibes)

I scored three local models on a sample 11-dish Armenian menu with `scripts/eval.py`:

| Model | Read: vision only | Read: Tesseract + model | Dish names right: generic → **Hyur** |
|---|---|---|---|
| Gemma 3 12B | 85.5% | **94%** | 7/11 → **11/11** |
| Qwen2.5-VL 7B | 44% | **94%** | 7/11 → **11/11** |
| Qwen2.5 7B (text only) | n/a | **94%** | 8/11 → **10/11** |

*Reading = character-level similarity of dish names to the printed menu. Names right = the English name keeps
the real dish name, for example "Khorovats … with Pork Rib Chops" instead of "Pork Kebab".*

What surprised me:

- **Two popular open vision models decided Armenian was Georgian.** Qwen2.5-VL and Qwen3-VL both returned a
  confident menu in Georgian script with every dish invented. Gemma 3 read the Armenian script, but imperfectly.
  A 6 MB Tesseract model beat all of them, so the final design uses each open component for what it's good at.
- **The glossary mattered more than the model.** Without it, Gemma 3 wrote "Pork Kebab", "Hashlama" and "Grape
  Leaf Dolma". With it, every model I tried got the dishes right. That's the case for a small, swappable model plus
  owner-curated knowledge.
- **Small models make confident dietary mistakes.** One run tagged meat-stuffed Tolma as *vegetarian*. Another
  tagged Basturma (beef) as *contains-pork*. That's why dietary tags are decided in code, not in the prompt.
- **Generic mode invents things.** Faced with an OCR-garbled coffee line, the no-glossary run described it as "a
  traditional Armenian herbal tea". Hyur's review step and blank-name fallback exist because of that.

## Why open innovation matters here

- **$0 per menu makes the business work.** Restaurants reprint menus whenever a price changes. With no per-call
  bill, "translate it again" is never a decision, and I can sell a flat price.
- **The glossary is the product, the model is a dropdown.** When a better open model ships, owners switch in
  the UI and keep every correction. No lock-in to anyone's pricing or deprecation schedule.
- **Offline and private.** A back-office laptop with patchy Wi-Fi is enough, and menus, prices and supplier
  notes never leave it.
- **I could see the failures and fix them.** Running everything locally let me test four models on the same
  menu in an afternoon, find the Georgian misread, and swap in Tesseract for the step it does best. With a
  closed API I would have seen one model's output and never known why it was wrong.

## First user

<!-- TODO: who tried it (owner/manager of a café?), what happened, would they pay, what they asked for next.
Ideas to ask: QR-code menu page, more languages (Farsi/Chinese for tour groups), allergen icons. -->

## How I built it

Python + FastAPI, vanilla JS, Ollama (Gemma 3 12B), Tesseract 5 (`hye` model), RapidFuzz, on an Apple M5
MacBook with 16 GB of memory. The showcase site is static and deployed with GitHub Pages. I built it pair-programming with
Claude Code. <!-- TODO: DevRelay / Entire session link -->

Run it yourself:

```bash
brew install tesseract ollama
ollama pull gemma3:12b
git clone https://github.com/ErikDallaqyan/hacktoberfest-project hyur && cd hyur
scripts/get_tessdata.sh hye rus eng
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```
