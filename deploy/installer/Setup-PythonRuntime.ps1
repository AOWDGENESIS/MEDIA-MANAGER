#Requires -Version 5.1
<#
.SYNOPSIS
    Legt eine virtuelle Python-Umgebung fuer den GENESIS Core-Service an
    und installiert dessen Abhaengigkeiten.

.DESCRIPTION
    Eigenstaendiges Skript (ausgelagert aus Install-GenesisMediaManager.ps1,
    damit sowohl der einfache PowerShell-Installer ALS AUCH die MSI-Variante
    (als deferred CustomAction nach der Dateiinstallation, siehe
    wix/Product.wxs) dieselbe, einmal geprüfte Logik verwenden - keine
    Doppelpflege zweier leicht unterschiedlicher Kopien.

.PARAMETER InstallDir
    Wurzelordner der Installation (enthaelt client/, backend/, i18n/).

.PARAMETER SkipVoice
    Ueberspringt die optionale Sprachausgabe-Abhaengigkeit (piper-tts).
#>
[CmdletBinding()]
param(
    [string]$InstallDir,
    [switch]$SkipVoice
)

$ErrorActionPreference = "Stop"

# Bewusst KEIN "[Parameter(Mandatory)]" (das wuerde PowerShell bei
# fehlendem Aufrufparameter zu einer interaktiven Eingabeaufforderung
# verleiten - verwirrend/unbrauchbar in einem Konsolenfenster, das
# gleich darauf wieder schliesst). Stattdessen: klarer, sofortiger
# Fehlschlag mit Erklaerung (kein stiller/unklarer Fehlschlag).
if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    throw "Setup-PythonRuntime.ps1 braucht den Parameter -InstallDir (Pfad, in den GENESIS Media Manager installiert wurde/wird). Nicht direkt aufrufen - stattdessen Install-GenesisMediaManager.ps1 ausfuehren."
}

function Write-Step  { param([string]$Message) Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Message) Write-Host "    OK: $Message" -ForegroundColor Green }
function Write-Warn2 { param([string]$Message) Write-Host "    WARNUNG: $Message" -ForegroundColor Yellow }

Write-Step "Suche installiertes Python (3.11 oder neuer) fuer den Core-Service"
$PythonExe = $null
# Ein explizit auf PATH eingerichtetes Python hat Vorrang vor dem
# Windows-py-Launcher (dessen Standardversion kann eine andere sein).
foreach ($candidate in @("python", "py", "python3")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    try {
        $verOutput = & $candidate --version 2>&1
    } catch {
        continue
    }
    if ($verOutput -match "Python (\d+)\.(\d+)") {
        $maj = [int]$Matches[1]
        $min = [int]$Matches[2]
        if ($maj -gt 3 -or ($maj -eq 3 -and $min -ge 11)) {
            $PythonExe = $candidate
            break
        }
    }
}

if (-not $PythonExe) {
    Write-Warn2 "Kein Python 3.11+ gefunden."
    Write-Host ""
    Write-Host "    GENESIS Media Manager braucht Python 3.11 oder neuer fuer den" -ForegroundColor Yellow
    Write-Host "    lokalen Core-Service (Bibliothek/Scan/Tags/Duplikate/...)." -ForegroundColor Yellow
    Write-Host "    Bitte installieren: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "    WICHTIG: beim Installieren den Haken 'Add python.exe to PATH' setzen!" -ForegroundColor Yellow
    Write-Host "    Danach dieses Skript erneut ausfuehren:" -ForegroundColor Yellow
    Write-Host "    powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -InstallDir `"$InstallDir`"" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "    Der .NET-Client laesst sich bereits oeffnen, zeigt aber ohne" -ForegroundColor Yellow
    Write-Host "    laufenden Core-Service keine Daten an." -ForegroundColor Yellow
    # Ohne Python ist die Einrichtung nicht erfolgreich: Installer duerfen
    # den Client nicht als startbereit melden.
    exit 1
}
Write-Ok "Gefunden: $PythonExe"

Write-Step "Virtuelle Python-Umgebung wird angelegt"
$venvDir = Join-Path $InstallDir ".venv"
if (Test-Path $venvDir) {
    Remove-Item -Path $venvDir -Recurse -Force
}
& $PythonExe -m venv $venvDir
if ($LASTEXITCODE -ne 0) { throw "Anlegen der virtuellen Umgebung fehlgeschlagen (python -m venv)." }

$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "venv wurde angelegt, aber '$venvPython' fehlt - unerwartetes Python-Setup."
}
Write-Ok "Virtuelle Umgebung angelegt unter '$venvDir'"

Write-Step "Core-Service-Kernabhaengigkeiten werden installiert (braucht Internetzugang, dauert evtl. 1-2 Minuten)"
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r (Join-Path $InstallDir "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "pip install der Kernabhaengigkeiten ist fehlgeschlagen - siehe Ausgabe oben."
}
Write-Ok "Kernabhaengigkeiten installiert (Bibliothek/Scan/Tags/Duplikate/Download-Center/...)"

if (-not $SkipVoice) {
    Write-Step "Optionale Sprachausgabe (Voice Studio, Paragraph 28/29) wird installiert"
    & $venvPython -m pip install -r (Join-Path $InstallDir "backend\requirements-voice.txt")
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "piper-tts konnte nicht installiert werden - ALLE Funktionen AUSSER Voice Studio/Sprachausgabe funktionieren trotzdem normal."
        Write-Host "    Spaeter manuell nachholen mit:" -ForegroundColor Yellow
        Write-Host "    `"$venvPython`" -m pip install -r `"$InstallDir\backend\requirements-voice.txt`"" -ForegroundColor Yellow
    } else {
        Write-Ok "Voice Studio-Abhaengigkeiten installiert"
    }
}
