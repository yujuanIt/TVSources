#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_DIR"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
node --experimental-vm-modules --test tests/*.test.mjs
node --check assets/editor.js
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build-source-site.py
