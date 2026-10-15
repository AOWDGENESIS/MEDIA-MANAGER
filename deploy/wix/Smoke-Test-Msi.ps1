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
    $p = Start-Process -FilePath msiexec.exe -ArgumentList @(
        '/i', ('"' + $msi + '"'), '/qn', '/norestart', '/l*v', ('"' + $installLog + '"')
    ) -PassThru -Wait
    if ($p.ExitCode -ne 0) { throw "MSI-Installation fehlgeschlagen: $($p.ExitCode)" }
    foreach ($file in @($client, $backend, (Join-Path $installDir 'Start-GenesisMediaManager.bat'))) {
        if (-not (Test-Path $file)) { throw "MSI enthaelt Datei nicht: $file" }
    }

    # MSI startet pip nach InstallFinalize asynchron. Ein MSI-Exit-Code 0
    # beweist daher NICHT, dass der Core benutzbar ist: explizit warten.
    Write-Host 'Warte auf asynchrone Python-Einrichtung durch MSI'
    $ready = $false
    for ($i = 0; $i -lt 100; $i++) {
        if (Test-Path $python) {
            & $python -c 'import fastapi, sqlalchemy, uvicorn' 2>$null
            if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        }
        Start-Sleep -Seconds 3
    }
    if (-not $ready) { throw 'MSI-Python-Setup hat nach 5 Minuten keine lauffaehigen Core-Abhaengigkeiten bereitgestellt' }
    # Optionale Voice-Pakete werden nach den Core-Abhaengigkeiten installiert.
    # Erst deinstallieren, wenn auch dieser asynchrone Installer beendet ist.
    $setupFinished = $false
    for ($i = 0; $i -lt 90; $i++) {
        $setupProcesses = @(Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" |
            Where-Object { $_.CommandLine -like '*Setup-PythonRuntime.ps1*' -and
                $_.CommandLine -like "*$installDir*" })
        if ($setupProcesses.Count -eq 0) { $setupFinished = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $setupFinished) { throw 'Asynchrones MSI-Python-Setup laeuft nach weiteren 3 Minuten noch' }

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

    New-Item -ItemType Directory -Force -Path (Split-Path $sentinel) | Out-Null
    Set-Content -Path $sentinel -Value 'MSI: Benutzerdaten erhalten'
    $entry = @(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -eq 'GENESIS Media Manager' -and $_.WindowsInstaller -eq 1 })
    if ($entry.Count -ne 1 -or $entry[0].PSChildName -notmatch '^\{[0-9A-Fa-f-]{36}\}$') {
        throw 'MSI-Uninstall-Eintrag in HKCU nicht eindeutig gefunden'
    }
    $productCode = $entry[0].PSChildName
    Write-Host "Deinstalliere MSI $productCode"
    $p = Start-Process -FilePath msiexec.exe -ArgumentList @(
        '/x', $productCode, '/qn', '/norestart', '/l*v', ('"' + $uninstallLog + '"')
    ) -PassThru -Wait
    if ($p.ExitCode -ne 0) { throw "MSI-Deinstallation fehlgeschlagen: $($p.ExitCode)" }
    if (Test-Path $client) { throw 'MSI-Deinstallation hat Client hinterlassen' }
    if (Test-Path $python) { throw 'MSI-Deinstallation hat venv hinterlassen' }
    if (-not (Test-Path $sentinel)) { throw 'MSI-Deinstallation hat Benutzerdaten geloescht' }
    Write-Host 'MSI-Smoke-Test erfolgreich: Installation, Core /health, Deinstallation, Benutzerdaten erhalten.'
} catch {
    Write-Host "::error::$($_.Exception.Message)"
    foreach ($log in @($installLog, $uninstallLog, $apiLog)) {
        if (Test-Path $log) {
            Write-Host "Diagnose aus $log"
            Select-String -Path $log -Pattern 'error|fehler|Return value 3|Setup-Python|GENESIS' |
                Select-Object -Last 25 | ForEach-Object { Write-Host $_.Line }
            Get-Content $log -Tail 25
        }
    }
    throw
} finally {
    if ($apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $sentinel -ErrorAction SilentlyContinue
}
