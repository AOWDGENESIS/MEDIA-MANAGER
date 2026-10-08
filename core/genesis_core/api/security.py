"""Authentifizierung der lokalen REST-API (Deep Review Sitzung 2, ADR-0006).

HINTERGRUND / GEFUNDENES PROBLEM:
Die Core-API bindet ausschliesslich an 127.0.0.1 - das schuetzt NICHT vor
sogenannten "Drive-by-Localhost"-/JSON-CSRF-Angriffen: jede Webseite, die im
Browser des Nutzers offen ist, kann waehrend GENESIS laeuft per JavaScript
eine Anfrage an http://127.0.0.1:<port> senden. Browser-CORS-Regeln
verhindern zwar, dass die fremde Seite die ANTWORT lesen kann, nicht aber,
dass die Anfrage beim Server ankommt und dort Seiteneffekte ausloest
("blinde" CSRF). Da kuenftige Endpunkte (Umbenennen, Loeschen, Download)
genau solche Seiteneffekte haben werden, WIDERSPRICHT ein unauthentifizierter
Endpunkt dem Sicherheitsmodell (§44: "Aenderung = Benutzerbestaetigung") -
denn eine fremde Webseite hat nie eine Benutzerbestaetigung eingeholt.

LOESUNG: Ein pro Installation einmalig erzeugtes, zufaelliges Shared-Secret-
Token wird in einer Datei mit restriktiven Dateirechten (0600, nur Owner)
im GENESIS-Datenverzeichnis abgelegt. Nur lokale Prozesse, die als derselbe
Betriebssystem-Benutzer laufen (also: unsere eigenen UI-Clients), koennen
diese Datei lesen - eine Webseite im Browser kann das nicht. Jede
schreibende/analysierende Anfrage MUSS den Header `X-Genesis-Token` mit
diesem Wert mitschicken. `/health` bleibt bewusst oeffentlich (uebliche
Praxis fuer reine Liveness-Checks, keine sensiblen/aendernden Daten).
"""
from __future__ import annotations

import hmac
import secrets
import stat
from pathlib import Path

from fastapi import Header, HTTPException

TOKEN_FILENAME = "api_token.txt"


def load_or_create_token(data_dir: Path) -> str:
    token_path = Path(data_dir) / TOKEN_FILENAME
    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token, encoding="utf-8")
    try:
        # Nur fuer den Besitzer lesbar/schreibbar (POSIX). Unter Windows
        # greift stattdessen der ACL-Schutz des Benutzerprofilordners
        # (%APPDATA%) - dort ist ein zusaetzliches chmod wirkungslos, aber
        # auch nicht schaedlich.
        token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # z.B. auf Dateisystemen ohne POSIX-Rechte - kein harter Fehler
    return token


def make_token_dependency(expected_token: str):
    """Erzeugt eine FastAPI-Dependency, die den Header `X-Genesis-Token`
    gegen das erwartete Token prueft (konstante Vergleichszeit gegen
    Timing-Angriffe via hmac.compare_digest)."""

    def _verify(x_genesis_token: str | None = Header(default=None)) -> None:
        if not x_genesis_token or not hmac.compare_digest(x_genesis_token, expected_token):
            raise HTTPException(
                status_code=401,
                detail=(
                    "Fehlendes oder ungueltiges API-Token (Header X-Genesis-Token). "
                    "Die lokale GENESIS-API erfordert Authentifizierung, um "
                    "Cross-Site-/Drive-by-Localhost-Anfragen abzuwehren (ADR-0006)."
                ),
            )

    return _verify
