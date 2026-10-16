#Requires -Version 5.1
<#
.SYNOPSIS
    Windows-CI-Test des tatsaechlich erzeugten ZIPs: Entpacken,
    PowerShell-Installation, Start/Core und Deinstallation.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $repoRoot 'deploy\installer\Set-OfflineTestEnvironment.ps1')
$zip = Join-Path $repoRoot 'build\GenesisMediaManager-Setup.zip'
$extractDir = Join-Path $env:RUNNER_TEMP 'genesis-zip-smoke'
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\GenesisMediaManager'
$client = Join-Path $installDir 'client\GenesisMediaManager.exe'
$python = Join-Path $installDir 'runtime\python\python.exe'
$sentinel = Join-Path $env:APPDATA 'GenesisMediaManager\ci-zip-user-data.txt'

if (-not (Test-Path $zip)) { throw "Paket-ZIP fehlt: $zip" }
if (Test-Path $client) { throw "ZIP-Test braucht einen freien Programmordner: $client" }
if (Test-Path $extractDir) { throw "ZIP-Testordner bereits vorhanden: $extractDir" }

try {
    Write-Host "Entpacke $zip"
    Expand-Archive -LiteralPath $zip -DestinationPath $extractDir
    $installer = Join-Path $extractDir 'installer\Install-GenesisMediaManager.ps1'
    $uninstaller = Join-Path $installDir 'Uninstall-GenesisMediaManager.ps1'
    foreach ($file in @($installer, (Join-Path $extractDir 'start.bat'),
                       (Join-Path $extractDir 'client\GenesisMediaManager.exe'))) {
        if (-not (Test-Path $file)) { throw "ZIP-Inhalt unvollstaendig: $file" }
    }
    Write-Host 'Installiere entpacktes ZIP via beigelegtem Installer'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
    if ($LASTEXITCODE -ne 0) { throw "ZIP-Installation fehlgeschlagen: $LASTEXITCODE" }
    foreach ($file in @($client, $python, $uninstaller,
                        (Join-Path $installDir 'backend\run_api.py'))) {
        if (-not (Test-Path $file)) { throw "ZIP-Installation unvollstaendig: $file" }
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $extractDir 'installer\Test-OfflineRuntime.ps1') -InstallDir $installDir
    if ($LASTEXITCODE -ne 0) { throw 'ZIP-Offline-Runtime nicht lauffaehig' }

    Write-Host 'Pruefe den mitgelieferten ZIP-Schnellstart'
    & $env:ComSpec /d /c ('"' + (Join-Path $extractDir 'start.bat') + '"')
    if ($LASTEXITCODE -ne 0) { throw "ZIP-start.bat fehlgeschlagen: $LASTEXITCODE" }
    $healthy = $false
    for ($i = 0; $i -lt 25; $i++) {
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8420/health' -TimeoutSec 2 -NoProxy
            if ($health.status -eq 'ok') { $healthy = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $healthy) { throw 'ZIP-Start hat den Core nicht gestartet' }

    New-Item -ItemType Directory -Force -Path (Split-Path $sentinel) | Out-Null
    Set-Content -Path $sentinel -Value 'ZIP: Benutzerdaten erhalten'
    Write-Host 'Deinstalliere ZIP/PowerShell-Installation'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $uninstaller
    if ($LASTEXITCODE -ne 0) { throw "ZIP-Deinstallation fehlgeschlagen: $LASTEXITCODE" }
    # Der Uninstaller entfernt sich selbst und den Programmordner ueber
    # einen kurz verzoegerten, separaten cmd-Prozess.
    $removed = $false
    for ($i = 0; $i -lt 25; $i++) {
        if (-not (Test-Path $client) -and -not (Test-Path $python) -and
            -not (Test-Path $uninstaller)) { $removed = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $removed) { throw 'ZIP-Deinstallation hat Client, Python oder Uninstaller hinterlassen' }
    if (-not (Test-Path $sentinel)) { throw 'ZIP-Deinstallation hat Benutzerdaten geloescht' }
    Write-Host 'ZIP-Smoke-Test erfolgreich: Entpacken, Installation, Start/Core, Deinstallation, Benutzerdaten erhalten.'
} catch {
    Write-Host "::error::$($_.Exception.Message)"
    $log = Join-Path $env:APPDATA 'GenesisMediaManager\core-service.log'
    if (Test-Path $log) { Get-Content $log -Tail 50 }
    throw
} finally {
    # Nur Prozesse der Testinstallation entfernen, nicht beliebige
    # fremde Python-Prozesse des Runners.
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$installDir*backend*run_api.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Get-Process -Name GenesisMediaManager -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $client } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Remove-Item $sentinel -ErrorAction SilentlyContinue
    Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue
}
