#Requires -Version 5.1
<#
.SYNOPSIS
    Beendet NUR Prozesse der angegebenen GENESIS-Installation.
.DESCRIPTION
    Wird vom Inno-Uninstaller vor dem Entfernen von client/ und .venv/
    aufgerufen. Andere Python-Prozesse und andere Client-Installationen
    bleiben unberuehrt. Nutzerdaten unter %APPDATA% werden nie geloescht.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$InstallDir,
    [switch]$RemoveVenv
)

$ErrorActionPreference = 'Stop'
$clientExe = [IO.Path]::GetFullPath((Join-Path $InstallDir 'client\GenesisMediaManager.exe'))
$backendScript = [IO.Path]::GetFullPath((Join-Path $InstallDir 'backend\run_api.py'))
$running = Get-CimInstance Win32_Process -Filter `
    "Name = 'GenesisMediaManager.exe' OR Name = 'python.exe' OR Name = 'pythonw.exe'"

foreach ($process in $running) {
    $isClient = $process.ExecutablePath -and
        [string]::Equals($process.ExecutablePath, $clientExe,
            [StringComparison]::OrdinalIgnoreCase)
    # Der venv-Launcher und sein Python-Kindprozess tragen beide das
    # absolute run_api.py in der CommandLine. Kein globales taskkill python.
    $isCore = $process.CommandLine -and
        ($process.CommandLine.IndexOf($backendScript, [StringComparison]::OrdinalIgnoreCase) -ge 0)
    if ($isClient -or $isCore) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
# Warten, bis Windows Dateisperren (DLLs, .venv) freigegeben hat.
Start-Sleep -Milliseconds 700
if ($RemoveVenv) {
    # Nur beim MSI-Uninstall; Inno entfernt .venv mit [UninstallDelete].
    # Die Laufzeitdateien stammen von pip und werden NICHT vom MSI verwaltet.
    $venv = Join-Path $InstallDir '.venv'
    if (Test-Path $venv) { Remove-Item -LiteralPath $venv -Recurse -Force -ErrorAction Stop }
}
