#Requires -Version 5.1
<#
.SYNOPSIS
    Prueft die mitgelieferte Windows-Runtime OHNE Download, pip oder
    installiertes Python. Wird von Inno, MSI, ZIP und CI verwendet.
#>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$InstallDir)
$ErrorActionPreference = 'Stop'
trap {
    $message = ($_.Exception.Message -replace '%', '%25') -replace '[\r\n]+', ' '
    Write-Host "::error::Offline-Runtime: $message"
    break
}
$runtime = Join-Path $InstallDir 'runtime'
$python = Join-Path $runtime 'python\python.exe'
$pythonw = Join-Path $runtime 'python\pythonw.exe'
$ffmpeg = Join-Path $runtime 'tools\ffmpeg\ffmpeg.exe'
$ffprobe = Join-Path $runtime 'tools\ffmpeg\ffprobe.exe'
$fpcalc = Join-Path $runtime 'tools\chromaprint\fpcalc.exe'
foreach ($file in @($python, $pythonw, $ffmpeg, $ffprobe, $fpcalc,
                    (Join-Path $InstallDir 'backend\run_api.py'))) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Offline-Paket unvollstaendig: $file" }
}
$expected = [IO.Path]::GetFullPath((Join-Path $runtime 'python')).TrimEnd('\')
$actual = & $python -c 'import sys; print(sys.prefix)'
if ($LASTEXITCODE -ne 0 -or -not [string]::Equals(
        ([string]$actual).Trim().TrimEnd('\'), $expected,
        [StringComparison]::OrdinalIgnoreCase)) {
    throw "Portable Python-Runtime nicht unabhaengig: sys.prefix=$actual (erwartet $expected)"
}
foreach ($module in @('fastapi', 'sqlalchemy', 'uvicorn', 'yt_dlp', 'mutagen', 'pydantic_settings')) {
    # Windows PowerShell 5.1 kann NativeCommandError auf stderr erzeugen;
    # die echte Python-Traceback-Diagnose als CI-Annotation ausgeben.
    $ErrorActionPreference = 'Continue'
    $output = & $python -c "import $module" 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($code -ne 0) {
        $output | Select-Object -Last 8 | ForEach-Object {
            $message = ($_.ToString() -replace '%', '%25') -replace '[\r\n]+', ' '
            Write-Host "::error::Python $module`: $message"
        }
        throw "Mitgeliefertes Python-Paket nicht importierbar: $module (Code $code)"
    }
}
Write-Host 'Offline-Core-Abhaengigkeiten OK'
foreach ($tool in @($ffmpeg, $ffprobe, $fpcalc)) {
    & $tool -version 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Medienwerkzeug startet nicht: $tool" }
}
Write-Host 'Portable Python-Runtime, Core-Pakete, ffmpeg, ffprobe und fpcalc sind lokal lauffaehig.'
