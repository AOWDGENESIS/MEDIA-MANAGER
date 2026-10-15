#Requires -Version 7.0
<#
.SYNOPSIS
    Bedienungs-Smoke-Test der echten WPF-Oberflaeche unter Windows.
    Waehlt Navigationseintraege ueber UI Automation (SelectionItemPattern),
    wie ein Benutzer ueber den sichtbaren Navigationsbaum, und prueft
    Fenster/Crash-Log nach jedem Schritt. Kein Pixel-/Screenshotvergleich.
#>
[CmdletBinding()]
param([Parameter(Mandatory)][int]$ClientProcessId)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName UIAutomationClient
$client = Get-Process -Id $ClientProcessId -ErrorAction Stop
$client.Refresh()
if ($client.MainWindowHandle -eq [IntPtr]::Zero) { throw 'Kein WPF-Hauptfenster fuer UI-Test' }
$root = [System.Windows.Automation.AutomationElement]::FromHandle($client.MainWindowHandle)
if (-not $root) { throw 'WPF-Fenster nicht fuer Windows UI Automation erreichbar' }
$crashLog = Join-Path $env:APPDATA 'GenesisMediaManager\client-crash.log'
# Alle eindeutigen Eintraege aus MainWindow.NavStructure. Seitenaktionen
# wie Import oder Loeschen benoetigen Testdaten/Einwilligung und gehoeren
# NICHT zu einem destruktiven Klicktest auf echten Medien.
$keys = @(
    'nav.dashboard',
    'nav.music', 'nav.audiobook', 'nav.movie', 'nav.episode', 'nav.podcast',
    'nav.ai_music', 'nav.unknown',
    'nav.search', 'nav.artists', 'nav.albums', 'nav.titles', 'nav.genres',
    'nav.persons', 'nav.sources',
    'nav.media_analysis', 'nav.metadata_editor', 'nav.rename',
    'nav.loudness', 'nav.cutter', 'nav.convert', 'nav.audio_recognition',
    'nav.duplicates', 'nav.quality_check', 'nav.artwork',
    'nav.download_center', 'nav.import',
    'nav.ai_metadata', 'nav.ai_audio_analysis', 'nav.voice_studio', 'nav.tts',
    'nav.settings', 'nav.databases', 'nav.providers', 'nav.plugins',
    'nav.licenses', 'nav.logs', 'nav.backups', 'nav.diagnostics',
    'nav.job_queue', 'nav.error_center'
)
foreach ($key in $keys) {
    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, $key)
    $element = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
    if (-not $element) { throw "UI-Navigationspunkt fehlt: $key" }
    $pattern = [System.Windows.Automation.SelectionItemPattern]$element.GetCurrentPattern(
        [System.Windows.Automation.SelectionItemPattern]::Pattern)
    $pattern.Select()
    Start-Sleep -Milliseconds 200
    $client.Refresh()
    if ($client.HasExited) { throw "WPF-Client nach Auswahl $key abgestuerzt" }
    if (Test-Path $crashLog) { throw "WPF-Crashlog nach Auswahl $key vorhanden" }
    if ($key -in @('nav.dashboard', 'nav.music', 'nav.settings', 'nav.error_center')) {
        Write-Host "::notice::UI-Navigation gewaehlt: $key"
    }
}
Start-Sleep -Seconds 2
$client.Refresh()
if ($client.HasExited -or (Test-Path $crashLog)) { throw 'WPF-Client nach UI-Navigation nicht stabil' }
Write-Host "UI-Smoke-Test: $($keys.Count) Navigationspunkte ueber Windows UI Automation ausgewaehlt; kein Crash."
