"""Beispiel-Plugin (§34): funktionierender Exporter fuer ein einfaches
"Pipe-separated values"-Format (aehnlich CSV, aber mit `|` statt `,` als
Trenner - nuetzlich fuer Werkzeuge, die Kommas in Titeln/Interpreten nicht
zuverlaessig escapen).

Dient als lebende Dokumentation: zeigt, wie ein Drittanbieter-Plugin eine
neue Export-Variante bereitstellt, ohne den Host-Exportcode
(`genesis_core.exporter`) selbst anfassen zu muessen. Jede GENESIS-
Installation kann dieses Beispiel 1:1 als Vorlage fuer eigene
Exporter-Plugins kopieren.
"""
from __future__ import annotations

from genesis_core.plugins import ExporterPlugin, PluginKind


class PipeSeparatedExporterPlugin(ExporterPlugin):
    plugin_id = "example-pipe-separated-exporter"
    plugin_kind = PluginKind.EXPORTER
    display_name = "Pipe-Separated Values (Beispiel-Plugin)"
    version = "1.0.0"
    author = "GENESIS Media Manager Dev"
    license = "MIT (Beispiel-Code, Teil des GENESIS-Projekts)"
    is_local = True
    requires_internet = False

    def file_extension(self) -> str:
        return ".psv"

    def export(self, rows: list) -> str:
        fields = [
            "media_file_id", "absolute_path", "filename", "kind", "title",
            "artist", "album", "track_number", "year", "duration_seconds",
        ]
        lines = ["|".join(fields)]
        for r in rows:
            values = [str(getattr(r, f, "") or "") for f in fields]
            lines.append("|".join(values))
        return "\n".join(lines) + "\n"


PLUGIN_CLASS = PipeSeparatedExporterPlugin
