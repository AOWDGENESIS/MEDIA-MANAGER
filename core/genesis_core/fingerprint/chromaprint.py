"""Duenner, sicherer Wrapper um die `fpcalc`-CLI (Chromaprint).

Prinzipien:
- Kein `shell=True`, keine String-Interpolation eines Dateipfads in einen
  Shell-Befehl (Injection-Vermeidung) - `subprocess.run` bekommt eine
  Argumentliste.
- Klare, deutschsprachige Fehlermeldungen statt rohem Stacktrace (§37) -
  `compute_fingerprint` wirft niemals eine rohe `subprocess`-Exception,
  sondern immer `FingerprintError` mit verstaendlichem Text, oder liefert
  ein `FingerprintResult`.
- Timeout, damit ein haengender Subprozess nicht die gesamte App blockiert.
"""
from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
from pathlib import Path

from genesis_core.logutil import get_logger

log = get_logger("Fingerprint")

DEFAULT_TIMEOUT_SECONDS = 30.0


class FingerprintError(RuntimeError):
    """Wird geworfen, wenn kein Fingerprint erzeugt werden konnte - z.B. weil
    `fpcalc` fehlt, die Datei kein gueltiges Audio enthaelt, oder der
    Vorgang das Timeout ueberschritten hat. Der Aufrufer soll dies als
    "Fingerprint nicht verfuegbar" behandeln, NICHT als App-Absturz."""


@dataclasses.dataclass
class FingerprintResult:
    algorithm: str
    fingerprint_data: str
    duration_seconds: float


def is_fpcalc_available() -> bool:
    return shutil.which("fpcalc") is not None


def compute_fingerprint(
    path: str | Path, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
) -> FingerprintResult:
    """Berechnet den Chromaprint-Fingerabdruck einer Audiodatei.

    Wirft `FingerprintError` bei jedem Fehlschlag (fehlendes fpcalc, Timeout,
    kein gueltiges Audio, o.ae.) - niemals eine rohe Exception.
    """
    path = Path(path)
    if not is_fpcalc_available():
        raise FingerprintError(
            "Chromaprint (fpcalc) ist nicht installiert - Fingerprinting nicht "
            "verfuegbar. Siehe scripts/setup_python_env.sh."
        )
    if not path.exists():
        raise FingerprintError(f"Datei nicht gefunden: {path}")

    try:
        proc = subprocess.run(
            ["fpcalc", "-json", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FingerprintError(
            f"Fingerprint-Berechnung fuer {path.name} hat das Zeitlimit "
            f"({timeout_seconds}s) ueberschritten."
        ) from exc
    except OSError as exc:
        raise FingerprintError(f"fpcalc konnte nicht gestartet werden: {exc}") from exc

    if proc.returncode != 0:
        raise FingerprintError(
            f"fpcalc konnte {path.name} nicht verarbeiten "
            f"(Exit-Code {proc.returncode}): {proc.stderr.strip()}"
        )

    try:
        data = json.loads(proc.stdout)
        fingerprint = data["fingerprint"]
        duration = float(data["duration"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise FingerprintError(
            f"fpcalc-Ausgabe fuer {path.name} konnte nicht gelesen werden: {exc}"
        ) from exc

    log.info("Fingerprint berechnet: %s (%.1fs)", path.name, duration)
    return FingerprintResult(
        algorithm="chromaprint", fingerprint_data=fingerprint, duration_seconds=duration
    )
