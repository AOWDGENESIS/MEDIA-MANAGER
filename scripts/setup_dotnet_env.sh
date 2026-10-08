#!/usr/bin/env bash
# Installiert das .NET SDK in der Sandbox, damit das WPF-Referenzprojekt
# (ui-windows-dotnet/) zumindest KOMPILIERT werden kann (nicht ausgefuehrt -
# WPF-Runtime gibt es nur unter Windows). Siehe DECISIONS.md ADR-0008.
#
# Muss ggf. zu Beginn JEDER neuen Sandbox-Sitzung erneut ausgefuehrt werden,
# da ~/.dotnet nicht Teil des Workspace-Snapshots ist (siehe PROGRESS.md
# "Ressourcen-Disziplin").
set -euo pipefail

DOTNET_DIR="$HOME/.dotnet"

if [ ! -x "$DOTNET_DIR/dotnet" ]; then
  echo ">>> Installiere .NET SDK 8.0 nach $DOTNET_DIR ..."
  curl -sSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh
  bash /tmp/dotnet-install.sh --channel 8.0 --install-dir "$DOTNET_DIR"
else
  echo ">>> .NET SDK bereits unter $DOTNET_DIR vorhanden."
fi

export PATH="$PATH:$DOTNET_DIR"
dotnet --version

echo ""
echo ">>> Kompiliert wird mit: dotnet build -p:EnableWindowsTargeting=true"
echo "    (noetig, weil das Projekt net8.0-windows/UseWPF=true verwendet -"
echo "    das erlaubt NUR die Kompilierprobe auf Linux, nicht das Ausfuehren.)"
echo ""
echo ">>> Beispiel:"
echo "    cd \"$(dirname "$0")/../ui-windows-dotnet/GenesisMediaManager.Client\""
echo "    dotnet build -p:EnableWindowsTargeting=true"
