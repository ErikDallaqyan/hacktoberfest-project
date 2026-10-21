"""Score a model on the demo folder: does each name have the right words, category, date and secret flag?

    python scripts/make_demo_files.py demo
    python scripts/eval.py demo                      # uses SLOTH_MODEL, default gemma3:4b
    SLOTH_MODEL=gemma3:12b python scripts/eval.py demo

Nothing is renamed. Results go to docs/eval/<model>.json.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from slothsort import config, namer, worker  # noqa: E402

# words: every group must have at least one of its words in the name.
# date: the date the name must start with; None means "no date is printed, so use the file's own date".
EXPECTED = {
    "Screenshot 2026-10-14 at 9.41.22 AM.png": dict(words=[["skyline"], ["boarding"]], cats={"travel"}, date="2026-10-24"),
    "Screenshot 2026-10-15 at 2.03.10 PM.png": dict(words=[["keyerror", "error", "traceback"], ["billing", "invoices", "python"]], cats={"code"}, date="2026-10-15"),
    "Screenshot 2026-10-16 at 7.12.45 PM.png": dict(words=[["dinner", "taco", "tacos", "lupita"]], cats={"chats"}, date="2026-10-16"),
    "Screenshot 2026-10-17 at 11.30.02 AM.png": dict(words=[["homenest", "apartment", "rent", "rental", "listing"], ["oakland", "linden", "2br", "bedroom"]], cats={"shopping", "other", "work"}, date="2026-10-17"),
    "Screenshot 2026-10-18 at 4.55.31 PM.png": dict(words=[["api"], ["key", "keys"]], cats={"code", "work"}, date="2026-10-18", secrets=True),
    "Screenshot 2026-10-19 at 8.20.14 PM.png": dict(words=[["desk"]], cats={"shopping"}, date="2026-10-19"),
    "download.pdf": dict(words=[["acme"], ["invoice"]], cats={"money"}, date="2026-10-02", secrets=False),
    "document (1).pdf": dict(words=[["eastbay", "electric", "power"], ["bill", "statement"]], cats={"money"}, date="2026-09-28"),
    "Scan 2026-10-12.pdf": dict(words=[["corner", "hardware"], ["receipt", "paint", "hardware"]], cats={"money", "shopping"}, date="2026-10-12"),
    "image (3).png": dict(words=[["signup", "signups", "newsletter", "subscribers"]], cats={"work"}, date=None),
    "8f14e45fceea167a5a36dedd4bea2543.png": dict(words=[["sloth", "meme", "procrastination", "screenshots"]], cats={"memes"}, date=None),
}


def score(path: Path) -> dict:
    exp = EXPECTED[path.name]
    s = namer.suggest(path)
    target = worker.plan_name(path, s, sort_into_folders=False).name
    words = set(target.rsplit(".", 1)[0].split("-"))
    fallback = time.strftime("%Y-%m-%d", time.localtime(path.stat().st_mtime))
    want_date = exp["date"] or fallback
    checks = {
        "words": all(words & set(group) for group in exp["words"]),
        "category": s.category in exp["cats"],
        "date": target.startswith(want_date),
        "secrets": s.contains_secrets == exp.get("secrets", False),
    }
    return {"file": path.name, "name": target, "category": s.category, "what": s.what,
            "secrets": s.contains_secrets, "seconds": s.seconds, "checks": checks, "pass": all(checks.values())}


def main() -> None:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "demo")
    rows = []
    for name in EXPECTED:
        r = score(folder / name)
        rows.append(r)
        bad = [k for k, ok in r["checks"].items() if not ok]
        print(f"{'PASS' if r['pass'] else 'MISS'} {r['seconds']:>5}s  {r['name']}" + (f"   ({', '.join(bad)})" if bad else ""))

    n = len(rows)
    timed = sorted(r["seconds"] for r in rows)
    summary = {
        "model": config.MODEL,
        "files": n,
        "all_checks_passed": sum(r["pass"] for r in rows),
        **{k: sum(r["checks"][k] for r in rows) for k in ("words", "category", "date", "secrets")},
        "median_seconds": timed[n // 2],
        "total_seconds": round(sum(timed), 1),
    }
    print(json.dumps(summary, indent=2))
    out = ROOT / "docs" / "eval" / f"{config.MODEL.replace(':', '-')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print("saved", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
