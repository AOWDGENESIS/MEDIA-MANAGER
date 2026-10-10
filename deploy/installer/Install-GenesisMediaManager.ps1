#Requires -Version 5.1
<#
.SYNOPSIS
    Installiert GENESIS Media Manager (.NET-Client + Python-Core-Service)
    fuer den aktuellen Benutzer - keine Administratorrechte noetig.

.DESCRIPTION
    Kopiert die mitgelieferten Programmdateien (client/, backend/, i18n/)
    nach %LOCALAPPDATA%\Programs\GenesisMediaManager, legt eine virtuelle
    Python-Umgebung fuer den lokalen Core-Service an, installiert dessen
    Abhaengigkeiten (braucht dafuer einmalig Internetzugang - genau wie
    jede normale Windows-App-Installation), erzeugt Startmenue-/Desktop-
    Verknuepfungen und traegt das Programm unter "Apps & Features" ein.

    GENESIS Media Manager selbst arbeitet danach vollstaendig lokal/
    offline (siehe ARCHITECTURE.md, ADR-0001: Core-Service bindet nur an
    127.0.0.1, kein Cloud-Zugriff).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File Install-GenesisMediaManager.ps1

.EXAMPLE
    # Eigenen Installationsordner waehlen:
    powershell -ExecutionPolicy Bypass -File Install-GenesisMediaManager.ps1 -InstallDir "D:\Programme\GenesisMediaManager"
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\GenesisMediaManager"),
    [switch]$SkipPythonSetup
)

$ErrorActionPreference = "Stop"

function Write-Step  { param([string]$Message) Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Message) Write-Host "    OK: $Message" -ForegroundColor Green }
function Write-Warn2 { param([string]$Message) Write-Host "    WARNUNG: $Message" -ForegroundColor Yellow }

$ScriptRoot  = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $ScriptRoot

Write-Host "=== GENESIS Media Manager - Installation ===" -ForegroundColor Green

# --- 0) Alle mitgelieferten Skripte entsperren ("Mark of the Web") -------
# Windows versieht JEDE einzelne Datei aus einem heruntergeladenen ZIP mit
# einer Zone.Identifier-Markierung ("aus dem Internet"). Reale Beobachtung
# (Deep-Review-Fund, erster Testlauf durch einen echten Nutzer): obwohl
# dieses Skript selbst per Rechtsklick -> "Mit PowerShell ausfuehren" noch
# anlief, wurde der Aufruf von Setup-PythonRuntime.ps1 weiter unten mit
# "ist nicht digital signiert ... PSSecurityException" abgebrochen - genau
# dieses klassische Mark-of-the-Web-Verhalten kann je nach ZIP-Werkzeug/
# Windows-Version pro Datei unterschiedlich ausfallen. Unblock-File entfernt
# die Markierung robust fuer ALLE mitgelieferten Skripte, bevor irgendeines
# davon aufgerufen wird (zusaetzlich zu Punkt a) unten, siehe dort).
Get-ChildItem -Path $PackageRoot -Recurse -Filter "*.ps1" -ErrorAction SilentlyContinue |
    Unblock-File -ErrorAction SilentlyContinue

Write-Step "Installationsziel: $InstallDir"

# --- 0b) Laufende Instanz beenden (vermeidet "Zugriff verweigert" beim ---
# ----    Aktualisieren einer bestehenden Installation) --------------------
# Echter Nutzer-Testlauf: Ein zweiter Installationslauf schlug fehl mit
# "Remove-Item: ... PresentationCore.resources.dll ... Zugriff verweigert"
# - der .NET-Client (oder der lokale Core-Service) lief noch aus einer
# frueheren Sitzung und hatte seine eigenen DLLs/Dateien geladen, die
# Windows dann exklusiv sperrt. Deshalb VOR jedem Kopiervorgang aktiv
# beenden, statt den Nutzer raten zu lassen, was "nicht mehr verfuegbar"
# bedeutet.
Write-Step "Pruefe auf eine noch laufende GENESIS Media Manager-Instanz"
$runningClient = Get-Process -Name "GenesisMediaManager" -ErrorAction SilentlyContinue
if ($runningClient) {
    Write-Warn2 "GENESIS Media Manager laeuft noch - wird automatisch beendet, damit die Installation fortfahren kann."
    $runningClient | Stop-Process -Force -ErrorAction SilentlyContinue
}
try {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" -ErrorAction Stop |
        Where-Object { $_.CommandLine -like "*run_api.py*" } |
        ForEach-Object {
            Write-Warn2 "Core-Service (PID $($_.ProcessId)) laeuft noch - wird automatisch beendet."
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
} catch {
    # Get-CimInstance kann auf manchen Systemen fehlschlagen (z.B. WMI
    # deaktiviert) - dann bestenfalls weiter unten per Fehlermeldung beim
    # Kopieren bemerkt, kein Grund die gesamte Installation abzubrechen.
}
if ($runningClient) { Start-Sleep -Milliseconds 500 }

# --- 1) Programmdateien kopieren -----------------------------------------
if (Test-Path $InstallDir) {
    Write-Warn2 "Zielordner existiert bereits - Programmdateien werden aktualisiert (Mediathek-Daten/Einstellungen unter '$env:APPDATA\GenesisMediaManager' bleiben unberuehrt)."
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

foreach ($part in @("client", "backend", "i18n")) {
    $src = Join-Path $PackageRoot $part
    $dst = Join-Path $InstallDir $part
    if (-not (Test-Path $src)) {
        throw "Erwarteter Ordner fehlt im Installationspaket: $src (Paket beschaedigt/unvollstaendig?)"
    }
    if (Test-Path $dst) {
        try {
            Remove-Item -Path $dst -Recurse -Force -ErrorAction Stop
        } catch {
            throw "Ordner '$dst' konnte nicht aktualisiert werden - mindestens eine Datei darin ist noch in Benutzung ($($_.Exception.Message)). Bitte GENESIS Media Manager vollstaendig beenden (im Task-Manager pruefen: 'GenesisMediaManager.exe', 'python.exe'/'pythonw.exe' beenden) und die Installation erneut starten."
        }
    }
    Copy-Item -Path $src -Destination $dst -Recurse -Force
}
Write-Ok "Programmdateien nach '$InstallDir' kopiert (Client/Core-Service/Sprachdateien)"

# Vorsichtshalber auch die KOPIERTEN Skripte entsperren (NTFS kann die
# Zone.Identifier-Markierung bei Copy-Item je nach Windows-Version/

# Antivirus-Interaktion mitkopieren).
Get-ChildItem -Path $InstallDir -Recurse -Filter "*.ps1" -ErrorAction SilentlyContinue |
    Unblock-File -ErrorAction SilentlyContinue

# --- 2) Python-Laufzeitumgebung fuer den Core-Service --------------------
# Ausgelagert nach Setup-PythonRuntime.ps1, damit MSI-Installation (siehe
# wix/Product.wxs, CustomAction nach Dateiinstallation) und dieser einfache
# PowerShell-Installer dieselbe Logik verwenden.
#
# b) Bewusst als EIGENER powershell.exe-Prozess mit explizitem
# "-ExecutionPolicy Bypass" gestartet (statt per "&" im selben Prozess
# aufzurufen): "Bypass" bedeutet laut Microsoft-Dokumentation "nichts wird
# blockiert, keine Warnungen/Eingabeaufforderungen" - unabhaengig von einer
# evtl. verbliebenen Mark-of-the-Web-Markierung der Datei. Zusammen mit dem
# Unblock-File weiter oben (Punkt a) damit doppelt abgesichert gegen genau
# den "ist nicht digital signiert"-Fehler, der bei einem echten Nutzer
# aufgetreten ist, obwohl dieses Hauptskript selbst anlief.
if (-not $SkipPythonSetup) {
    $setupScript = Join-Path $ScriptRoot "Setup-PythonRuntime.ps1"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setupScript -InstallDir $InstallDir
    if ($LASTEXITCODE -ne 0) {
        throw "Setup-PythonRuntime.ps1 ist fehlgeschlagen (Exit-Code $LASTEXITCODE) - Installation abgebrochen."
    }
}

# --- 3) Start-Skript erzeugen ---------------------------------------------
Write-Step "Start-Skript wird erzeugt"
$startBat = Join-Path $InstallDir "Start-GenesisMediaManager.bat"
Copy-Item -Path (Join-Path $ScriptRoot "Start-GenesisMediaManager.bat") -Destination $startBat -Force
Write-Ok "Start-GenesisMediaManager.bat erzeugt"


# --- 4) Verknuepfungen (Startmenue + Desktop) -----------------------------
Write-Step "Verknuepfungen werden angelegt"
$wsh = New-Object -ComObject WScript.Shell

function New-AppShortcut {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Target,
        [string]$Arguments,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [string]$IconPath
    )
    $shortcut = $wsh.CreateShortcut($Path)
    $shortcut.TargetPath = $Target
    if ($Arguments) { $shortcut.Arguments = $Arguments }
    $shortcut.WorkingDirectory = $WorkingDirectory
    if ($IconPath) { $shortcut.IconLocation = $IconPath }
    $shortcut.Save()
}

$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\GENESIS Media Manager"
New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null

$clientExe = Join-Path $InstallDir "client\GenesisMediaManager.exe"
$startBat  = Join-Path $InstallDir "Start-GenesisMediaManager.bat"

New-AppShortcut -Path (Join-Path $startMenuDir "GENESIS Media Manager.lnk") `
    -Target $startBat -WorkingDirectory $InstallDir -IconPath $clientExe

New-AppShortcut -Path (Join-Path $startMenuDir "Deinstallieren.lnk") `
    -Target "powershell.exe" `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\Uninstall-GenesisMediaManager.ps1`"" `
    -WorkingDirectory $InstallDir

try {
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $desktopShortcut = Join-Path $desktopPath "GENESIS Media Manager.lnk"
    New-AppShortcut -Path $desktopShortcut -Target $startBat -WorkingDirectory $InstallDir -IconPath $clientExe
    Write-Ok "Startmenue- und Desktop-Verknuepfung angelegt"
} catch {
    Write-Warn2 "Desktop-Verknuepfung konnte nicht angelegt werden (Startmenue-Verknuepfung ist trotzdem da): $($_.Exception.Message)"
}

# --- 5) Uninstall-Skript + Eintrag in "Apps & Features" -------------------
Copy-Item -Path (Join-Path $ScriptRoot "Uninstall-GenesisMediaManager.ps1") `
    -Destination (Join-Path $InstallDir "Uninstall-GenesisMediaManager.ps1") -Force

Write-Step "Eintrag unter 'Apps & Features' wird angelegt (nur fuer aktuellen Benutzer, keine Adminrechte)"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\GenesisMediaManager"
New-Item -Path $uninstallKey -Force | Out-Null
Set-ItemProperty -Path $uninstallKey -Name "DisplayName" -Value "GENESIS Media Manager"
Set-ItemProperty -Path $uninstallKey -Name "DisplayVersion" -Value "0.2.0"
Set-ItemProperty -Path $uninstallKey -Name "Publisher" -Value "GENESIS Media Manager Projekt"
Set-ItemProperty -Path $uninstallKey -Name "InstallLocation" -Value $InstallDir
Set-ItemProperty -Path $uninstallKey -Name "DisplayIcon" -Value $clientExe
Set-ItemProperty -Path $uninstallKey -Name "UninstallString" `
    -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\Uninstall-GenesisMediaManager.ps1`""
Set-ItemProperty -Path $uninstallKey -Name "NoModify" -Value 1 -Type DWord
Set-ItemProperty -Path $uninstallKey -Name "NoRepair" -Value 1 -Type DWord
Write-Ok "Erscheint ab jetzt unter Einstellungen -> Apps -> Installierte Apps"

Write-Host ""
Write-Host "=== Installation abgeschlossen ===" -ForegroundColor Green
Write-Host "Start ueber die Verknuepfung 'GENESIS Media Manager' (Startmenue/Desktop)" -ForegroundColor Green
Write-Host "oder direkt: $startBat" -ForegroundColor Green
Write-Host ""
