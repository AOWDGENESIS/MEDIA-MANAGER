"""Gemeinsame Typen/Interface fuer Download-/Import-Provider (§30-§32).

Architektur (analog zu genesis_core.providers fuer Metadaten und
genesis_core.voice fuer TTS - austauschbare Provider hinter einer schmalen
Schnittstelle, Prinzip "Provider muessen austauschbar sein", §30):

    URL/Pfad -> detect_provider() -> DownloadProvider
                                        .check_availability()  (nur lesend)
                                        .fetch_metadata()       (nur lesend)
                                        .list_options()         (nur lesend)
                                        .download()             (SCHREIBT,
                                                                  braucht
                                                                  confirm=True
                                                                  auf API-Ebene)

WICHTIG (§30, harte Grenze - niemals aufweichen):
  - Kein Provider darf DRM-Schutzmechanismen umgehen. Dienste, die ein
    rechtmaessiges, nicht-DRM-umgehendes Herunterladen nicht zulassen
    (Spotify, Audible, Pocket FM), werden als NICHT VERFUEGBAR erkannt und
    gemeldet (siehe drm_blocked.py) - es wird niemals versucht, das zu
    "loesen".
  - Kein Provider speichert Zugangsdaten/Cookies. Oeffentlich erreichbare
    Inhalte werden ohne Login abgerufen; Dienste, die zwingend ein Login
    voraussetzen, fallen unter obigen Punkt.
"""
from __future__ import annotations

import abc
import dataclasses
from pathlib import Path


class DownloadError(RuntimeError):
    """Allgemeiner Fehler waehrend Erkennung/Pruefung/Download (z.B.
    Netzwerkfehler, nicht erreichbare URL) - KEIN stiller Fehlschlag
    (Prinzip "structured error handling")."""


class DownloadNotPermittedError(DownloadError):
    """Wird erhoben, wenn ein Dienst keinen zulaessigen (nicht-DRM-
    umgehenden) Download ermoeglicht (§30). Dies ist ein ERWARTETES,
    sauber gemeldetes Ergebnis - kein Bug."""


class ConfirmationRequiredError(PermissionError):
    """Download/Import wurde ohne confirm=True angefordert (Prinzip #6:
    Aenderungen/Downloads erfordern eine explizite Bestaetigung)."""


class ProviderNotFoundError(DownloadError):
    """Keine registrierte Quelle erkennt die angegebene URL/den Pfad."""


@dataclasses.dataclass
class AvailabilityResult:
    """Ergebnis der Verfuegbarkeitspruefung (§31 Schritt "Verfuegbarkeit
    pruefen"). `available=False` ist ein vollkommen normales, zu meldendes
    Ergebnis (z.B. DRM-geschuetzter Dienst, offline, 404)."""

    available: bool
    reason: str | None = None
    requires_login: bool = False


@dataclasses.dataclass
class SourceMetadata:
    """Vorschau-Metadaten vor dem eigentlichen Download (§31 Schritt
    "Metadaten abrufen") - rein informativ, veraendert nichts."""

    title: str | None = None
    description: str | None = None
    duration_seconds: float | None = None
    uploader: str | None = None
    thumbnail_url: str | None = None
    original_id: str | None = None
    license: str | None = None
    extra: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class DownloadOption:
    """Eine moegliche Download-Variante (§31 Schritt "Downloadoptionen
    anzeigen"), z.B. verschiedene Qualitaeten/Formate."""

    option_id: str
    label: str
    file_extension: str
    approx_size_bytes: int | None = None
    quality_note: str | None = None


@dataclasses.dataclass
class DownloadedFile:
    """Ergebnis eines tatsaechlich ausgefuehrten Downloads."""

    path: Path
    original_id: str | None = None
    suggested_title: str | None = None


class DownloadProvider(abc.ABC):
    """Interface, das jeder Download-/Import-Adapter implementiert."""

    provider_id: str = "base"
    display_name: str = "Basis-Provider"
    requires_internet: bool = True

    @abc.abstractmethod
    def matches(self, url: str) -> bool:
        """Erkennt, ob dieser Provider fuer die angegebene URL/den Pfad
        zustaendig ist (§31 Schritt "Quelle erkennen")."""

    @abc.abstractmethod
    def check_availability(self, url: str) -> AvailabilityResult:
        """Rein lesende Pruefung, ob ein zulaessiger Download moeglich ist."""

    @abc.abstractmethod
    def fetch_metadata(self, url: str) -> SourceMetadata:
        """Rein lesender Metadaten-Abruf fuer die Vorschau."""

    def list_options(self, url: str) -> list[DownloadOption]:
        """Standardmaessig genau eine Option ("Original"). Provider mit
        mehreren Qualitaetsstufen (z.B. YouTube) ueberschreiben dies."""
        return [
            DownloadOption(option_id="default", label="Original", file_extension="")
        ]

    @abc.abstractmethod
    def download(self, url: str, option_id: str, dest_dir: Path) -> DownloadedFile:
        """Fuehrt den eigentlichen Download/Import aus. Darf NUR von der
        Download-Engine nach erfolgreicher confirm=True-Pruefung aufgerufen
        werden (§31 Schritt "Benutzer bestaetigt" -> "Download")."""
