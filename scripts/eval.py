"""Score models on the sample menu: reading accuracy, and translation quality with vs without the glossary.

    .venv/bin/python scripts/eval.py gemma3:12b qwen2.5vl:7b qwen2.5:7b
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "samples"))

from rapidfuzz import fuzz  # noqa: E402

from app import pipeline  # noqa: E402
from app.ollama_client import OllamaError  # noqa: E402
from make_sample_menu import MENU  # noqa: E402

# What an English-speaking guest must see in each dish name for the translation to count as right.
EXPECTED_EN = {
    "Տոլմա խաղողի տերևով": ["tolma"],
    "Բաստուրմա": ["basturma"],
    "Ժինգյալով հաց": ["zhingyalov"],
    "Խորոված խոզի": ["khorovats", "pork"],
    "Խաշլամա": ["khashlama"],
    "Մանթի": ["manti"],
    "Ղափամա": ["ghapama"],
    "Գաթա": ["gata"],
    "Փախլավա": ["pakhlava"],
    "Թան": ["tan"],
    "Հայկական սուրճ": ["armenian", "coffee"],
}
MEAT_DISHES = {"Տոլմա խաղողի տերևով", "Բաստուրմա", "Խորոված խոզի", "Խաշլամա", "Մանթի"}


def truth_menu() -> dict:
    return pipeline._with_ids({
        "title": "Ճաշացանկ", "currency": "AMD",
        "sections": [{"name": s, "items": [{"name": n, "description": d, "price": p} for n, d, p in items]}
                     for s, items in MENU],
    })


def score_reading(menu: dict) -> dict:
    truth = [(n, p) for _, items in MENU for n, _, p in items]
    got = [(it["name"], it["price"]) for s in menu.get("sections", []) for it in s.get("items", [])]
    name_scores = [max((fuzz.ratio(n, g) for g, _ in got), default=0) for n, _ in truth]
    prices = {p for _, p in got}
    return {
        "dishes_found": f"{len(got)}/{len(truth)}",
        "name_accuracy": round(sum(name_scores) / len(truth), 1),
        "prices_right": f"{sum(any(p in gp for gp in prices) for _, p in truth)}/{len(truth)}",
    }


def score_translation(result: dict) -> dict:
    names_ok, veg_wrong = 0, 0
    for s in result["sections"]:
        for it in s["items"]:
            want = EXPECTED_EN.get(it["source_name"], [])
            if all(w in it["name"].lower() for w in want):
                names_ok += 1
            if it["source_name"] in MEAT_DISHES and "vegetarian" in it["dietary"]:
                veg_wrong += 1
    return {"names_right": f"{names_ok}/{len(EXPECTED_EN)}", "false_vegetarian": veg_wrong}


def main(models: list[str]):
    image = (ROOT / "samples" / "sample_menu_hy.png").read_bytes()
    report = {}
    for model in models:
        row = {}
        for reader in ("vision", "ocr"):
            try:
                menu, stats = pipeline.extract_from_image(image, "hy", model, reader, "armenian-classics")
                row[f"read_{reader}"] = {**score_reading(menu), "seconds": stats["seconds"]}
            except OllamaError as e:
                row[f"read_{reader}"] = {"error": str(e)[:120]}
        for label, gid, guard in (("generic", "__none__", False), ("hyur", "armenian-classics", True)):
            t0 = time.time()
            try:
                res, _ = pipeline.translate(truth_menu(), "hy", "en", gid, model, dietary_guard=guard)
                row[label] = {**score_translation(res), "seconds": round(time.time() - t0, 1),
                              "sample": [it["name"] for it in res["sections"][1]["items"]]}
            except OllamaError as e:
                row[label] = {"error": str(e)[:120]}
        report[model] = row
        print(json.dumps({model: row}, ensure_ascii=False, indent=2), flush=True)
    out = ROOT / "docs" / "eval.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["gemma3:12b"])
