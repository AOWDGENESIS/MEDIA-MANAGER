#Requires -Version 5.1
<#
.SYNOPSIS
    Positiver Windows-CI-Test fuer MSI: frische Installation, Core und
    Deinstallation. Laeuft NACH dem Inno-Smoke-Test im selben CI-Job.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$msi = Join-Path $repoRoot 'build\package\GenesisMediaManager-Setup.msi'
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\GenesisMediaManager'
$client = Join-Path $installDir 'client\GenesisMediaManager.exe'
$python = Join-Path $installDir '.venv\Scripts\python.exe'
$backend = Join-Path $installDir 'backend\run_api.py'
$sentinel = Join-Path $env:APPDATA 'GenesisMediaManager\ci-msi-user-data.txt'
$installLog = Join-Path $env:RUNNER_TEMP 'genesis-msi-install.log'
$uninstallLog = Join-Path $env:RUNNER_TEMP 'genesis-msi-uninstall.log'
$apiLog = Join-Path $env:RUNNER_TEMP 'genesis-msi-api-stderr.log'
$apiProcess = $null

if (-not (Test-Path $msi)) { throw "MSI fehlt: $msi" }
if (Test-Path $client) { throw "MSI-Test braucht einen freien Programmordner: $client" }

try {
    Write-Host 'Installiere MSI im frischen Benutzerprofil (nach Inno-Deinstallation)'
    # setup-python@v6 erweitert nur den PATH des CI-Prozesses. Der MSI-
    # Dienst erbt ihn nicht; den bereits geprueften Interpreter uebergeben.
    $pythonFromCi = (Get-Command python -ErrorAction Stop).Source
    $p = Start-Process -FilePath msiexec.exe -ArgumentList @(
        '/i', ('"' + $msi + '"'), '/qn', '/norestart',
        ('GENESIS_PYTHON="' + $pythonFromCi + '"'), '/l*v', ('"' + $installLog + '"')
    ) -PassThru -Wait
    if ($p.ExitCode -ne 0) { throw "MSI-Installation fehlgeschlagen: $($p.ExitCode)" }
    foreach ($file in @($client, $backend, (Join-Path $installDir 'Start-GenesisMediaManager.bat'),
                       (Join-Path $installDir 'MsiOwnership.txt'))) {
        if (-not (Test-Path $file)) { throw "MSI enthaelt Datei nicht: $file" }
    }

    # Die MSI-Custom-Action wartet jetzt selbst auf pip und prueft den
    # Exit-Code. Zusaetzlich den benutzbaren Core statt nur die Datei pruefen.
    if (-not (Test-Path $python)) { throw 'MSI hat keine Python-Umgebung angelegt' }
    & $python -c 'import fastapi, sqlalchemy, uvicorn'
    if ($LASTEXITCODE -ne 0) { throw 'MSI-Core-Abhaengigkeiten nicht importierbar' }

    $apiProcess = Start-Process -FilePath $python -ArgumentList @(
        ('"' + $backend + '"'), '--port', '18421', '--data-dir',
        ('"' + (Join-Path $env:RUNNER_TEMP 'genesis-msi-api-data') + '"')
    ) -PassThru -RedirectStandardError $apiLog
    $healthy = $false
    for ($i = 0; $i -lt 45; $i++) {
        if ($apiProcess.HasExited) { throw "MSI-Core vorzeitig beendet: $($apiProcess.ExitCode)" }
        try {
            $result = Invoke-RestMethod -Uri 'http://127.0.0.1:18421/health' -TimeoutSec 2
            if ($result.status -eq 'ok') { $healthy = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $healthy) { throw 'MSI-Core antwortet nicht auf /health' }
    Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
    $apiProcess.WaitForExit(10000) | Out-Null
    $apiProcess = $null

    # Negativer Test: Der ZIP-/PowerShell-Installer darf auch dann nicht
    # ueber das MSI schreiben, wenn dessen Uninstall-Eintrag nicht unter
    # HKCU des CI-Prozesses sichtbar ist.
    $guardError = Join-Path $env:RUNNER_TEMP 'genesis-zip-msi-conflict.err'
    $guardOutput = Join-Path $env:RUNNER_TEMP 'genesis-zip-msi-conflict.out'
    $zipInstaller = Join-Path $repoRoot 'deploy\installer\Install-GenesisMediaManager.ps1'
    $blocked = Start-Process -FilePath powershell.exe -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $zipInstaller + '"'), '-SkipPythonSetup'
    ) -PassThru -Wait -RedirectStandardOutput $guardOutput -RedirectStandardError $guardError
    if ($blocked.ExitCode -eq 0 -or
        -not (Select-String -Path $guardError -Pattern 'MSI-Installer verwaltet diese App' -Quiet)) {
        throw "ZIP-Installer hat bestehende MSI-Installation nicht eindeutig abgewiesen (Code $($blocked.ExitCode))"
    }
    if (-not (Test-Path $client)) { throw 'ZIP-Konflikttest hat den MSI-Client veraendert' }

    New-Item -ItemType Directory -Force -Path (Split-Path $sentinel) | Out-Null
    Set-Content -Path $sentinel -Value 'MSI: Benutzerdaten erhalten'
    # Der MSI-Uninstaller muss .venv auch bei laufendem Core entfernen.
    $startBat = Join-Path $installDir 'Start-GenesisMediaManager.bat'
    & $env:ComSpec /d /c ('"' + $startBat + '"')
    if ($LASTEXITCODE -ne 0) { throw "MSI-Startskript fehlgeschlagen: $LASTEXITCODE" }
    $runningHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8420/health' -TimeoutSec 5
    if ($runningHealth.status -ne 'ok') { throw 'MSI-Core laeuft vor Deinstallation nicht' }

    # Per-User-MSI erscheinen je nach Windows-/Installer-Kontext nicht
    # zwingend im HKCU-Uninstall-Zweig des aufrufenden pwsh-Prozesses.
    # msiexec /x akzeptiert die bereits gebaute MSI-Datei direkt.
    Write-Host 'Deinstalliere MSI anhand des Installationspakets (Core laeuft)'
    $p = Start-Process -FilePath msiexec.exe -ArgumentList @(
        '/x', ('"' + $msi + '"'), '/qn', '/norestart', '/l*v', ('"' + $uninstallLog + '"')
    ) -PassThru -Wait
    if ($p.ExitCode -ne 0) { throw "MSI-Deinstallation fehlgeschlagen: $($p.ExitCode)" }
    if (Test-Path $client) { throw 'MSI-Deinstallation hat Client hinterlassen' }
    if (Test-Path (Join-Path $installDir 'MsiOwnership.txt')) { throw 'MSI-Deinstallation hat Besitzer-Marker hinterlassen' }
    if (Test-Path $python) { throw 'MSI-Deinstallation hat venv hinterlassen' }
    if (-not (Test-Path $sentinel)) { throw 'MSI-Deinstallation hat Benutzerdaten geloescht' }
    Write-Host 'MSI-Smoke-Test erfolgreich: Installation, Core /health, Deinstallation, Benutzerdaten erhalten.'
} catch {
    Write-Host "::error::$($_.Exception.Message)"
    foreach ($log in @($installLog, $uninstallLog, $apiLog)) {
        if (Test-Path $log) {
            Write-Host "Diagnose aus $log"
            if ($log -eq $installLog) {
                $matches = @(Select-String -Path $log -Pattern 'RunPythonSetup|powershell.exe|Return value 3|Error 1721|Error 1722')
                Write-Host "::error::MSI-Log: $($matches.Count) Zeilen zur Python-Custom-Action"
                $matches | Select-Object -First 18 | ForEach-Object {
                    $message = ($_.Line -replace '%', '%25') -replace '[\r\n]+', ' '
                    Write-Host "::error::$message"
                }
            }
            Get-Content $log -Tail 12
        }
    }
    throw
} finally {
    if ($apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$installDir*backend*run_api.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Get-Process -Name GenesisMediaManager -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $client } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Remove-Item $sentinel -ErrorAction SilentlyContinue
}
