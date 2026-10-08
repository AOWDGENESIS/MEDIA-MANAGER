#!/usr/bin/env bash
# Fuehrt die komplette Python-Testsuite im SAFE TEST MODE aus (§50/§51).
set -euo pipefail
cd "$(dirname "$0")/.."

echo ">>> Stelle sicher, dass Abhaengigkeiten installiert sind ..."
bash scripts/setup_python_env.sh >/dev/null

echo ">>> Fuehre pytest aus (core/) ..."
cd core
python3 -m pytest -v --tb=short
