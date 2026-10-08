"""Gemeinsame Pytest-Fixtures.

Erzwingt SAFE TEST MODE (§51): Tests arbeiten IMMER in temporaeren
Verzeichnissen und einer temporaeren SQLite-DB, niemals in einem echten
GENESIS-Datenverzeichnis und niemals mit echten Mediendateien (§50).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from genesis_core.config import Settings
from genesis_core.db import Database
from testdata_generator.generate import generate_test_library


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "genesis_data"
    d.mkdir()
    return d


@pytest.fixture()
def settings(tmp_data_dir: Path) -> Settings:
    s = Settings()
    s.paths.data_dir = tmp_data_dir
    s.general.safe_test_mode = True
    s.ensure_directories()
    return s


@pytest.fixture()
def db(settings: Settings) -> Database:
    return Database(settings.paths.resolved_database_path())


@pytest.fixture(scope="session")
def test_library_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("genesis_test_library")
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg nicht verfuegbar - Testbibliothek kann nicht erzeugt werden")
    generate_test_library(root)
    return root
