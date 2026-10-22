#Requires -Version 7.0
<#
.SYNOPSIS
    Windows-CI: mitgelieferte FFmpeg-/Chromaprint-Binaries tatsaechlich
    auf einer KLEINEN synthetischen Testdatei verwenden (nicht nur -version).
#>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$PackageDir)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Set-OfflineTestEnvironment.ps1')
$tools = Join-Path $PackageDir 'runtime\tools'
$ffmpeg = Join-Path $tools 'ffmpeg\ffmpeg.exe'
$ffprobe = Join-Path $tools 'ffmpeg\ffprobe.exe'
$fpcalc = Join-Path $tools 'chromaprint\fpcalc.exe'
$scanDir = Join-Path $env:RUNNER_TEMP 'genesis-ci-real-scan'
$wave = Join-Path $scanDir 'genesis-offline-ci-tone.wav'
if (Test-Path $scanDir) { throw "Synthetischer Scan-Ordner existiert schon: $scanDir" }
New-Item -ItemType Directory -Path $scanDir | Out-Null
try {
    & $ffmpeg -nostdin -hide_banner -loglevel error -f lavfi -i 'sine=frequency=440:duration=8' `
        -ac 1 -ar 44100 -y $wave
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $wave)) {
        throw 'Mitgeliefertes ffmpeg kann kein Test-Audio erzeugen'
    }
    $probeJson = & $ffprobe -v error -show_entries format=duration -of json $wave
    if ($LASTEXITCODE -ne 0) { throw 'Mitgeliefertes ffprobe kann Test-Audio nicht analysieren' }
    $probe = ($probeJson -join "`n") | ConvertFrom-Json
    if ([double]$probe.format.duration -lt 7) { throw 'ffprobe meldet unplausible Dauer' }
    $fingerprintJson = & $fpcalc -json $wave
    if ($LASTEXITCODE -ne 0) { throw 'Mitgeliefertes fpcalc kann Test-Audio nicht fingerprinten' }
    $fingerprint = ($fingerprintJson -join "`n") | ConvertFrom-Json
    if (-not $fingerprint.fingerprint) { throw 'Chromaprint hat keinen Fingerprint erzeugt' }
    # Jetzt den ECHTEN Scan mit dem mitgelieferten Windows-Python, Backend
    # und ffprobe ausfuehren (nicht nur die einzelnen CLIs ansprechen).
    # Ausschliesslich synthetische Testdaten unter RUNNER_TEMP.
    $env:PYTHONPATH = Join-Path $PackageDir 'backend'
    $env:GENESIS_CI_SCAN_DIR = $scanDir
    $python = Join-Path $PackageDir 'runtime\python\python.exe'
    $scanScript = @'
import os
from pathlib import Path
from sqlalchemy import select
from genesis_core.db import Database
from genesis_core.db.models import MediaFile, TechnicalMetadata
from genesis_core.scanner.scanner import scan_directories
root = Path(os.environ['GENESIS_CI_SCAN_DIR'])
db = Database(root / 'genesis-ci-scan.sqlite')
result = scan_directories(db, [root])
assert result.files_found == 1 and result.files_new == 1 and not result.errors, result
with db.session() as session:
    media = session.execute(select(MediaFile)).scalar_one()
    technical = session.execute(select(TechnicalMetadata)).scalar_one()
    assert media.filename == 'genesis-offline-ci-tone.wav'
    assert technical.duration_seconds >= 7, technical.duration_seconds
print('GENESIS scan: synthetisches Audio gelesen, Hash und FFprobe-Metadaten gespeichert')
'@
    & $python -c $scanScript
    if ($LASTEXITCODE -ne 0) { throw 'Echter Scan mit mitgeliefertem ffprobe/Python fehlgeschlagen' }
    Write-Host 'Medien-Funktionstest erfolgreich: FFmpeg-Synthese, FFprobe/Chromaprint und GENESIS-Scan.'
} catch {
    $message = ($_.Exception.Message -replace '%', '%25') -replace '[\r\n]+', ' '
    Write-Host "::error::Medien-Funktionstest: $message"
    throw
} finally {
    Remove-Item -LiteralPath $scanDir -Recurse -Force -ErrorAction SilentlyContinue
}
