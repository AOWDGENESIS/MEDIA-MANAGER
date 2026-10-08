"""Plugin-System (§34, §48/§49).

Erlaubt, GENESIS um zusaetzliche Metadaten-/Fingerprint-/Downloader-/
TTS-/KI-/Artwork-/DB-/Exporter-/Importer-/Konverter-Erweiterungen zu
ergaenzen, OHNE den Host instabil zu machen (§34: "Plugins duerfen die
Hauptanwendung nicht destabilisieren koennen").

Sandboxing-Strategie dieser ersten Version (bewusst einfach und
nachvollziehbar gehalten statt eines vollen Prozess-/Betriebssystem-
Sandbox, der auf allen drei Zielplattformen Admin-Rechte oder komplexe
Zusatzinfrastruktur braeuchte - siehe §52 "kein Admin-Zwang"):

1. Jedes Plugin lebt in einem EIGENEN Unterordner unter dem
   Plugin-Verzeichnis (`settings.paths.data_dir / "plugins"`) mit genau
   einer `plugin.py`-Datei, die ein Modul-Attribut `PLUGIN_CLASS`
   (Referenz auf eine `PluginBase`-Unterklasse) bereitstellen MUSS.
2. Laden (Import + Instanziierung + Validierung) geschieht IMMER in einem
   try/except-Block, der JEDE Exception abfaengt - Syntaxfehler, fehlende
   Abhaengigkeiten, fehlerhafte Pflichtattribute, eine Exception direkt
   im Konstruktor. Ein fehlerhaftes Plugin fuehrt NIEMALS zum Absturz des
   Hosts oder zum Abbruch des Ladevorgangs der UEBRIGEN Plugins - es
   landet lediglich mit einem `load_error` in der Registry (sichtbar im
   Diagnostics-Bildschirm, §38) und bleibt inaktiv. ZUSAETZLICH (Deep-
   Review-Fund, Sitzung 11) laeuft der komplette Lade-Vorgang mit einem
   Zeitlimit (`PLUGIN_LOAD_TIMEOUT_SECONDS`, siehe `_run_with_timeout`):
   ein Plugin, das statt einer Exception stattdessen HAENGT (Endlosschleife,
   blockierender Aufruf ohne eigenes Timeout), blockierte zuvor nachweislich
   den gesamten Core-Service-Start auf unbestimmte Zeit - eine Exception
   allein reicht als Schutz also NICHT aus.
3. Jeder Plugin-Methodenaufruf zur LAUFZEIT (z.B. `ExporterPlugin.export`,
   `file_extension`) wird ebenfalls vom Aufrufer in einem try/except UND
   mit demselben Zeitlimit-Mechanismus umschlossen (siehe
   `PluginRegistry.call_exporter`/`safe_export_filename`) - ein zur
   Ladezeit einwandfreies Plugin, das erst bei einem SPAETEREN Aufruf
   eine Exception wirft ODER haengt, darf den aufrufenden Host-Workflow
   ebenso wenig zum Absturz/Einfrieren bringen.
4. Eine ECHTE Betriebssystem-Sandbox (separater Prozess/eingeschraenkte
   Rechte) ist als Haertungs-Backlog-Punkt dokumentiert (siehe
   PROGRESS.md) - fuer die Phase-9-Zielsetzung ("Plugins duerfen den Host
   nicht destabilisieren") reicht die hier umgesetzte Fehlerisolierung
   auf Python-Ebene aus und deckt den in der Spezifikation explizit
   geforderten Beweis ("absichtlich fehlerhaftes Test-Plugin") ab.

Zwei mitgelieferte Beispiel-Plugins (siehe `genesis_core/plugins/
examples/`) dienen gleichzeitig als lebende Dokumentation UND als
Testgrundlage fuer genau diese Stabilitaetsgarantie:
- `examples/example_exporter/plugin.py`  - ein funktionierendes,
  tatsaechlich nutzbares Pipe-separated-values-Export-Plugin.
- `examples/broken_example/plugin.py`    - wirft absichtlich eine
  Exception beim Import, um zu beweisen, dass der Host dadurch NICHT
  destabilisiert wird.
"""
from __future__ import annotations

import dataclasses
import enum
import importlib.util
import sys
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from genesis_core.logutil import get_logger

log = get_logger("Plugins")

T = TypeVar("T")

# Deep-Review-Fund (Sitzung 11, Abgleich gegen ADR-0020-Zusagen): der
# bisherige try/except-Schutz faengt nur EXCEPTIONS ab - ein Plugin, das
# beim Laden ODER beim Aufruf stattdessen haengt (Endlosschleife, ein
# blockierender Netzwerk-/Dateisystemaufruf ohne eigenes Timeout), wurde
# dadurch NICHT erkannt und blockierte reproduzierbar (siehe
# test_plugins.py::test_hanging_plugin_at_load_time_does_not_block_host)
# den kompletten Ladevorgang - bei `discover_and_load` beim Core-Service-
# Start sogar den Start der GESAMTEN Anwendung auf unbestimmte Zeit. Das
# ist ein staerkerer Verstoss gegen §34 ("Plugins duerfen die
# Hauptanwendung nicht destabilisieren koennen") als eine blosse
# Exception, und faellt ausdruecklich noch in das von ADR-0020 selbst
# beschriebene Bedrohungsmodell ("eigene/Community-Plugins mit
# Programmierfehlern", nicht erst boeswilliger Code - eine Endlosschleife
# ist ein klassischer, harmloser Programmierfehler, kein Angriff).
#
# Fix: Laden UND jeder Laufzeitaufruf eines Plugins laufen jetzt in einem
# eigenen Worker-Thread mit Zeitlimit (`_run_with_timeout`). Nach
# Ueberschreiten des Limits gibt die Funktion sofort mit einem klaren
# Fehler zurueck, die Hauptanwendung bleibt bedienbar - der haengende
# Hintergrund-Thread selbst kann in Python nicht hart beendet werden und
# laeuft im schlimmsten Fall bis Prozessende im Hintergrund weiter (siehe
# Docstring von `_run_with_timeout`). Das ist eine bewusst unvollstaendige,
# aber klar dokumentierte Verbesserung - eine vollstaendige Loesung
# (Prozess- statt Thread-Isolation mit hartem `terminate()`) ist Teil des
# bereits in Entscheidung 1/PROGRESS.md dokumentierten "echte OS-Sandbox"-
# Backlogs und wuerde eine Cross-Prozess-Schnittstelle fuer alle
# Plugin-Kategorien erfordern - eine groessere Architekturaenderung, die
# hier bewusst NICHT nebenbei mitgezogen wird.
PLUGIN_LOAD_TIMEOUT_SECONDS = 10.0
PLUGIN_CALL_TIMEOUT_SECONDS = 60.0
# file_extension() soll laut Schnittstelle ein triviales, sofortiges
# Literal zurueckgeben - 5s sind grosszuegig genug fuer legitime Plugins,
# begrenzen aber einen haengenden Aufruf deutlich straffer als export().
PLUGIN_METADATA_CALL_TIMEOUT_SECONDS = 5.0


class PluginTimeoutError(RuntimeError):
    """Ein Plugin hat beim Laden oder bei einem Methodenaufruf das
    Zeitlimit ueberschritten - vermutlich eine Endlosschleife oder ein
    blockierender Aufruf ohne eigenes Timeout. Wird wie jede andere
    Plugin-Exception als `load_error`/Aufruf-Fehler behandelt, nie als
    Absturz des Hosts."""


def _run_with_timeout(fn: Callable[[], T], timeout_seconds: float, description: str) -> T:
    """Fuehrt `fn` in einem separaten Thread aus und erzwingt ein
    Zeitlimit. Python kann einen Thread nicht sicher von aussen
    terminieren - bei Ueberschreitung des Limits kehrt diese Funktion
    trotzdem sofort zurueck (der Aufrufer/Host bleibt reaktionsfaehig);
    der haengende Thread selbst laeuft im Hintergrund weiter, bis er von
    selbst endet oder der Prozess beendet wird. Das ist der entscheidende
    Unterschied zum vorherigen Verhalten (unbegrenztes Haengenbleiben DES
    AUFRUFERS, siehe Modul-Kommentar oben).

    BEWUSST `threading.Thread(daemon=True)` statt `concurrent.futures.
    ThreadPoolExecutor`: dessen Worker-Threads sind NICHT daemonisch - ein
    fuer immer haengender Worker wuerde dann sogar einen sauberen Shutdown
    des GESAMTEN Core-Service-Prozesses verhindern (von Python selbst beim
    Interpreter-Exit erzwungenes Warten auf alle Nicht-Daemon-Threads,
    empirisch verifiziert waehrend dieser Sitzung). Ein Daemon-Thread
    verhindert das nicht - der Host bleibt in jedem Fall sauber
    herunterfahrbar, auch mit einem fuer immer haengenden Plugin-Rest im
    Hintergrund."""
    result: dict[str, Any] = {}

    def _runner() -> None:
        try:
            result["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - wird im Aufrufer-Thread erneut ausgeloest
            result["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True, name=f"genesis-plugin-{description[:40]}")
    thread.start()
    thread.join(timeout=timeout_seconds)
    if thread.is_alive():
        raise PluginTimeoutError(
            f"{description} ueberschritt das Zeitlimit von {timeout_seconds:.0f}s - "
            "moeglicherweise eine Endlosschleife oder ein blockierender Aufruf "
            "ohne eigenes Timeout im Plugin."
        )
    if "error" in result:
        raise result["error"]
    return result["value"]


class PluginKind(str, enum.Enum):
    """Alle in §34 genannten Plugin-Kategorien. Nicht jede Kategorie hat in
    dieser ersten Version bereits eine voll ausgearbeitete, eigene
    Schnittstelle (siehe Moduldocstring/PROGRESS.md Backlog) - die Liste
    existiert trotzdem vollstaendig, damit Registry/Diagnostics/UI von
    Anfang an alle Kategorien einheitlich benennen und spaetere
    Erweiterungen keine Enum-Bruchstelle verursachen."""

    METADATA = "metadata"
    FINGERPRINT = "fingerprint"
    DOWNLOADER = "downloader"
    TTS = "tts"
    AI = "ai"
    ARTWORK = "artwork"
    DB = "db"
    EXPORTER = "exporter"
    IMPORTER = "importer"
    CONVERTER = "converter"


class PluginValidationError(ValueError):
    """Ein geladenes Modul erfuellt nicht die Mindestanforderungen an ein
    GENESIS-Plugin (fehlendes `PLUGIN_CLASS`, falscher Typ, fehlende/
    ungueltige Pflichtattribute). Wird von der Registry abgefangen und als
    `load_error` gespeichert - fuehrt NIE zum Programmabbruch."""


class PluginBase:
    """Gemeinsame Basis aller Plugins. Konkrete Plugin-Kategorien (siehe
    `ExporterPlugin` unten) erweitern dies um kategorie-spezifische,
    tatsaechlich erzwungene abstrakte Methoden.

    Die hier gelisteten Klassenattribute sind PFLICHT (werden von
    `PluginRegistry._validate` geprueft) - sie liefern die nach §34/§48
    notwendige Transparenz (wer hat das Plugin geschrieben, unter welcher
    Lizenz, arbeitet es lokal/offline oder braucht es Internet) BEVOR ein
    Plugin ueberhaupt als nutzbar gilt."""

    plugin_id: str = ""
    plugin_kind: PluginKind | None = None
    display_name: str = ""
    version: str = "0.1.0"
    author: str | None = None
    license: str | None = None
    is_local: bool = True
    requires_internet: bool = False


class ExporterPlugin(PluginBase):
    """Erweitert §42 (Export) um zusaetzliche, von Nutzern/Drittanbietern
    beigesteuerte Ausgabeformate, ohne dass der Host-Exportcode selbst
    angepasst werden muss."""

    plugin_kind = PluginKind.EXPORTER

    def file_extension(self) -> str:
        raise NotImplementedError

    def export(self, rows: list) -> str:  # rows: list[genesis_core.exporter.MediaExportRow]
        raise NotImplementedError


@dataclasses.dataclass
class LoadedPlugin:
    plugin_id: str
    plugin_kind: str | None
    display_name: str
    version: str | None
    author: str | None
    license: str | None
    is_local: bool
    requires_internet: bool
    source_path: str
    instance: Any = None
    load_error: str | None = None

    @property
    def loaded_successfully(self) -> bool:
        return self.load_error is None and self.instance is not None


def _validate(instance: Any, source_path: Path) -> None:
    if not isinstance(instance, PluginBase):
        raise PluginValidationError(
            f"PLUGIN_CLASS in {source_path} erzeugt keine PluginBase-Unterklasse."
        )
    if not instance.plugin_id or not isinstance(instance.plugin_id, str):
        raise PluginValidationError(f"Plugin in {source_path} hat keine gueltige plugin_id.")
    if not isinstance(instance.plugin_kind, PluginKind):
        raise PluginValidationError(
            f"Plugin '{instance.plugin_id}' hat keine gueltige plugin_kind (PluginKind-Enum)."
        )
    if not instance.display_name:
        raise PluginValidationError(f"Plugin '{instance.plugin_id}' hat keinen display_name.")


def _load_single_plugin(plugin_dir: Path) -> LoadedPlugin:
    plugin_file = plugin_dir / "plugin.py"
    source_path = str(plugin_file)

    if not plugin_file.exists():
        return LoadedPlugin(
            plugin_id=plugin_dir.name, plugin_kind=None, display_name=plugin_dir.name,
            version=None, author=None, license=None, is_local=True, requires_internet=False,
            source_path=source_path, instance=None,
            load_error=f"Keine plugin.py in {plugin_dir} gefunden.",
        )

    # Eindeutiger Modulname (inkl. Zufallsanteil), damit zwei gleichnamige
    # Plugin-Ordner sich nicht gegenseitig im sys.modules-Cache ueberschreiben.
    module_name = f"genesis_plugin_{plugin_dir.name}_{uuid.uuid4().hex[:8]}"

    def _import_exec_instantiate_validate() -> Any:
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if spec is None or spec.loader is None:
            raise PluginValidationError(f"Konnte Modul-Spezifikation fuer {plugin_file} nicht erzeugen.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # <-- hier wuerde ein absichtlich
        # kaputtes Plugin (z.B. examples/broken_example) seine Exception
        # werfen, ODER ein haengendes Plugin das Zeitlimit ueberschreiten;
        # beides wird unten abgefangen (Exception direkt, Haenger ueber
        # `_run_with_timeout`, siehe Modul-Kommentar).

        plugin_class = getattr(module, "PLUGIN_CLASS", None)
        if plugin_class is None:
            raise PluginValidationError(
                f"{plugin_file} definiert kein Modul-Attribut PLUGIN_CLASS."
            )
        instance = plugin_class()
        _validate(instance, plugin_file)
        return instance

    try:
        try:
            instance = _run_with_timeout(
                _import_exec_instantiate_validate,
                timeout_seconds=PLUGIN_LOAD_TIMEOUT_SECONDS,
                description=f"Laden von Plugin '{plugin_dir.name}'",
            )
        finally:
            sys.modules.pop(module_name, None)
    except Exception as exc:  # noqa: BLE001 - Kernprinzip: Plugin-Fehler duerfen den Host NIE mitreissen
        log.warning("Plugin in %s konnte nicht geladen werden: %s", plugin_dir, exc)
        return LoadedPlugin(
            plugin_id=plugin_dir.name, plugin_kind=None, display_name=plugin_dir.name,
            version=None, author=None, license=None, is_local=True, requires_internet=False,
            source_path=source_path, instance=None, load_error=str(exc),
        )

    log.info("Plugin geladen: %s (%s)", instance.plugin_id, instance.plugin_kind.value)
    return LoadedPlugin(
        plugin_id=instance.plugin_id, plugin_kind=instance.plugin_kind.value,
        display_name=instance.display_name, version=instance.version,
        author=instance.author, license=instance.license, is_local=instance.is_local,
        requires_internet=instance.requires_internet, source_path=source_path,
        instance=instance, load_error=None,
    )


class PluginRegistry:
    """Haelt alle beim letzten `discover_and_load`-Aufruf gefundenen
    Plugins (sowohl erfolgreich geladene als auch fehlgeschlagene, siehe
    Moduldocstring Punkt 2)."""

    def __init__(self) -> None:
        self._plugins: dict[str, LoadedPlugin] = {}

    def discover_and_load(self, plugins_dir: str | Path) -> list[LoadedPlugin]:
        """Durchsucht `plugins_dir` nach Unterordnern mit `plugin.py` und
        laedt jeden gefundenen Kandidaten EINZELN und FEHLERISOLIERT (ein
        kaputtes Plugin verhindert nie das Laden der uebrigen)."""
        self._plugins = {}
        root = Path(plugins_dir)
        if not root.exists():
            return []

        seen_plugin_ids: set[str] = set()
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            loaded = _load_single_plugin(entry)
            if loaded.loaded_successfully and loaded.plugin_id in seen_plugin_ids:
                log.warning(
                    "Doppelte plugin_id '%s' (%s) - ignoriert, erstes Plugin bleibt aktiv.",
                    loaded.plugin_id, entry,
                )
                loaded = dataclasses.replace(
                    loaded, load_error=f"plugin_id '{loaded.plugin_id}' bereits vergeben.",
                    instance=None,
                )
            elif loaded.loaded_successfully:
                seen_plugin_ids.add(loaded.plugin_id)
            self._plugins[f"{entry.name}::{loaded.plugin_id}"] = loaded
        return self.list_plugins()

    def list_plugins(self) -> list[LoadedPlugin]:
        return list(self._plugins.values())

    def get_exporters(self) -> list[LoadedPlugin]:
        return [
            p for p in self._plugins.values()
            if p.loaded_successfully and p.plugin_kind == PluginKind.EXPORTER.value
        ]

    def find_exporter(self, plugin_id: str) -> LoadedPlugin | None:
        for p in self.get_exporters():
            if p.plugin_id == plugin_id:
                return p
        return None

    def call_exporter(self, plugin_id: str, rows: list) -> tuple[str | None, str | None]:
        """Ruft `export()` eines geladenen Exporter-Plugins SICHER auf -
        gibt `(content, error)` zurueck statt eine Exception des Plugins
        ungefangen durchzureichen (Moduldocstring Punkt 3: auch Laufzeit-
        Fehler duerfen den Host nicht mitreissen)."""
        plugin = self.find_exporter(plugin_id)
        if plugin is None:
            return None, f"Exporter-Plugin '{plugin_id}' nicht gefunden oder nicht geladen."
        try:
            content = _run_with_timeout(
                lambda: plugin.instance.export(rows),
                timeout_seconds=PLUGIN_CALL_TIMEOUT_SECONDS,
                description=f"Aufruf von export() in Plugin '{plugin_id}'",
            )
            return content, None
        except Exception as exc:  # noqa: BLE001
            log.warning("Exporter-Plugin '%s' ist beim Aufruf fehlgeschlagen: %s", plugin_id, exc)
            return None, str(exc)

    def safe_export_filename(self, plugin_id: str, base_name: str = "export") -> str:
        """Baut einen sicheren Dateinamen fuer den `Content-Disposition`-
        Header von `GET /plugins/export/{plugin_id}` (§34+§42). `file_
        extension()` ist Plugin-Code - genau wie `export()` zur Laufzeit
        NIEMALS vertrauenswuerdig behandeln (Funde beim Deep-Review-Pass,
        Sitzung 11): ein Plugin koennte theoretisch einen leeren String,
        Pfadtrenner (`/`, `..`) oder beliebig lange Werte zurueckgeben.
        Erlaubt werden deshalb ausschliesslich alphanumerische Zeichen
        (max. 10 Stück) - bei jeder Abweichung oder einer Exception im
        Plugin greift der sichere Fallback `.txt`, OHNE den Aufruf
        fehlschlagen zu lassen (dieselbe Fehlerisolierungs-Philosophie wie
        beim Laden/Aufrufen des Plugins selbst)."""
        ext = "txt"
        plugin = self.find_exporter(plugin_id)
        if plugin is not None:
            try:
                candidate = _run_with_timeout(
                    lambda: str(plugin.instance.file_extension()).strip().lstrip("."),
                    timeout_seconds=PLUGIN_METADATA_CALL_TIMEOUT_SECONDS,
                    description=f"Aufruf von file_extension() in Plugin '{plugin_id}'",
                )
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "Exporter-Plugin '%s': file_extension() fehlgeschlagen, nutze "
                    "Fallback '.txt': %s", plugin_id, exc,
                )
                candidate = ""
            if candidate and candidate.isalnum() and len(candidate) <= 10:
                ext = candidate
        return f"{base_name}.{ext}"


__all__ = [
    "ExporterPlugin",
    "LoadedPlugin",
    "PluginBase",
    "PluginKind",
    "PluginRegistry",
    "PluginTimeoutError",
    "PluginValidationError",
]
