# Hyur — menu translation that knows your dishes

**Hyur** (հյուր, Armenian for *guest*) turns a photo of a restaurant menu into a clean bilingual menu for
foreign guests — running entirely on the restaurant's own laptop with open-weight models via
[Ollama](https://ollama.com).

Without restaurant knowledge, open models turned *Khorovats* into "Pork Kebab", *Khashlama* into "Hashlama",
garlic matsun into "pickled cabbage", and tagged meat-stuffed *Tolma* as vegetarian. Hyur keeps a **house glossary** per restaurant: how each dish
should be named and explained. The model must follow it, and every correction the owner makes is saved back
to the glossary so the next menu comes out right the first time.

## Results

On the sample 11-dish Armenian menu (`scripts/eval.py`, Apple M5, 16 GB):

| Model | Read: vision only | Read: Tesseract + model | Dish names right: generic → Hyur |
|---|---|---|---|
| gemma3:12b | 85.5% | 94% | 7/11 → **11/11** |
| qwen2.5vl:7b | 44% | 94% | 7/11 → **11/11** |
| qwen2.5:7b | — | 94% | 8/11 → **10/11** |

Qwen2.5-VL and Qwen3-VL read the Armenian menu as Georgian; Tesseract's Armenian model reads it in 0.3 s.

## How it works

```
menu photo ──► Tesseract OCR (hye) ──► Gemma 3 structures it ──► sections, dishes, prices
                                                │  OCR typos snapped to glossary spellings
                                                │  owner reviews / fixes any misreads
                                                ▼
                    house glossary match (fuzzy, handles Armenian/Russian suffixes)
                                                │  per-dish rules injected into the prompt
                                                ▼
                    Gemma 3 translation ──► dietary safety check ──► bilingual menu (print / JSON)
                                                ▲
                          owner corrections ────┘ saved back to the glossary
```

- **Reading**: Tesseract OCR reads the photo, then the model structures the text. A model-only vision path
  is available too (`Read photos with → Model vision`), but open vision models are weak on Armenian script.
- **Glossary grounding**: only the entries that match a dish are injected, right under that dish, split into
  "this dish is X" and "mentions ingredient X".
- **Prices and order never pass through the model's output** — translations are merged back by dish id.
- **Dietary guard**: a dish whose text mentions meat can never be labelled vegetarian, and pork is always
  flagged, whatever the model says.

## Run it

Requires [Ollama](https://ollama.com), [Tesseract](https://github.com/tesseract-ocr/tesseract) and Python 3.11+.

```bash
brew install tesseract ollama
ollama pull gemma3:12b
scripts/get_tessdata.sh hye rus eng
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```

Open http://localhost:8000, click **Use the sample Armenian menu**, then **Read menu** → **Translate**.

Any Ollama model works; pick it in the UI or set `HYUR_VISION_MODEL` / `HYUR_TEXT_MODEL`.
Smaller machines can use `gemma3:4b`.

## Evaluate

```bash
.venv/bin/python scripts/eval.py gemma3:12b qwen2.5vl:7b
```

Scores reading accuracy on the sample menu and English translation quality with vs. without the house
glossary. Results are written to `docs/eval.json`.

## Tests

```bash
.venv/bin/python -m pytest -q
```

## Showcase site

`site/` is a static page with the real pipeline output on the sample menu, deployed by
`.github/workflows/pages.yml`. Rebuild its data with `scripts/build_site_data.py gemma3:12b`.

## Glossaries

`data/glossaries/armenian-classics.json` is a starter set of 24 Armenian dishes and 14 common ingredients in English and Russian.
Click **+ New** in the app to copy it for your restaurant; corrections you save land in your copy.
Uploaded menus are stored in `data/menus/` and are git-ignored.

## License

MIT
