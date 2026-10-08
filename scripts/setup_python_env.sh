#!/usr/bin/env bash
# Richtet die Python-Umgebung für den GENESIS Core Service ein.
# Muss ggf. zu Beginn JEDER neuen Sandbox-Sitzung erneut ausgeführt werden,
# da installierte Pakete laut Sandbox-Regeln nicht Teil des Workspace-Snapshots
# sind (siehe PROGRESS.md "Ressourcen-Disziplin").
set -euo pipefail
cd "$(dirname "$0")/.."

echo ">>> Installiere Python-Abhängigkeiten für core/ ..."
sudo pip install --quiet --disable-pip-version-check --break-system-packages -r core/requirements.txt

echo ">>> Installiere Python-Abhängigkeiten für ui-reference-pyside/ (PySide6, httpx) ..."
sudo pip install --quiet --disable-pip-version-check --break-system-packages -r ui-reference-pyside/requirements.txt

echo ">>> Prüfe Qt-Systembibliothek libxkbcommon (von PySide6 zur Laufzeit benötigt,
    auch im QT_QPA_PLATFORM=offscreen-Modus) ..."
if ! ldconfig -p | grep -q libxkbcommon.so.0; then
  echo "libxkbcommon fehlt, installiere via apt (Deep-Review-Fund, Sitzung 11 ..."
  echo "Fortsetzung: PySide6-Tests schlugen mit ImportError ohne diese System-"
  echo "bibliothek fehl, obwohl das Python-Paket selbst installiert war) ..."
  sudo apt-get update -qq && sudo apt-get install -y -qq libxkbcommon0 libxkbcommon-x11-0
fi

echo ">>> Prüfe FFmpeg/FFprobe ..."
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg fehlt, installiere via apt ..."
  sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg sqlite3
fi
ffmpeg -version | head -1
ffprobe -version | head -1

echo ">>> Prüfe Chromaprint (fpcalc, Audio-Fingerprinting §12/§13) ..."
if ! command -v fpcalc >/dev/null 2>&1; then
  echo "fpcalc fehlt, installiere via apt (libchromaprint-tools, LGPL-2.1) ..."
  sudo apt-get update -qq && sudo apt-get install -y -qq libchromaprint-tools
fi
fpcalc -version

echo ">>> Fertig. Core-Umgebung einsatzbereit."
