#!/usr/bin/env python3
"""Startet die lokale GENESIS Core API (nur 127.0.0.1, kein Cloud-Zugriff).

Nutzung:
    python3 run_api.py [--port 8420] [--data-dir ./devdata]
"""
from __future__ import annotations

import argparse
import os

import uvicorn

from genesis_core.api.app import create_app
from genesis_core.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--data-dir", type=str, default=None)
    args = parser.parse_args()

    if args.data_dir:
        os.environ["GENESIS_DATA_DIR"] = args.data_dir

    settings = Settings.load()
    app = create_app(settings)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
