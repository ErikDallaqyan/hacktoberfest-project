"""python -m slothsort            start watching and open the review page
python -m slothsort scan DIR   preview names for a folder without touching anything
python -m slothsort scan DIR --apply   rename them for real (undo from the review page)"""
import argparse
import logging
import sys
from pathlib import Path

from . import config


def scan(folder: Path, apply: bool) -> None:
    from . import journal, namer, worker

    files = worker.backlog([folder], config.RENAME_ALL)
    if not files:
        print(f"Nothing to rename in {folder}: no throwaway names found.")
        return
    w = worker.Worker()
    total = 0.0
    for p in files:
        if apply:
            row = w.process(p)
            if not row:
                continue
            total += row["seconds"] or 0
            new = Path(row["new_path"]).name if row["new_path"] else f"ERROR {row['error']}"
            print(f"{p.name}\n  -> {new}   [{row['category']}, {row['seconds']}s]")
        else:
            s = namer.suggest(p)
            total += s.seconds
            target = worker.plan_name(p, s, w.sort_into_folders)
            flag = "  ⚠ shows a secret" if s.contains_secrets else ""
            print(f"{p.name}\n  -> {target.relative_to(folder)}   [{s.category}, {s.seconds}s]{flag}")
    print(f"\n{len(files)} files, {total:.0f}s of model time on {config.MODEL}."
          + ("" if apply else " Nothing was renamed; add --apply to do it."))


def main() -> None:
    ap = argparse.ArgumentParser(prog="slothsort", description="Names your files so you don't have to.")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("scan", help="preview or apply names for one folder")
    s.add_argument("folder", type=Path)
    s.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.cmd == "scan":
        scan(args.folder.expanduser().resolve(), args.apply)
        return

    import uvicorn

    print(f"Sloth Sort is watching {', '.join(str(d) for d in config.WATCH_DIRS)}")
    print(f"Review page: http://127.0.0.1:{config.PORT}")
    uvicorn.run("slothsort.server:app", host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    sys.exit(main())
