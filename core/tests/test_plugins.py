"""Tests fuer das Plugin-System (§34) - insbesondere der zentrale Beweis,
dass ein fehlerhaftes Plugin den Host NICHT destabilisiert."""
from __future__ import annotations

from pathlib import Path

import pytest

from genesis_core import plugins as plugins_module
from genesis_core.exporter import MediaExportRow
from genesis_core.plugins import (
    PluginKind,
    PluginRegistry,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "genesis_core" / "plugins" / "examples"


def _sample_rows() -> list[MediaExportRow]:
    return [
        MediaExportRow(
            media_file_id=1, absolute_path="/music/a.mp3", filename="a.mp3",
            extension=".mp3", kind="music", size_bytes=10, content_hash_sha256=None,
            is_missing=False, title="Song", artist="Artist", album="Album",
            track_number=1, year=2020, duration_seconds=100.0,
        )
    ]


def test_discover_and_load_finds_working_example_exporter():
    registry = PluginRegistry()
    loaded = registry.discover_and_load(EXAMPLES_DIR)
    ids = {p.plugin_id for p in loaded}
    assert "example-pipe-separated-exporter" in ids

    exporter = next(p for p in loaded if p.plugin_id == "example-pipe-separated-exporter")
    assert exporter.loaded_successfully
    assert exporter.plugin_kind == PluginKind.EXPORTER.value
    assert exporter.license is not None


def test_discover_and_load_isolates_broken_plugin_without_crashing():
    """Der zentrale §34-Beweis: ein Plugin, das beim Import eine Exception
    wirft, darf weder den Host abstuerzen lassen noch das Laden der
    UEBRIGEN (funktionierenden) Plugins verhindern."""
    registry = PluginRegistry()
    loaded = registry.discover_and_load(EXAMPLES_DIR)

    broken = next(p for p in loaded if p.plugin_id == "broken_example")
    assert not broken.loaded_successfully
    assert broken.load_error is not None
    assert "absichtlich fehlerhaftes" in broken.load_error

    # Das funktionierende Plugin ist TROTZ des kaputten Nachbarn weiterhin da.
    working = next(p for p in loaded if p.plugin_id == "example-pipe-separated-exporter")
    assert working.loaded_successfully


def test_example_exporter_actually_produces_pipe_separated_output():
    registry = PluginRegistry()
    registry.discover_and_load(EXAMPLES_DIR)
    content, error = registry.call_exporter("example-pipe-separated-exporter", _sample_rows())
    assert error is None
    assert content is not None
    assert "media_file_id|absolute_path" in content
    assert "a.mp3" in content
    assert "|" in content


def test_discover_and_load_nonexistent_dir_returns_empty(tmp_path: Path):
    registry = PluginRegistry()
    assert registry.discover_and_load(tmp_path / "does_not_exist") == []


def test_plugin_missing_plugin_py_is_reported_as_load_error(tmp_path: Path):
    (tmp_path / "empty_plugin_dir").mkdir()
    registry = PluginRegistry()
    loaded = registry.discover_and_load(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].load_error is not None


def test_plugin_without_plugin_class_attribute_is_rejected(tmp_path: Path):
    plugin_dir = tmp_path / "no_plugin_class"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text("x = 1\n", encoding="utf-8")
    registry = PluginRegistry()
    loaded = registry.discover_and_load(tmp_path)
    assert loaded[0].load_error is not None
    assert "PLUGIN_CLASS" in loaded[0].load_error


def test_plugin_not_a_pluginbase_subclass_is_rejected(tmp_path: Path):
    plugin_dir = tmp_path / "wrong_type"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        "class NotAPlugin:\n    pass\nPLUGIN_CLASS = NotAPlugin\n", encoding="utf-8"
    )
    registry = PluginRegistry()
    loaded = registry.discover_and_load(tmp_path)
    assert loaded[0].load_error is not None


def test_plugin_missing_required_attributes_is_rejected(tmp_path: Path):
    plugin_dir = tmp_path / "missing_attrs"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        "from genesis_core.plugins import PluginBase\n"
        "class Incomplete(PluginBase):\n"
        "    plugin_id = ''\n"
        "PLUGIN_CLASS = Incomplete\n",
        encoding="utf-8",
    )
    registry = PluginRegistry()
    loaded = registry.discover_and_load(tmp_path)
    assert loaded[0].load_error is not None
    assert "plugin_id" in loaded[0].load_error


def test_duplicate_plugin_id_keeps_first_and_flags_second(tmp_path: Path):
    body = (
        "from genesis_core.plugins import ExporterPlugin, PluginKind\n"
        "class Dup(ExporterPlugin):\n"
        "    plugin_id = 'dup-id'\n"
        "    plugin_kind = PluginKind.EXPORTER\n"
        "    display_name = 'Dup'\n"
        "    def file_extension(self): return '.txt'\n"
        "    def export(self, rows): return 'x'\n"
        "PLUGIN_CLASS = Dup\n"
    )
    for name in ("plugin_a", "plugin_b"):
        d = tmp_path / name
        d.mkdir()
        (d / "plugin.py").write_text(body, encoding="utf-8")

    registry = PluginRegistry()
    loaded = registry.discover_and_load(tmp_path)
    successful = [p for p in loaded if p.loaded_successfully and p.plugin_id == "dup-id"]
    failed = [p for p in loaded if not p.loaded_successfully]
    assert len(successful) == 1
    assert len(failed) == 1
    assert "bereits vergeben" in failed[0].load_error


def test_call_exporter_catches_runtime_exception(tmp_path: Path):
    """Nicht nur Ladefehler, auch ein zur Laufzeit fehlschlagendes Plugin
    darf den Host nicht mitreissen (Moduldocstring Punkt 3)."""
    plugin_dir = tmp_path / "runtime_boom"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        "from genesis_core.plugins import ExporterPlugin, PluginKind\n"
        "class Boom(ExporterPlugin):\n"
        "    plugin_id = 'boom'\n"
        "    plugin_kind = PluginKind.EXPORTER\n"
        "    display_name = 'Boom'\n"
        "    def file_extension(self): return '.txt'\n"
        "    def export(self, rows): raise RuntimeError('kaputt zur Laufzeit')\n"
        "PLUGIN_CLASS = Boom\n",
        encoding="utf-8",
    )
    registry = PluginRegistry()
    registry.discover_and_load(tmp_path)
    content, error = registry.call_exporter("boom", _sample_rows())
    assert content is None
    assert error is not None
    assert "kaputt zur Laufzeit" in error


def test_call_unknown_exporter_returns_clear_error():
    registry = PluginRegistry()
    content, error = registry.call_exporter("does-not-exist", [])
    assert content is None
    assert "nicht gefunden" in error


def test_safe_export_filename_uses_plugin_extension():
    registry = PluginRegistry()
    registry.discover_and_load(EXAMPLES_DIR)
    filename = registry.safe_export_filename("example-pipe-separated-exporter")
    assert filename == "export.psv"


def test_safe_export_filename_falls_back_for_unknown_plugin():
    registry = PluginRegistry()
    assert registry.safe_export_filename("does-not-exist") == "export.txt"


def test_safe_export_filename_sanitizes_malicious_extension(tmp_path: Path):
    """Deep-Review-Fund (Sitzung 11): `file_extension()` ist Plugin-Code
    und darf NIE ungeprueft in einen Dateinamen/HTTP-Header einfliessen -
    ein boeswilliges oder nur fehlerhaftes Plugin koennte versuchen,
    Pfadtrenner einzuschleusen oder beim Aufruf selbst abzustuerzen."""
    plugin_dir = tmp_path / "evil_extension"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        "from genesis_core.plugins import ExporterPlugin, PluginKind\n"
        "class Evil(ExporterPlugin):\n"
        "    plugin_id = 'evil-extension'\n"
        "    plugin_kind = PluginKind.EXPORTER\n"
        "    display_name = 'Evil'\n"
        "    def file_extension(self): return '../../etc/passwd'\n"
        "    def export(self, rows): return 'x'\n"
        "PLUGIN_CLASS = Evil\n",
        encoding="utf-8",
    )
    registry = PluginRegistry()
    registry.discover_and_load(tmp_path)
    assert registry.safe_export_filename("evil-extension") == "export.txt"


def test_safe_export_filename_falls_back_when_extension_raises(tmp_path: Path):
    plugin_dir = tmp_path / "boom_extension"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        "from genesis_core.plugins import ExporterPlugin, PluginKind\n"
        "class BoomExt(ExporterPlugin):\n"
        "    plugin_id = 'boom-extension'\n"
        "    plugin_kind = PluginKind.EXPORTER\n"
        "    display_name = 'BoomExt'\n"
        "    def file_extension(self): raise RuntimeError('kaputt')\n"
        "    def export(self, rows): return 'x'\n"
        "PLUGIN_CLASS = BoomExt\n",
        encoding="utf-8",
    )
    registry = PluginRegistry()
    registry.discover_and_load(tmp_path)
    assert registry.safe_export_filename("boom-extension") == "export.txt"


# --- Deep-Review-Fund (Sitzung 11, Abgleich gegen ADR-0020-Zusagen) -------
#
# Der bisherige try/except-Schutz faengt nur EXCEPTIONS ab, nicht aber ein
# Plugin, das stattdessen HAENGT (Endlosschleife/blockierender Aufruf ohne
# eigenes Timeout). Empirisch nachgewiesen: ein Plugin mit einer
# Modul-Ebene-Blockierung liess `discover_and_load` (und damit beim
# echten Core-Service-Start den KOMPLETTEN Anwendungsstart) unbegrenzt
# haengen. Die folgenden Tests verwenden `monkeypatch`, um die
# Produktions-Zeitlimits (10s/60s/5s) auf Testgeschwindigkeit zu
# reduzieren, statt echte zehn Sekunden pro Testlauf zu warten.

def test_hanging_plugin_at_load_time_times_out_instead_of_blocking_forever(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plugins_module, "PLUGIN_LOAD_TIMEOUT_SECONDS", 0.2)
    plugin_dir = tmp_path / "hangs_at_import"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        "import time\n"
        "from genesis_core.plugins import ExporterPlugin, PluginKind\n"
        "class Hanger(ExporterPlugin):\n"
        "    plugin_id = 'hangs-at-import'\n"
        "    plugin_kind = PluginKind.EXPORTER\n"
        "    display_name = 'Hanger'\n"
        "    def file_extension(self): return 'txt'\n"
        "    def export(self, rows): return 'x'\n"
        "time.sleep(999)\n"  # simuliert Endlosschleife/blockierenden Aufruf
        "PLUGIN_CLASS = Hanger\n",
        encoding="utf-8",
    )
    registry = PluginRegistry()
    loaded = registry.discover_and_load(tmp_path)  # darf NICHT 999s blockieren
    assert len(loaded) == 1
    assert loaded[0].load_error is not None
    assert "Zeitlimit" in loaded[0].load_error


def test_hanging_exporter_call_times_out_instead_of_blocking_forever(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plugins_module, "PLUGIN_CALL_TIMEOUT_SECONDS", 0.2)
    plugin_dir = tmp_path / "hangs_at_export"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        "import time\n"
        "from genesis_core.plugins import ExporterPlugin, PluginKind\n"
        "class SlowExporter(ExporterPlugin):\n"
        "    plugin_id = 'hangs-at-export'\n"
        "    plugin_kind = PluginKind.EXPORTER\n"
        "    display_name = 'SlowExporter'\n"
        "    def file_extension(self): return 'txt'\n"
        "    def export(self, rows):\n"
        "        time.sleep(999)\n"
        "        return 'niemals erreicht'\n"
        "PLUGIN_CLASS = SlowExporter\n",
        encoding="utf-8",
    )
    registry = PluginRegistry()
    registry.discover_and_load(tmp_path)
    content, error = registry.call_exporter("hangs-at-export", _sample_rows())
    assert content is None
    assert error is not None
    assert "Zeitlimit" in error


def test_hanging_file_extension_call_falls_back_to_txt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plugins_module, "PLUGIN_METADATA_CALL_TIMEOUT_SECONDS", 0.2)
    plugin_dir = tmp_path / "hangs_at_extension"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        "import time\n"
        "from genesis_core.plugins import ExporterPlugin, PluginKind\n"
        "class SlowExt(ExporterPlugin):\n"
        "    plugin_id = 'hangs-at-extension'\n"
        "    plugin_kind = PluginKind.EXPORTER\n"
        "    display_name = 'SlowExt'\n"
        "    def file_extension(self):\n"
        "        time.sleep(999)\n"
        "        return 'txt'\n"
        "    def export(self, rows): return 'x'\n"
        "PLUGIN_CLASS = SlowExt\n",
        encoding="utf-8",
    )
    registry = PluginRegistry()
    registry.discover_and_load(tmp_path)
    assert registry.safe_export_filename("hangs-at-extension") == "export.txt"


def test_run_with_timeout_returns_value_for_fast_function() -> None:
    assert plugins_module._run_with_timeout(lambda: 42, 5.0, "schneller Aufruf") == 42


def test_run_with_timeout_reraises_exception_from_function() -> None:
    def _boom():
        raise ValueError("kaputt")

    with pytest.raises(ValueError, match="kaputt"):
        plugins_module._run_with_timeout(_boom, 5.0, "werfender Aufruf")
