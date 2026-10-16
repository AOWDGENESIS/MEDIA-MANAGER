#Requires -Version 7.0
<#
.SYNOPSIS
    Echte Inno-Wizard-Buttons ueber Windows UI Automation betaetigen.
    Separater CI-Test nach dem stillen Inno-Test; keine Nutzerdateien.
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $repoRoot 'deploy\installer\Set-OfflineTestEnvironment.ps1')
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName UIAutomationClient
$setup = Join-Path $repoRoot 'build\GenesisMediaManager-Inno-Setup.exe'
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\GenesisMediaManager'
$client = Join-Path $installDir 'client\GenesisMediaManager.exe'
$uninstall = Join-Path $installDir 'unins000.exe'
$log = Join-Path $env:RUNNER_TEMP 'genesis-inno-wizard.log'
if (Test-Path $client) { throw 'GUI-Wizard braucht eine frische Installation' }
$p = $null
try {
    $p = Start-Process -FilePath $setup -ArgumentList @(
        '/NORESTART', ('/LOG="' + $log + '"')
    ) -PassThru
    $window = $null
    for ($i=0; $i -lt 30; $i++) {
        $p.Refresh()
        if ($p.HasExited) { throw "Setup-Wizard vorzeitig beendet: $($p.ExitCode)" }
        if ($p.MainWindowHandle -ne [IntPtr]::Zero) {
            $window = [System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
            if ($window) { break }
        }
        Start-Sleep -Seconds 1
    }
    if (-not $window) { throw 'Inno-Setup-Fenster nicht fuer Benutzerinteraktion erreichbar' }
    $clicks = @()
    for ($i=0; $i -lt 150; $i++) {
        $p.Refresh()
        if ($p.HasExited) { break }
        $condition = [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Button)
        $buttons = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
        $target = $null
        foreach ($button in $buttons) {
            if ($button.Current.IsEnabled -and -not $button.Current.IsOffscreen -and
                $button.Current.Name -match '(Weiter|Installieren|Fertigstellen|Next|Install|Finish)') {
                $target = $button
                break
            }
        }
        if ($target) {
            $name = $target.Current.Name
            $pattern = [System.Windows.Automation.InvokePattern]$target.GetCurrentPattern(
                [System.Windows.Automation.InvokePattern]::Pattern)
            $pattern.Invoke()
            $clicks += $name
            Write-Host "::notice::Inno-Wizard geklickt: $name"
            Start-Sleep -Seconds 2
        } else {
            Start-Sleep -Seconds 2
        }
    }
    $p.Refresh()
    if (-not $p.HasExited) { throw 'GUI-Wizard hat nach 5 Minuten nicht abgeschlossen' }
    if ($p.ExitCode -ne 0) { throw "GUI-Wizard Exit-Code $($p.ExitCode)" }
    if ($clicks.Count -lt 2 -or -not (Test-Path $client) -or -not (Test-Path $uninstall)) {
        throw "Wizard-Klicks/Installation unvollstaendig: $($clicks -join ' -> ')"
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $installDir 'installer\Test-OfflineRuntime.ps1') -InstallDir $installDir
    if ($LASTEXITCODE -ne 0) { throw 'Offline-Runtime nach Wizard-Installation fehlgeschlagen' }
    $u = Start-Process -FilePath $uninstall -ArgumentList @(
        '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'
    ) -PassThru -Wait
    if ($u.ExitCode -ne 0 -or (Test-Path $client)) { throw 'Wizard-Installation nicht sauber deinstalliert' }
    Write-Host "Wizard-Klicktest bestanden: $($clicks -join ' -> ')"
} catch {
    $msg = ($_.Exception.Message -replace '%','%25') -replace '[\r\n]+',' '
    Write-Host "::error::Inno-Wizard: $msg"
    if (Test-Path $log) { Get-Content $log -Tail 12 | ForEach-Object { Write-Host "::error::Inno-Wizard-Log: $_" } }
    throw
} finally {
    if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    Get-Process -Name GenesisMediaManager -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $client } |
        Stop-Process -Force -ErrorAction SilentlyContinue
}
