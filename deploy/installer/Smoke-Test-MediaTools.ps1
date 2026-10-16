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
$wave = Join-Path $env:RUNNER_TEMP 'genesis-offline-ci-tone.wav'
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
    Write-Host 'Medien-Funktionstest erfolgreich: FFmpeg-Synthese, FFprobe-Dauer, Chromaprint-Fingerprint.'
} catch {
    $message = ($_.Exception.Message -replace '%', '%25') -replace '[\r\n]+', ' '
    Write-Host "::error::Medien-Funktionstest: $message"
    throw
} finally {
    Remove-Item -LiteralPath $wave -Force -ErrorAction SilentlyContinue
}
