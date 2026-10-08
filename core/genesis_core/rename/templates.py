"""Sichere Platzhalter-Vorlagen fuer das Umbenennen von Mediendateien (§15).

Kein `eval`/`exec` - Templates werden ausschliesslich ueber
`str.format_map` mit einer kontrollierten Platzhalterliste aufgeloest.
Werte werden VOR dem Einsetzen dateisystemsicher bereinigt (verbotene
Zeichen, reservierte Windows-Namen, Laengenbegrenzung), damit ein Tag-Wert
(z.B. ein Interpretenname mit einem "/" oder ":") niemals ungewollt einen
zusaetzlichen Ordner erzeugt oder einen ungueltigen Dateinamen produziert.
"""
from __future__ import annotations

import string

FORBIDDEN_CHARS = '<>:"/\\|?*'
_CONTROL_CHARS = "".join(chr(c) for c in range(32))
_RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
MAX_COMPONENT_LENGTH = 180  # konservativ unterhalb typischer 255-Zeichen-Limits


class RenameTemplateError(RuntimeError):
    """Vorlage konnte fuer eine bestimmte Datei nicht (sicher) aufgeloest
    werden - z.B. fehlender Platzhalter oder ungueltiger Format-Spezifizierer."""


def sanitize_filename_component(value: str) -> str:
    """Macht einen einzelnen String dateisystemsicher (fuer EINE
    Pfadkomponente, nicht fuer einen ganzen Pfad mit Trennzeichen)."""
    if value is None:
        return ""
    cleaned = "".join(
        " " if ch in FORBIDDEN_CHARS or ch in _CONTROL_CHARS else ch for ch in str(value)
    )
    cleaned = " ".join(cleaned.split())  # mehrfache Leerzeichen normalisieren
    cleaned = cleaned.strip().rstrip(". ")  # Windows mag keine trailing dots/spaces
    if not cleaned:
        return ""
    if cleaned.upper() in _RESERVED_WINDOWS_NAMES:
        cleaned = f"_{cleaned}"
    if len(cleaned) > MAX_COMPONENT_LENGTH:
        cleaned = cleaned[:MAX_COMPONENT_LENGTH].rstrip()
    return cleaned


class _SafeFormatDict(dict):
    def __missing__(self, key):
        raise RenameTemplateError(
            f"Die Vorlage verwendet den Platzhalter '{{{key}}}', den es fuer "
            "dieses Medium nicht gibt (siehe verfuegbare Platzhalter in der "
            "Dokumentation)."
        )


class _EmptyAwareFormatter(string.Formatter):
    """Wendet numerische Format-Spezifizierer (z.B. ``:02d``) nur an, wenn
    fuer diese Datei tatsaechlich ein Wert vorhanden ist. Ist das Feld leer
    (Prinzip #16 - keine Fantasiedaten), wird es unabhaengig vom Format-Spec
    zu einem leeren String, statt einen verwirrenden ``ValueError`` ueber
    "Unknown format code 'd' for object of type 'str'" zu werfen."""

    def format_field(self, value, format_spec):
        if value == "" and format_spec:
            return ""
        try:
            return format(value, format_spec)
        except (ValueError, TypeError) as exc:
            raise RenameTemplateError(
                f"Ungueltiger Format-Spezifizierer '{format_spec}' fuer Wert "
                f"{value!r}: {exc}"
            ) from exc


def referenced_placeholder_names(template: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in string.Formatter().parse(template)
        if field_name
    }


def render_template(template: str, context: dict) -> tuple[str, list[str]]:
    """Rendert eine Vorlage gegen einen Kontext aus Rohwerten (koennen
    ``None``, ``str`` oder ``int`` sein).

    Liefert (gerenderter_string, liste_leerer_platzhalter). Leere/fehlende
    Werte werden NICHT als Platzhaltertext wie "Unknown" fantasiert
    (Prinzip #16) - sie werden zu einem leeren String, UND zusaetzlich in der
    zurueckgegebenen Liste vermerkt, damit die aufrufende Stelle den Nutzer
    warnen kann ("Feld 'jahr' ist bei dieser Datei leer").
    """
    used_fields = referenced_placeholder_names(template)
    empty_fields: list[str] = []
    safe_context: dict[str, object] = {}

    for key in used_fields:
        # WICHTIG: `key not in context` (unbekannter Platzhaltername) ist ein
        # anderer Fall als "Platzhalter bekannt, aber Wert fuer DIESE Datei
        # leer" (context[key] is None). Der Aufrufer muss deshalb IMMER alle
        # bekannten Platzhalternamen im Kontext-Dict fuehren (Wert ggf.
        # None), damit diese Unterscheidung funktioniert.
        if key not in context:
            raise RenameTemplateError(
                f"Die Vorlage verwendet den unbekannten Platzhalter '{{{key}}}'."
            )
        raw_value = context[key]
        if raw_value is None or raw_value == "":
            empty_fields.append(key)
            safe_context[key] = ""
        elif isinstance(raw_value, int):
            safe_context[key] = raw_value  # numerische Format-Specs (z.B. :02d) erhalten
        else:
            safe_context[key] = sanitize_filename_component(str(raw_value))

    try:
        rendered = _EmptyAwareFormatter().vformat(
            template, (), _SafeFormatDict(safe_context)
        )
    except (ValueError, IndexError, TypeError) as exc:
        raise RenameTemplateError(f"Vorlage ist ungueltig: {exc}") from exc

    # Deep-Review-Fund (Sitzung 3, kleinere Haertung): Ist z.B. `{ext}` fuer
    # eine original-endungslose Datei leer, kann der gerenderte Name auf
    # einen Punkt/Leerzeichen enden (z.B. "Titel." statt "Titel"). Windows
    # erlaubt das technisch nicht zuverlaessig (wird beim Erstellen
    # stillschweigend entfernt/normalisiert) - genau dieselbe Regel wie
    # `sanitize_filename_component` bereits PRO Platzhalterwert anwendet,
    # hier zusaetzlich auf den GESAMTEN gerenderten Dateinamen angewendet.
    rendered = rendered.rstrip(". ")

    return rendered, empty_fields
