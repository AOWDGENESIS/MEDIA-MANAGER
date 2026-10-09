#Requires -Version 7.0
<#
.SYNOPSIS
    Baut das komplette GENESIS-Media-Manager-Installationspaket
    (self-contained .NET-Client + Python-Core-Service-Quellcode +
    i18n-Kataloge + Installer-Skripte) und optional das echte MSI.

.DESCRIPTION
    Dieses Skript ist die EINZIGE Quelle der Wahrheit fuer den
    Paketierungsvorgang - sowohl fuer lokale Builds (z.B. in der
    Linux-Entwicklungssandbox, wo "dotnet publish -r win-x64" trotz
    fehlendem echtem Windows funktioniert, weil nur vorkompilierte
    Runtime-Pakete per NuGet geladen werden) als auch fuer den
    GitHub-Actions-Workflow ".github/workflows/build-windows-installer.yml"
    (laeuft auf windows-latest und kann zusaetzlich das echte MSI mit dem
    WiX-Toolset bauen - siehe deploy/wix/Product.wxs fuer die Begruendung,
    warum das NICHT von Linux aus moeglich ist).

.PARAMETER OutputDir
    Zielordner fuer das zusammengestellte Paket (wird geleert/neu angelegt).

.PARAMETER BuildMsi
    Baut zusaetzlich das MSI mit dem WiX-Toolset (`dotnet tool install -g
    wix` muss vorhanden sein). Funktioniert nur unter echtem Windows.

.PARAMETER SkipZip
    Erzeugt kein ZIP-Archiv, nur den entpackten Paketordner.
#>
[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\build\package"),
    [switch]$BuildMsi,
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Write-Step { param([string]$Message) Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Message) Write-Host "    OK: $Message" -ForegroundColor Green }

Write-Host "=== GENESIS Media Manager - Paketbau ===" -ForegroundColor Green

if (Test-Path $OutputDir) {
    Remove-Item -Path $OutputDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$OutputDir = Resolve-Path $OutputDir

# --- 1) .NET/WPF-Client: self-contained fuer win-x64 ----------------------
Write-Step "Baue .NET/WPF-Client (self-contained, win-x64)"
$clientProject = Join-Path $RepoRoot "ui-windows-dotnet\GenesisMediaManager.Client\GenesisMediaManager.Client.csproj"
$clientOut = Join-Path $OutputDir "client"
dotnet publish $clientProject -c Release -r win-x64 --self-contained true `
    -p:EnableWindowsTargeting=true -p:PublishSingleFile=false `
    -o $clientOut
if ($LASTEXITCODE -ne 0) { throw "dotnet publish fehlgeschlagen" }
Copy-Item -Path (Join-Path $RepoRoot "i18n") -Destination (Join-Path $clientOut "i18n") -Recurse -Force
Write-Ok "Client gebaut nach '$clientOut' (inkl. i18n-Fallback-Kopie)"

# --- 2) Python-Core-Service-Quellcode --------------------------------------
Write-Step "Stelle Core-Service-Quellcode zusammen"
$backendOut = Join-Path $OutputDir "backend"
New-Item -ItemType Directory -Force -Path $backendOut | Out-Null
Copy-Item -Path (Join-Path $RepoRoot "core\genesis_core") -Destination (Join-Path $backendOut "genesis_core") -Recurse -Force
Copy-Item -Path (Join-Path $RepoRoot "core\run_api.py") -Destination (Join-Path $backendOut "run_api.py") -Force
Copy-Item -Path (Join-Path $RepoRoot "core\pyproject.toml") -Destination (Join-Path $backendOut "pyproject.toml") -Force
Get-ChildItem -Path $backendOut -Include "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $backendOut -Include "*.pyc" -Recurse -File | Remove-Item -Force -ErrorAction SilentlyContinue

# Laufzeit-Abhaengigkeiten (ohne Test-/Dev-Werkzeuge aus core/requirements.txt).
@"
# GENESIS Media Manager - Core-Service-Laufzeitabhaengigkeiten (ohne
# Test-/Entwicklungswerkzeuge, siehe core/requirements.txt im Haupt-Repo
# fuer Lizenzangaben und die vollstaendige Liste inkl. Dev-Werkzeugen).
sqlalchemy>=2.0,<3.0
alembic>=1.13,<2.0
pydantic>=2.6,<3.0
pydantic-settings>=2.2,<3.0
fastapi>=0.110,<1.0
uvicorn[standard]>=0.29,<1.0
httpx>=0.27,<1.0
PyYAML>=6.0,<7.0
mutagen>=1.47,<2.0
python-multipart>=0.0.9
yt-dlp>=2026.8,<2027.0
"@ | Set-Content -Path (Join-Path $backendOut "requirements.txt") -Encoding UTF8

@"
# Optional: lokale Sprachausgabe (Voice Studio, Paragraph 28/29). Separat
# gehalten, weil piper-tts auf manchen Systemen zusaetzliche Build-
# Werkzeuge braucht - Kernfunktionen (Bibliothek/Scan/Tags/Duplikate/...)
# funktionieren auch OHNE dieses Paket.
piper-tts>=1.8,<2.0
"@ | Set-Content -Path (Join-Path $backendOut "requirements-voice.txt") -Encoding UTF8

Write-Ok "Core-Service-Quellcode zusammengestellt nach '$backendOut'"

# --- 3) Gemeinsame i18n-Kataloge (fuer genesis_core.i18n.default_catalog_dir()) --
Write-Step "Kopiere gemeinsame i18n-Kataloge"
Copy-Item -Path (Join-Path $RepoRoot "i18n") -Destination (Join-Path $OutputDir "i18n") -Recurse -Force
Write-Ok "i18n-Ordner auf Paketwurzel-Ebene kopiert"

# --- 4) Installer-Skripte + Endnutzer-Anleitung -----------------------------
Write-Step "Kopiere Installer-Skripte und Anleitung"
Copy-Item -Path (Join-Path $PSScriptRoot "installer") -Destination (Join-Path $OutputDir "installer") -Recurse -Force
Copy-Item -Path (Join-Path $PSScriptRoot "README-INSTALL.md") -Destination (Join-Path $OutputDir "README-INSTALL.md") -Force
Write-Ok "Installer-Skripte und README-INSTALL.md kopiert"

# --- 4b) start.bat auf Paketwurzel-Ebene (Fortsetzung 23, Nutzerwunsch:
#         "Installation und Start in einem Rutsch") ---------------------------
#
# Ein einziger Doppelklick fuer Endnutzer: erkennt automatisch, ob die App
# bereits unter %LOCALAPPDATA%\Programs\GenesisMediaManager installiert ist.
# Falls nicht, wird der vorhandene PowerShell-Installer automatisch mit
# Bypass der Ausfuehrungsrichtlinie aufgerufen (kein manuelles
# Rechtsklick-"Als Administrator ausfuehren" noetig, keine Richtlinien-
# Huerden) - danach wird die App in jedem Fall sofort gestartet, ueber das
# vom Installer selbst erzeugte Start-GenesisMediaManager.bat.
Write-Step "Erzeuge start.bat auf Paketwurzel-Ebene"
$startBatContent = @'
@echo off
setlocal
rem GENESIS Media Manager - Installation + Start in einem Schritt.
rem Einfach per Doppelklick ausfuehren: erkennt automatisch, ob die App
rem schon installiert ist, installiert sie bei Bedarf unbeaufsichtigt
rem (keine manuelle Rechtsklick-/Ausfuehrungsrichtlinien-Huerde) und
rem startet sie danach sofort.

set "INSTALLDIR=%LOCALAPPDATA%\Programs\GenesisMediaManager"
set "SCRIPTDIR=%~dp0"

if exist "%INSTALLDIR%\client\GenesisMediaManager.exe" goto :start

echo ============================================================
echo  GENESIS Media Manager wird zum ersten Mal eingerichtet ...
echo  (einmaliger Vorgang, braucht kurz Internetzugang fuer die
echo   Python-Laufzeitumgebung des lokalen Core-Service)
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTDIR%installer\Install-GenesisMediaManager.ps1"
if errorlevel 1 (
    echo.
    echo FEHLER: Installation fehlgeschlagen - siehe Meldungen oben.
    pause
    exit /b 1
)

:start
if exist "%INSTALLDIR%\Start-GenesisMediaManager.bat" (
    call "%INSTALLDIR%\Start-GenesisMediaManager.bat"
) else (
    start "" "%INSTALLDIR%\client\GenesisMediaManager.exe"
)
endlocal
'@
Set-Content -Path (Join-Path $OutputDir "start.bat") -Value $startBatContent -Encoding ASCII
Write-Ok "start.bat erzeugt (Installation + Start in einem Schritt)"

# --- 5) Optional: echtes MSI mit WiX bauen (nur unter echtem Windows) ------
if ($BuildMsi) {
    Write-Step "Baue MSI mit WiX-Toolset"
    if (-not (Get-Command wix -ErrorAction SilentlyContinue)) {
        throw "wix-CLI nicht gefunden. Installieren mit: dotnet tool install --global wix --version 5.0.2"
    }
    $msiOut = Join-Path $OutputDir "GenesisMediaManager-Setup.msi"
    wix build (Join-Path $PSScriptRoot "wix\Product.wxs") `
        -ext WixToolset.Util.wixext `
        -d ProductVersion=0.2.0.0 `
        -d "ClientSourceDir=$(Join-Path $OutputDir 'client')" `
        -d "BackendSourceDir=$(Join-Path $OutputDir 'backend')" `
        -d "I18nSourceDir=$(Join-Path $OutputDir 'i18n')" `
        -d "InstallerSourceDir=$(Join-Path $OutputDir 'installer')" `
        -d "StartScriptSource=$(Join-Path $PSScriptRoot 'installer\Install-GenesisMediaManager.ps1')" `
        -o $msiOut
    if ($LASTEXITCODE -ne 0) { throw "wix build fehlgeschlagen" }
    Write-Ok "MSI gebaut: $msiOut"
}

# --- 6) ZIP erzeugen ---------------------------------------------------------
if (-not $SkipZip) {
    Write-Step "Erzeuge ZIP-Archiv"
    $zipPath = Join-Path (Split-Path -Parent $OutputDir) "GenesisMediaManager-Setup.zip"
    if (Test-Path $zipPath) { Remove-Item -Path $zipPath -Force }
    Compress-Archive -Path (Join-Path $OutputDir "*") -DestinationPath $zipPath -CompressionLevel Optimal
    Write-Ok "ZIP erzeugt: $zipPath"
}

Write-Host "`n=== Paketbau abgeschlossen ===" -ForegroundColor Green
Write-Host "Paketordner: $OutputDir" -ForegroundColor Green
