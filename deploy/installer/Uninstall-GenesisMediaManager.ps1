#Requires -Version 5.1
<#
.SYNOPSIS
    Deinstalliert GENESIS Media Manager (entfernt Programmdateien,
    Verknuepfungen und den Eintrag unter "Apps & Features").

.DESCRIPTION
    Die Mediathek-Datenbank und alle Einstellungen unter
    "%APPDATA%\GenesisMediaManager" werden ABSICHTLICH NICHT geloescht
    (Grundprinzip: keine stillen Datenverluste) - bei einer
    Neuinstallation stehen Bibliothek/Einstellungen danach sofort wieder
    zur Verfuegung. Wer auch diese Daten entfernen moechte, kann den
    Ordner danach manuell loeschen.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"
$InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== GENESIS Media Manager wird deinstalliert ===" -ForegroundColor Cyan

# --- Laufende Prozesse beenden (falls die App gerade offen ist) ----------
Get-Process -Name "GenesisMediaManager" -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

try {
    Get-CimInstance Win32_Process -Filter "CommandLine like '%run_api.py%'" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
} catch {
    # Win32_Process-Abfrage kann auf manchen Systemen fehlschlagen (z.B.
    # eingeschraenkte WMI-Rechte) - kein Abbruch, der Core-Service beendet
    # sich spaetestens beim naechsten Abmelden/Neustart von selbst.
}

# --- Verknuepfungen entfernen ---------------------------------------------
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\GENESIS Media Manager"
Remove-Item -Path $startMenuDir -Recurse -Force -ErrorAction SilentlyContinue

try {
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $desktopShortcut = Join-Path $desktopPath "GENESIS Media Manager.lnk"
    Remove-Item -Path $desktopShortcut -Force -ErrorAction SilentlyContinue
} catch { }

Write-Host "    Verknuepfungen entfernt" -ForegroundColor Green

# --- Registry-Eintrag entfernen -------------------------------------------
Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\GenesisMediaManager" `
    -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "    Eintrag unter 'Apps & Features' entfernt" -ForegroundColor Green

Write-Host ""
Write-Host "Hinweis: Mediathek-Daten/Einstellungen unter" -ForegroundColor Yellow
Write-Host "'$env:APPDATA\GenesisMediaManager' bleiben erhalten (nicht geloescht)." -ForegroundColor Yellow
Write-Host ""

# --- Programmordner entfernen ---------------------------------------------
# Das Skript selbst liegt IN diesem Ordner und laeuft noch - deshalb
# verzoegertes Loeschen ueber einen kurzen, abgekoppelten cmd-Aufruf
# (startet NACH Ende dieses PowerShell-Prozesses).
Write-Host "Programmordner wird entfernt: $InstallDir" -ForegroundColor Cyan
$cmdArgs = "/c timeout /t 2 /nobreak >nul & rmdir /s /q `"$InstallDir`""
Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs -WindowStyle Hidden

Write-Host "Fertig. GENESIS Media Manager wurde deinstalliert." -ForegroundColor Green
