#Requires -Version 5.1
<#
.SYNOPSIS
    Windows-CI-Smoke-Test fuer die echte Inno-Setup-EXE: Installation,
    Python-Umgebung, Core-API und Deinstallation (ohne GUI-Interaktion).
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$setup = Join-Path $repoRoot 'build\GenesisMediaManager-Inno-Setup.exe'
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\GenesisMediaManager'
$uninstall = Join-Path $installDir 'unins000.exe'
$python = Join-Path $installDir '.venv\Scripts\python.exe'
$dataDir = Join-Path $env:APPDATA 'GenesisMediaManager'
$sentinel = Join-Path $dataDir 'ci-keep-user-data.txt'
$log = Join-Path $env:RUNNER_TEMP 'genesis-inno-install.log'
$apiError = Join-Path $env:RUNNER_TEMP 'genesis-inno-api-stderr.log'
$apiOutput = Join-Path $env:RUNNER_TEMP 'genesis-inno-api-stdout.log'
$testData = Join-Path $env:RUNNER_TEMP 'genesis-smoke-data'
$apiProcess = $null

if (-not (Test-Path $setup)) { throw "Setup-EXE fehlt: $setup" }
if (Test-Path $installDir) { throw "CI-Test braucht ein frisches Benutzerprofil: $installDir existiert bereits" }

try {
    Write-Host "Installiere Inno-Setup-EXE: $setup"
    # PowerShell wartet bei GUI-EXEs mit dem Call-Operator nicht immer auf
    # das Prozessende; -Wait/-PassThru liefert den echten Installer-Code.
    $installProcess = Start-Process -FilePath $setup -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/LOG="' + $log + '"')
    ) -Wait -PassThru
    if ($installProcess.ExitCode -ne 0) { throw "Setup-EXE: Exit-Code $($installProcess.ExitCode)" }

    foreach ($path in @(
        (Join-Path $installDir 'client\GenesisMediaManager.exe'),
        (Join-Path $installDir 'backend\run_api.py'),
        (Join-Path $installDir 'Start-GenesisMediaManager.bat'),
        $python,
        $uninstall
    )) {
        if (-not (Test-Path $path)) { throw "Fehlende Installationsdatei: $path" }
    }

    Write-Host 'Pruefe installierte Python-Abhaengigkeiten und Core-API /health'
    & $python -c 'import fastapi, sqlalchemy, uvicorn'
    if ($LASTEXITCODE -ne 0) { throw 'Python-Laufzeitabhaengigkeiten fehlen' }

    $apiScript = Join-Path $installDir 'backend\run_api.py'
    # Der Test nutzt Port 18420 und einen separaten Datenordner, damit er
    # keine echten Nutzerdaten beruehrt. Nur der Backend-Prozess wird gestartet;
    # WPF-Oberflaechen koennen im CI-Runner nicht visuell geprueft werden.
    $apiProcess = Start-Process -FilePath $python -ArgumentList @(
        ('"' + $apiScript + '"'), '--port', '18420', '--data-dir', ('"' + $testData + '"')
    ) -PassThru -RedirectStandardOutput $apiOutput -RedirectStandardError $apiError
    $ready = $false
    for ($i = 0; $i -lt 45; $i++) {
        if ($apiProcess.HasExited) { throw "Core-Service vorzeitig beendet (Exit-Code $($apiProcess.ExitCode))" }
        try {
            $result = Invoke-RestMethod -Uri 'http://127.0.0.1:18420/health' -TimeoutSec 2
            if ($result.status -eq 'ok') { $ready = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw 'Core-Service /health antwortet nicht mit status ok' }
    Write-Host 'Core-API antwortet: status ok'

    Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
    if (-not $apiProcess.WaitForExit(10000)) { throw 'Core-Service konnte nicht beendet werden' }
    $apiProcess = $null

    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    Set-Content -Path $sentinel -Value 'Mediathek-Daten erhalten'
    Write-Host 'Deinstalliere Inno-Setup-Paket'
    $uninstallProcess = Start-Process -FilePath $uninstall -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
    ) -Wait -PassThru
    if ($uninstallProcess.ExitCode -ne 0) { throw "Deinstallation: Exit-Code $($uninstallProcess.ExitCode)" }
    if (Test-Path $python) { throw 'Uninstaller hat die Python-Umgebung nicht entfernt' }
    if (Test-Path (Join-Path $installDir 'client\GenesisMediaManager.exe')) { throw 'Uninstaller hat den Client nicht entfernt' }
    if (-not (Test-Path $sentinel)) { throw 'Uninstaller hat Benutzerdaten geloescht' }
    Write-Host 'Smoke-Test erfolgreich: Installation, Core-API, Deinstallation, Benutzerdaten erhalten.'
} catch {
    Write-Host "::error::$($_.Exception.Message)"
    if (Test-Path $log) { Get-Content $log -Tail 70 }
    if (Test-Path $apiError) { Get-Content $apiError -Tail 70 }
    throw
} finally {
    if ($apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $sentinel -ErrorAction SilentlyContinue
}
