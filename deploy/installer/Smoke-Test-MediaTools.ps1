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
    # Die hermetische Umgebung versteckt absichtlich alle globalen Tools;
    # nur fuer diesen lokalen Scan die MITGELIEFERTEN CLIs freischalten.
    $env:PATH = "$(Split-Path -Parent $ffprobe);$(Split-Path -Parent $fpcalc);$env:PATH"
    $python = Join-Path $PackageDir 'runtime\python\python.exe'
    $scanScript = Join-Path $PSScriptRoot 'Smoke-Test-Scanner.py'
    if (-not (Test-Path -LiteralPath $scanScript)) { throw "Scanner-Testskript fehlt: $scanScript" }
    # Python-Fehler direkt als Annotation ausgeben, da GitHub-Rawlogs aus
    # dieser Umgebung nicht immer abrufbar sind.
    $env:PYTHONUNBUFFERED = '1'
    $oldNativePreference = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
    try {
        $scanOutput = & $python $scanScript 2>&1
        $scanExit = $LASTEXITCODE
    } finally {
        $PSNativeCommandUseErrorActionPreference = $oldNativePreference
    }
    $scanOutput | ForEach-Object {
        $line = ($_.ToString() -replace '%', '%25') -replace '[\r\n]+', ' '
        if ($scanExit -ne 0) { Write-Host "::error::Scanner-Test: $line" }
        else { Write-Host $line }
    }
    if ($scanExit -ne 0) { throw "Echter Scan mit mitgeliefertem ffprobe/Python fehlgeschlagen (Code $scanExit)" }
    Write-Host 'Medien-Funktionstest erfolgreich: FFmpeg-Synthese, FFprobe/Chromaprint und GENESIS-Scan.'
} catch {
    $message = ($_.Exception.Message -replace '%', '%25') -replace '[\r\n]+', ' '
    Write-Host "::error::Medien-Funktionstest: $message"
    throw
} finally {
    Remove-Item -LiteralPath $scanDir -Recurse -Force -ErrorAction SilentlyContinue
}
