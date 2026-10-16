#!/usr/bin/env bash
# Download Tesseract "best" language models into data/tessdata. Usage: scripts/get_tessdata.sh hye rus eng
set -euo pipefail
dir="$(cd "$(dirname "$0")/.." && pwd)/data/tessdata"
mkdir -p "$dir"
for lang in "${@:-hye rus eng}"; do
  for l in $lang; do
    echo "fetching $l"
    curl -fsSL -o "$dir/$l.traineddata" "https://github.com/tesseract-ocr/tessdata_best/raw/main/$l.traineddata"
  done
done
