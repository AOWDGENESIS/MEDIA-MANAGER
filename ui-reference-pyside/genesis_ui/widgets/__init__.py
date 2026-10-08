"""Kleine, wiederverwendbare Hilfsbausteine fuer die PySide6-Referenz-UI.

`set_plain_text()` entstand als direkter Fix aus dem Deep-Review-Pass
Sitzung 11 (siehe `docs/REVIEW_LOG.md`, Finding zu `QLabel`-Rich-Text-
Autoerkennung): `QLabel.setText()` nutzt standardmaessig `Qt.AutoText` und
interpretiert einen String als HTML/Rich-Text, SOBALD er wie Markup
aussieht (`Qt.mightBeRichText()`-Heuristik, z.B. ein Text, der mit `<`
beginnt). Das betrifft in GENESIS konkret jeden Text, der NICHT vom
Entwickler selbst stammt, sondern aus einer potenziell externen/
unzuverlaessigen Quelle gelesen wird - z.B. ein KI-generierter
Metadatenvorschlag (§25, dessen Eingabekontext u.a. den Dateinamen
enthaelt - ein Nutzer koennte absichtlich oder versehentlich eine Datei
mit HTML-aehnlichem Namen ablegen), eine Fehlermeldung/technische Details
aus dem Fehler-Center (§37), ein Plugin-`display_name`/`load_error` (§34,
Plugin-Code gilt grundsaetzlich als nicht vertrauenswuerdig) oder ein
Job-`current_item`-Dateipfad (§35/§36).

Es handelt sich NICHT um eine Remote-Code-Execution-Luecke (Qt-Rich-Text
ist ein stark eingeschraenktes HTML-Subset ohne JavaScript) - aber ohne
diesen Fix koennte ein entsprechend praeparierter String die Darstellung
verfaelschen (z.B. Teile des Textes verschwinden lassen, Formatierung
vortaeuschen). `set_plain_text()` erzwingt `Qt.PlainText`, womit die
Heuristik nie greift - der Text wird IMMER exakt so angezeigt, wie er im
Datenmodell steht."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


def set_plain_text(label: QLabel, text: str) -> None:
    """Setzt `text` auf `label`, erzwingt dabei `Qt.PlainText` - zu
    verwenden ueberall dort, wo der angezeigte String NICHT eine fest im
    Quellcode stehende, uebersetzte UI-Beschriftung ist, sondern aus Core-
    API-Antworten, Dateinamen/-pfaden, Plugin-Code oder KI-Ausgaben
    stammt (siehe Moduldocstring)."""
    label.setTextFormat(Qt.PlainText)
    label.setText(text)


def escape_mnemonic(text: str) -> str:
    """Verdoppelt jedes `&` in `text`.

    Zweiter, eigenstaendiger Fund desselben Deep-Review-Passes (Sitzung
    11): `QAbstractButton`-Text (QPushButton/QCheckBox/QRadioButton) UND
    `QGroupBox`-Titel interpretieren ein einzelnes `&` als Mnemonic-
    Markierung fuer das NAECHSTE Zeichen (z.B. zeigt `&Speichern` ein
    unterstrichenes "S" und bindet Alt+S als Tastenkuerzel). Das ist bei
    fest im Quellcode stehenden, uebersetzten Beschriftungen gewollt -
    wird aber zu einem konkreten, reproduzierbaren Darstellungsfehler,
    sobald echte Musik-/Film-/Hoerbuchmetadaten in so einem Text landen:
    `&`-Zeichen sind im echten Bibliotheksbestand haeufig ("Simon &
    Garfunkel", "AC/DC", "Earth, Wind & Fire", "Dungeons & Dragons"-
    Hoerbuecher) - ohne diesen Fix wuerde z.B. ein KI-Metadatenvorschlag
    mit dem Wert "Rock & Pop" als Checkbox-Text faelschlich "Rock Pop"
    mit unterstrichenem P anzeigen und Alt+P als ungewollte Tastatur-
    Abkuerzung fuer diese Checkbox registrieren."""
    return text.replace("&", "&&")


__all__ = ["escape_mnemonic", "set_plain_text"]

