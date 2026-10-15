#Requires -Version 5.1
# Nur CI: Installations-Smoke-Tests sollen weder ein globales Python
# noch pip-Downloads oder fremde ffmpeg/fpcalc-Binaries verwenden koennen.
# Dies aendert ausschliesslich die Umgebung des aktuellen CI-Schritts.
$ErrorActionPreference = 'Stop'
$system = $env:SystemRoot
$env:PATH = @(
    (Join-Path $system 'System32'),
    (Join-Path $system 'System32\WindowsPowerShell\v1.0'),
    (Join-Path $system 'System32\Wbem'),
    $system
) -join ';'
$env:PIP_NO_INDEX = '1'
$env:HTTP_PROXY = 'http://127.0.0.1:1'
$env:HTTPS_PROXY = 'http://127.0.0.1:1'
$env:ALL_PROXY = 'http://127.0.0.1:1'
if (Get-Command python -ErrorAction SilentlyContinue) { throw 'Offline-Test sieht noch globales Python' }
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { throw 'Offline-Test sieht noch globales FFmpeg' }
if (Get-Command fpcalc -ErrorAction SilentlyContinue) { throw 'Offline-Test sieht noch globales fpcalc' }
Write-Host 'Offline-Testumgebung: keine externen Python-/Medienwerkzeuge, pip offline, Proxy gesperrt.'
