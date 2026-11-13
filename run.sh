#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 analyze.py
python3 render_html.py
echo "report: $(pwd)/index.html"
