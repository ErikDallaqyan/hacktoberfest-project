---
title: "Sloth Sort: a local Gemma 3 that names your screenshots so you don't have to"
published: false
tags: devchallenge, hf26challenge, gemma, opensource
cover_image: https://erikdallaqyan.github.io/hacktoberfest-project/img/review.jpg
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

Open anyone's Desktop and you'll find something like this:

```
Screenshot 2026-10-14 at 9.41.22 AM.png
Screenshot 2026-10-15 at 2.03.10 PM.png
download.pdf
document (1).pdf
Scan 2026-10-12.pdf
image (3).png
8f14e45fceea167a5a36dedd4bea2543.png
```

Every one of those was important enough to save, and not important enough to name. "I'll rename them later" is one of the great lies of computing.

**Sloth Sort** does "later" for you. It watches `~/Desktop` and `~/Downloads`. When a file with a throwaway name shows up, **Gemma 3 running on your own laptop** looks at it, works out what it is, and renames it the way a tidy person would have:

```
Screenshot 2026-10-14 at 9.41.22 AM.png  →  2026-10-24-skyline-air-boarding-pass-sfo-to-jfk.png
Screenshot 2026-10-15 at 2.03.10 PM.png  →  2026-10-15-python-billing-customer-id-error.png
download.pdf                             →  2026-10-02-acme-cloud-invoice-rivers-design-llc.pdf
Scan 2026-10-12.pdf                      →  2026-10-12-corner-hardware-oakland-paint-supplies-receipt.pdf
```

Who gets to be lazier? Anyone who has ever typed "boarding pass" into Finder search and gotten nothing back, because the boarding pass is called `Screenshot 2026-10-14 at 9.41.22 AM.png`.

The whole point is that you do nothing:

- **It only touches throwaway names.** `Screenshot …`, `IMG_4821`, `download (2).pdf`, hashes and UUIDs get renamed. `taxes 2025 notes.pdf` is left exactly as you named it.
- **Dates go first**, so files sort by when things happened. That's the invoice date or flight date if one is printed on the file, otherwise when the file was saved.
- **Every rename can be undone.** A small review page on `127.0.0.1` lists every change with one-click Undo and a box to retype the name. A file you undo is never touched again. Spotted junk while you're there? **Delete** sends it to Sloth Sort's trash, and **Restore** brings it back.
- **It moves at a sloth's pace.** One file at a time, about 4 seconds each. The model unloads itself after 5 idle minutes, so it costs nothing while you aren't making clutter.

## Demo

**Live page:** https://erikdallaqyan.github.io/hacktoberfest-project/

Press **"Let the sloth do it"** to watch a messy Desktop get renamed one file at a time. The names are real Gemma 3 output for 12 made-up files, replayed in your browser.

The review page, after tidying that Desktop:

![Sloth Sort review page: each row shows the old name crossed out, the new name, a one-line description, a category, and Undo and Rename buttons](https://erikdallaqyan.github.io/hacktoberfest-project/img/review.jpg)

Notice the red **"shows a password or key"** flag on the API keys screenshot. Gemma noticed the keys and the page warns you, so that screenshot doesn't sit on your Desktop forever.

## Code

{% github ErikDallaqyan/hacktoberfest-project %}

Running it takes three commands:

```bash
ollama pull gemma3:4b
pip install -r requirements.txt
python -m slothsort        # then open http://127.0.0.1:8765
```

Not ready to let it loose? `python -m slothsort scan ~/Downloads` previews every name without touching a file.

## How I Built It

**The open pieces:** Google's open-weight **Gemma 3** (4B) does the looking, served locally by **Ollama**. Everything around it is plain Python: FastAPI for the review page, `watchdog` for folder events, `pypdfium2` for PDFs, Pillow for images, and SQLite for the undo journal.

**The pipeline for each file:**

1. **Watch.** `watchdog` reports new files in the watched folders. macOS writes screenshots as a hidden temp file and then renames them, so "moved" events count too.
2. **Filter.** About a dozen regexes decide whether a name is a throwaway (`Screenshot …`, `IMG_1234`, `download (2)`, hashes). Anything else is left alone.
3. **Wait.** A file that is still downloading keeps growing. Sloth Sort waits until the size stops changing.
4. **Look.** Images are shrunk to 896 px, which is the resolution Gemma 3 sees at anyway. For PDFs, Gemma gets the first page as an image *and* the text layer. Phone scans have no text at all, so the image does the work.
5. **Ask.** One call to Gemma, constrained by a JSON schema, returns a sentence describing the file, a 3–7 word title, a category, the date printed on the file, and whether a secret is visible.
6. **Decide in code.** Plain Python builds the filename (more on this below).
7. **Journal, then rename.** The rename is written to SQLite *before* the file moves, so Undo always knows where everything went.

### The model suggests, code decides

This was the most important design choice. Gemma is great at reading a boarding pass. I don't want it in charge of my file system. So Gemma only suggests *words*, and [`naming.py`](https://github.com/ErikDallaqyan/hacktoberfest-project/blob/main/slothsort/naming.py) decides what a filename is allowed to contain:

- **No account numbers, ever.** Any run of 5+ digits, any email and any phone number is scrubbed from every name the model suggests. Filenames end up in Spotlight, iCloud sync logs and email attachments, so `chase-statement-7730-2219-5541.pdf` should never exist, whatever the model says.
- **Dates only if they're really printed there.** Small models fill gaps confidently. A shopping cart that said "Free delivery Thu, Oct 29" came back as `2023-10-29`. A chart titled "Q3 2026" came back as July 1. Now the model also has to copy the date *exactly as printed*, and code accepts it only if that text has a day, a month and a year. Otherwise the file's own date is used.
- **Never overwrite.** A name clash becomes `-2`, `-3`.
- **Lowercase ASCII, 60 characters max, and the date isn't repeated** inside the title. `invoice-october-2-2026` after a `2026-10-02-` prefix was a real thing Gemma did.

There are 57 tests for these rules and for the full rename → undo → retype → delete → restore flow, with the model stubbed out, so they run in CI without Ollama.

### How good are the names?

I generated 11 made-up files with headless Chrome:
- a boarding pass, a Python traceback and a group chat
- a rental listing, an API keys page and a shopping cart
- an invoice PDF, an electric bill and an image-only scan of a hardware store receipt
- a chart and a meme

[`eval.py`](https://github.com/ErikDallaqyan/hacktoberfest-project/blob/main/scripts/eval.py) checks each suggested name for the right words, category, date and secret flag.

| | Gemma 3 4B |
| --- | --- |
| Passed every check | **9 / 11** |
| Dates right | 11 / 11 |
| Secret flag right | 11 / 11 |
| Median time per file | 4.1 s |

The two misses are honest ones:
- **The meme** became `lazy-desktop-collection` (no "sloth" or "meme" in the name).
- **The signups chart** got the category "other" instead of "work".

Both names are still something you'd find in a search.

## Why Does Open Innovation Matter?

Look at what's actually in a Downloads folder:
- bank statements
- utility bills with your home address
- screenshots of private group chats
- a settings page with your API keys still on it

A cloud vision API would need **every one of those uploaded** just to suggest a filename. That's a terrible trade for a tool whose whole job is to run on everything, all the time, without you looking. A local open-weight model makes the trade disappear:

- **Your files never leave your laptop.** Gemma runs through Ollama on `localhost`, and the review page only listens on `127.0.0.1`.
- **It costs $0 to run, forever.** "Set it up once and never think about it again" is the lazy dream, and that only works if there isn't an API bill growing in the background.
- **It works offline.** On a plane, which is exactly when you screenshot your boarding pass.
- **I could pick the model size myself.** This one mattered most this week. I started with Gemma 3 **12B**. It names slightly better, but on my 16 GB laptop it took about 10 seconds per file and made the whole machine lag. That's unacceptable for something that's supposed to run quietly in the background. Switching to **Gemma 3 4B** was a single setting: `SLOTH_MODEL=gemma3:4b`. It's about twice as fast, uses about 3 GB of memory instead of 8, and still gets every date right. With a closed API you get whatever model they serve, at whatever price they set.

## The Lazy Payoff

Renaming a screenshot by hand means opening it, figuring out what it is, picking a name, typing it and fixing the date. Call it 20–30 seconds, if you ever actually do it. Sloth Sort does it in about 4 seconds of *machine* time, and zero seconds of yours.

The bigger payoff is search. Spotlight can finally find "boarding pass", "invoice" or "keyerror", because those words are now in the filenames.

<!-- TODO (Erik): if you run it on your own Desktop/Downloads this week, add one real line here, e.g.
"I pointed it at my Downloads folder: N files named in M minutes, I undid K." Otherwise delete this comment. -->

## Prize Categories

- **Best Use of Gemma.** Gemma 3 is the whole engine: it reads screenshots, photos and image-only PDF scans locally through Ollama. Its vision support is what made a single model enough for every file type. Its range of sizes is what let me drop from 12B to 4B the moment my laptop complained.

<!-- Thanks for participating! -->
