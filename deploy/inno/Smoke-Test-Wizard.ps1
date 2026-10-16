#Requires -Version 7.0
<#
.SYNOPSIS
    Inno-Wizard ueber seine echten Windows-Buttons installieren und deinstallieren.
    Der Windows-CI-Runner stellt VCL-Buttons nicht immer ueber UI Automation bereit;
    daher per Win32-Kindfenster und BM_CLICK statt blindem Tastatur-Senden.
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $repoRoot 'deploy\installer\Set-OfflineTestEnvironment.ps1')
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class WizardControls {
    public class Button { public IntPtr Handle; public string Text; public string ClassName; public bool Enabled; public bool Visible; }
    private delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr param);
    [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr parent, EnumWindowsProc callback, IntPtr param);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int length);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetClassName(IntPtr hwnd, StringBuilder text, int length);
    [DllImport("user32.dll")] private static extern bool IsWindowEnabled(IntPtr hwnd);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] private static extern IntPtr SendMessage(IntPtr hwnd, uint message, IntPtr wparam, IntPtr lparam);
    public static List<Button> GetButtons(IntPtr parent) {
        var result = new List<Button>();
        EnumChildWindows(parent, (hwnd, param) => {
            var cls = new StringBuilder(256);
            GetClassName(hwnd, cls, cls.Capacity);
            if (cls.ToString().IndexOf("Button", StringComparison.OrdinalIgnoreCase) < 0) return true;
            var text = new StringBuilder(512);
            GetWindowText(hwnd, text, text.Capacity);
            result.Add(new Button { Handle = hwnd, Text = text.ToString(), ClassName = cls.ToString(),
                Enabled = IsWindowEnabled(hwnd), Visible = IsWindowVisible(hwnd) });
            return true;
        }, IntPtr.Zero);
        return result;
    }
    public static void Click(IntPtr hwnd) { SendMessage(hwnd, 0x00F5, IntPtr.Zero, IntPtr.Zero); }
}
'@
$setup = Join-Path $repoRoot 'build\GenesisMediaManager-Inno-Setup.exe'
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\GenesisMediaManager'
$client = Join-Path $installDir 'client\GenesisMediaManager.exe'
$uninstall = Join-Path $installDir 'unins000.exe'
$log = Join-Path $env:RUNNER_TEMP 'genesis-inno-wizard.log'
if (Test-Path $client) { throw 'GUI-Wizard braucht eine frische Installation' }
$p = $null
$wizardProcess = $null
try {
    $p = Start-Process -FilePath $setup -ArgumentList @(
        '/NORESTART', ('/LOG="' + $log + '"')
    ) -PassThru
    $handle = [IntPtr]::Zero
    for ($i=0; $i -lt 45; $i++) {
        $p.Refresh()
        if ($p.HasExited) { throw "Setup-Wizard vorzeitig beendet: $($p.ExitCode)" }
        # Die aeussere Inno-EXE entpackt einen .tmp-Kindprozess, der das
        # eigentliche Wizard-Fenster haelt. Erst diesen Prozess suchen.
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($p.Id)" -ErrorAction SilentlyContinue)
        $candidates = @($children | ForEach-Object {
            Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
        }) + @($p)
        foreach ($candidate in $candidates) {
            $candidate.Refresh()
            if ($candidate.HasExited -or $candidate.MainWindowHandle -eq [IntPtr]::Zero) { continue }
            $found = [WizardControls]::GetButtons($candidate.MainWindowHandle)
            if ($found.Count -gt 0) {
                $wizardProcess = $candidate
                $handle = $candidate.MainWindowHandle
                break
            }
        }
        if ($handle -ne [IntPtr]::Zero) { break }
        Start-Sleep -Seconds 1
    }
    if ($handle -eq [IntPtr]::Zero) {
        $diagnostics = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($p.Id)" -ErrorAction SilentlyContinue |
            ForEach-Object { "$($_.ProcessId):$($_.Name):$($_.CommandLine)" })
        Write-Host "::error::Inno-Kindprozesse ohne native Buttons: $($diagnostics -join '; ')"
        throw 'Inno-Setup-Fenster nicht fuer Benutzerinteraktion erreichbar'
    }
    Write-Host "::notice::Inno-Wizard-Fenster gefunden: PID=$($wizardProcess.Id), HWND=$handle"
    $clicks = @()
    for ($i=0; $i -lt 150; $i++) {
        $p.Refresh()
        if ($p.HasExited) { break }
        $buttons = [WizardControls]::GetButtons($handle)
        if ($i -eq 0 -or $i -eq 10) {
            $buttonInfo = @($buttons | ForEach-Object {
                "$($_.Text) [$($_.ClassName), enabled=$($_.Enabled), visible=$($_.Visible)]"
            })
            Write-Host "::notice::Inno-Wizard-Buttons: $($buttonInfo -join '; ')"
        }
        $target = $buttons | Where-Object {
            $_.Enabled -and $_.Visible -and $_.Text -match '(Weiter|Installieren|Fertigstellen|Next|Install|Finish)'
        } | Select-Object -First 1
        if ($target) {
            $name = $target.Text
            [WizardControls]::Click($target.Handle)
            $clicks += $name
            Write-Host "::notice::Inno-Wizard geklickt: $name"
        }
        Start-Sleep -Seconds 2
    }
    $p.Refresh()
    if (-not $p.HasExited) { throw "GUI-Wizard hat nach 5 Minuten nicht abgeschlossen: $($clicks -join ' -> ')" }
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
    if ($wizardProcess -and -not $wizardProcess.HasExited) {
        Stop-Process -Id $wizardProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    Get-Process -Name GenesisMediaManager -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $client } |
        Stop-Process -Force -ErrorAction SilentlyContinue
}
