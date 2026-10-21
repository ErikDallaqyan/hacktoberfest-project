"""Copy an eval run and small previews of the demo files into site/ for the showcase page.

    python scripts/build_site_data.py demo docs/eval/gemma3-4b.json
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from slothsort import reader  # noqa: E402


def main() -> None:
    demo, run = Path(sys.argv[1]), Path(sys.argv[2])
    data = json.loads(run.read_text())
    out_img = ROOT / "site" / "img" / "demo"
    out_img.mkdir(parents=True, exist_ok=True)
    for row in data["rows"]:
        slug = re.sub(r"[^a-z0-9]+", "-", row["file"].lower()).strip("-")
        (out_img / f"{slug}.jpg").write_bytes(reader.thumbnail(demo / row["file"], 360))
        row["thumb"] = f"img/demo/{slug}.jpg"
    (ROOT / "site" / "data" / "eval.json").write_text(json.dumps(data, indent=2))
    print(f"wrote {len(data['rows'])} rows and previews")


if __name__ == "__main__":
    main()
