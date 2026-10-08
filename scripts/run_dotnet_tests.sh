#!/usr/bin/env bash
# Baut den WPF-Client (Release, win-x64) und fuehrt die komplette
# Logik-Testsuite (GenesisMediaManager.Client.Tests) aus.
#
# WICHTIGER HINWEIS (siehe auch PROGRESS.md "Fortsetzung 23" und
# TEST_REPORT.md): Dieses Skript prueft NUR kompilierbaren C#/XAML-Code
# und reine Logik-Tests. Es kann und will KEIN echtes visuelles
# WPF-Rendering pruefen - das ist auf Nicht-Windows-Systemen (z.B. Linux-
# CI/Sandboxes ohne DWM/DirectX) technisch unmoeglich. Fuer eine
# verbindliche visuelle Abnahme des Dark-Themes muss die App auf einem
# echten Windows-Rechner gestartet und manuell/mit einem UI-Automatisierungs-
# Tool (z.B. WinAppDriver, Appium.WindowsDriver) geprueft werden.
set -euo pipefail
cd "$(dirname "$0")/.."

echo ">>> Baue GenesisMediaManager.Client (Release, win-x64, WarningLevel=9) ..."
cd ui-windows-dotnet/GenesisMediaManager.Client
dotnet build -c Release -p:EnableWindowsTargeting=true -r win-x64 -p:WarningLevel=9
cd ..

echo ">>> Fuehre GenesisMediaManager.Client.Tests aus (reine Logik-Tests) ..."
cd GenesisMediaManager.Client.Tests
dotnet test -c Release -p:WarningLevel=9
