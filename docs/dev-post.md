---
title: "Hyur: a menu translator that knows what Tolma is (runs on a laptop, costs $0 per menu)"
published: false
tags: devchallenge, hf26challenge, ai, opensource
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

## What I Built

Imagine a translation app turning "buffalo wings" into "wings of a buffalo". That's what generic translation does
to Armenian menus.

**Hyur** (pronounced "hyoor", Armenian for *guest*) turns a phone photo of a restaurant menu into a clean, printable
bilingual menu. It runs entirely on the restaurant's own laptop with open-weight models:
**Gemma 3 12B** through Ollama, plus **Tesseract** OCR.

**Who pays:** family restaurants with a menu in one language and guests who read another. I started with
Armenian: restaurants in Armenia that serve a growing number of tourists, and Armenian restaurants in places like
Glendale, Fresno and Watertown that want an English menu next to the Armenian one. Today many of them run the menu
through a generic translator or pay a translator every time the menu changes. Hyur is a one-time setup (or a
small monthly fee for glossary packs and reprints), and after that each menu costs nothing.

The insight that shaped the whole build: **the fix isn't a bigger model, it's the restaurant's own knowledge.**
Hyur keeps a *house glossary* of how each dish should be named and explained. The model has to follow it, and
every correction the owner makes is saved back to the glossary, so the menu gets better every time they use it.

## Demo

🔗 **Live showcase:** https://erikdallaqyan.github.io/hacktoberfest-project/ (the real pipeline output on a
sample menu; toggle **Generic** to see the same model without the glossary)

![Hyur home: your menu, in every guest's language](https://raw.githubusercontent.com/ErikDallaqyan/hacktoberfest-project/main/docs/img/01-home.jpg)

**1. Read and review.** The owner checks what was read; lines fixed automatically from the glossary are marked in green.

![Review step with auto-corrected dish names highlighted](https://raw.githubusercontent.com/ErikDallaqyan/hacktoberfest-project/main/docs/img/02-review.jpg)

**2. The bilingual menu.** Each dish keeps its real name (the way a US menu says "Pad Thai", not "Thai fried noodles"), the original
Armenian, a short description, dietary tags and the glossary entries it used. Prices are in Armenian dram (AMD). "Correct" saves the owner's wording for next time.

![Translated two-column menu with prices and glossary hits](https://raw.githubusercontent.com/ErikDallaqyan/hacktoberfest-project/main/docs/img/03-result.jpg)

**3. Why it works.** Same model, with and without the house glossary.

![Generic vs house-glossary translation comparison](https://raw.githubusercontent.com/ErikDallaqyan/hacktoberfest-project/main/docs/img/04-glossary.jpg)

## Code

{% github ErikDallaqyan/hacktoberfest-project %}

## How I Built It

**Open-source AI at the core:** Gemma 3 12B (open weights) running locally through Ollama, and Tesseract 5 with
its Armenian (`hye`) model. Around them: Python + FastAPI, RapidFuzz for fuzzy matching, and a vanilla JS
frontend. Everything ran on an Apple M5 MacBook with 16 GB of memory. I built it pair-programming with Claude Code.

### The pipeline

1. **Read.** Tesseract OCRs the photo in **0.3 s**. Gemma 3 then structures the text into sections, dishes,
   descriptions and prices.
2. **Fix.** When OCR swaps a letter in a dish name (think "Lasagma" for "Lasagna"), Hyur snaps it to the
   glossary's spelling: *Մանքի → Մանթի*, *Գաքա → Գաթա*,
   and even a word OCR split in two, *Բ ատուրմո → Բաստուրմա*. The owner then reviews every line, with
   auto-fixes highlighted, before anything is translated.
3. **Ground.** Every dish is fuzzy-matched against the house glossary. Armenian grammar adds endings to words
   (*խորիզ* → *խորիզ**ով***, "with khoriz"), so matching tolerates suffixes and typos but stays word-aligned, which keeps
   *pakhlava* from matching *lavash*. The matching rules go into the prompt **right under each dish**, split into
   "this dish is…" and "this ingredient is…".
4. **Translate.** Gemma 3 translates into any of 12 languages. Prices and dish order never pass through the
   model's output; translations are merged back by dish id.
5. **Guard.** Dietary tags are checked in code: a dish whose text mentions meat can never be "vegetarian", and
   "contains-pork" appears only when pork is actually mentioned.
6. **Learn.** *Correct → Save to house glossary* writes the fix back, per language, and it overrides the model
   on every later menu.

### What I found (measured, not vibes)

I scored three local models on a sample 11-dish Armenian menu with `scripts/eval.py`:

| Model | Read: vision only | Read: Tesseract + model | Dish names right: generic → **Hyur** |
|---|---|---|---|
| Gemma 3 12B | 85.5% | **94%** | 7/11 → **11/11** |
| Qwen2.5-VL 7B | 44% | **94%** | 7/11 → **11/11** |
| Qwen2.5 7B (text only) | n/a | **94%** | 8/11 → **10/11** |

*Reading = character-level similarity of dish names to the printed menu. Names right = the English name keeps
the real dish name, for example "Khorovats (Armenian barbecue) … with Pork Rib Chops" instead of "Pork Kebab".*

What surprised me:

- **Two popular open vision models decided Armenian was Georgian.** Armenian has its own 38-letter alphabet, and
  Georgian is a different one. Qwen2.5-VL and Qwen3-VL both returned a
  confident menu in Georgian script with every dish invented. Gemma 3 read the Armenian script, but imperfectly.
  A 6 MB Tesseract model beat all of them, so the final design uses each open component for what it's good at.
- **The glossary mattered more than the model.** Without it, Gemma 3 wrote "Pork Kebab", "Hashlama" and "Grape
  Leaf Dolma". With it, every model I tried got the dishes right. That's the case for a small, swappable model plus
  owner-curated knowledge.
- **Small models make confident dietary mistakes.** One run tagged Tolma (stuffed grape leaves with ground meat, the Armenian cousin of Greek dolmades) as *vegetarian*. Another
  tagged Basturma (beef) as *contains-pork*. That's why dietary tags are decided in code, not in the prompt.
- **Generic mode invents things.** Faced with an OCR-garbled coffee line, the no-glossary run described it as "a
  traditional Armenian herbal tea". Hyur's review step and blank-name fallback exist because of that.

### Shipping it

It ships as two Docker images: an nginx frontend and a FastAPI + Tesseract backend that talks to Ollama on the
host (Docker on a Mac can't use the Apple GPU). GitHub Actions runs the tests and smoke-tests both images on
every push, and deploys the showcase site to GitHub Pages.

With Docker and [Ollama](https://ollama.com) installed:

```bash
ollama pull gemma3:12b
git clone https://github.com/ErikDallaqyan/hacktoberfest-project hyur && cd hyur
docker compose up --build     # open http://localhost:8000
```

## Why Does Open Innovation Matter?

- **$0 per menu makes the business work.** Restaurants reprint menus whenever a price changes. With no per-call
  bill, "translate it again" is never a decision, and I can sell a flat price.
- **The glossary is the product, the model is a dropdown.** When a better open model ships, owners switch in
  the UI and keep every correction. No lock-in to anyone's pricing or deprecation schedule.
- **Offline and private.** The laptop in the back office is enough, even with spotty Wi-Fi, and menus, prices and supplier
  notes never leave it.
- **I could see the failures and fix them.** Running everything locally let me test four models on the same
  menu in an afternoon, find the Georgian misread, and swap in Tesseract for the step it does best. With a
  closed API I would have seen one model's output and never known why it was wrong.

## What's Next

So far I've tested Hyur on a sample Armenian menu, not on a restaurant's own photos. Next up:

- **Real menus:** phone photos of real menus, with glare, handwriting and two-column layouts.
- **A QR-code page:** so guests can read the menu in their own language on their phone.
- **More starter glossaries:** for example Georgian and Persian dishes.

## Prize Categories

- **Best Use of Gemma:** Gemma 3 12B runs locally and does both the menu structuring and the glossary-grounded
  translation. The eval above compares it with and without the glossary, and against Qwen models.
- **Best Use of GitHub Copilot (GitHub Actions):** Actions runs the test suite, builds and smoke-tests both
  Docker images on every push, and deploys the showcase site to GitHub Pages.
