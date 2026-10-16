"""Run the real pipeline on the sample menu and write the results the showcase site renders.

    .venv/bin/python scripts/build_site_data.py [model]
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import pipeline  # noqa: E402

TARGETS = ["en", "ru", "fr"]
# What the owner types in the "Check what we read" step for lines OCR could not recover.
# Applied only when OCR actually produced the misread, and recorded so the site can say so.
REVIEW_FIXES = {"Բայկականխարն": "Հայկական սուրճ"}


def main(model: str):
    out = ROOT / "site" / "data"
    out.mkdir(parents=True, exist_ok=True)
    image = (ROOT / "samples" / "sample_menu_hy.png").read_bytes()

    menu, read_stats = pipeline.extract_from_image(image, "hy", model, "auto", "armenian-classics")
    print("read", read_stats, flush=True)
    fixes = []
    for section in menu["sections"]:
        for item in section["items"]:
            if item["name"] in REVIEW_FIXES:
                fixes.append([item["name"], REVIEW_FIXES[item["name"]]])
                item["name"] = REVIEW_FIXES[item["name"]]
    result = {"model": model, "read": read_stats, "menu": menu, "translations": {}, "generic": {}, "stats": {},
              "review_fixes": fixes}
    for lang in TARGETS:
        res, stats = pipeline.translate(menu, "hy", lang, "armenian-classics", model)
        result["translations"][lang] = res
        result["stats"][lang] = stats
        print(lang, stats, flush=True)
    # Same model, no glossary and no guard: what a generic translation of this menu looks like.
    generic, _ = pipeline.translate(menu, "hy", "en", "__none__", model, dietary_guard=False)
    result["generic"]["en"] = generic

    (out / "sample.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    eval_json = ROOT / "docs" / "eval.json"
    if eval_json.exists():
        shutil.copy(eval_json, out / "eval.json")
    img = ROOT / "site" / "img"
    img.mkdir(exist_ok=True)
    shutil.copy(ROOT / "samples" / "sample_menu_hy.png", img / "sample_menu_hy.png")
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "gemma3:12b")
