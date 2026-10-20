#Requires -Version 5.1
<#
.SYNOPSIS
    Prueft die Windows-Uninstall-Registrierung des aktuellen Benutzers.
.DESCRIPTION
    Registry-Nachweis fuer "Installierte Apps", kein Ersatz fuer die
    visuelle Kontrolle in Windows-Einstellungen auf dem Ziel-PC.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('Inno', 'ZIP')][string]$Installer,
    [Parameter(Mandatory)][string]$InstallDir,
    [switch]$Absent
)
$ErrorActionPreference = 'Stop'
$keyName = if ($Installer -eq 'Inno') {
    '{D9F1FF8F-8DD4-4C55-A656-6B3B01B79466}_is1'
} else { 'GenesisMediaManager' }
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$keyName"
if ($Absent) {
    if (Test-Path -LiteralPath $key) { throw "$Installer-Uninstall-Eintrag nach Deinstallation verblieben: $key" }
    Write-Host "::notice::$Installer-Uninstall-Eintrag nach Deinstallation entfernt"
    return
}
if (-not (Test-Path -LiteralPath $key)) { throw "$Installer fehlt unter Windows-Uninstall (HKCU): $key" }
$entry = Get-ItemProperty -LiteralPath $key -ErrorAction Stop
$expectedScript = if ($Installer -eq 'Inno') { 'unins000.exe' } else { 'Uninstall-GenesisMediaManager.ps1' }
$uninstaller = Join-Path $InstallDir $expectedScript
if ($entry.DisplayName -ne 'GENESIS Media Manager' -or
    -not $entry.DisplayVersion -or
    -not $entry.UninstallString -or
    $entry.UninstallString -notlike "*$expectedScript*" -or
    -not $entry.InstallLocation -or
    $entry.InstallLocation.TrimEnd('\') -ine $InstallDir.TrimEnd('\') -or
    $entry.SystemComponent -eq 1 -or $entry.NoRemove -eq 1 -or
    $entry.ParentKeyName -or
    -not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
    throw "$Installer-Uninstall-Eintrag unvollstaendig/verborgen oder falscher Pfad: $key"
}
Write-Host "::notice::$Installer unter HKCU-Uninstall registriert: $($entry.DisplayName), Version=$($entry.DisplayVersion), Pfad=$($entry.InstallLocation), Uninstaller vorhanden"
