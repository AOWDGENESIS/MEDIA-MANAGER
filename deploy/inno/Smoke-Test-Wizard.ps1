#Requires -Version 7.0
<#
.SYNOPSIS
    Inno-Wizard mit vorgegebenem Zielpfad samt Leerzeichen per echte
    Windows-Buttons bedienen, installieren, starten, updaten, deinstallieren.
    Der Windows-CI-Runner stellt VCL-Buttons nicht immer ueber UI Automation
    bereit; daher per Win32-Kindfenster und BM_CLICK.
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
    public static bool HasText(IntPtr parent, string expected) {
        bool found = false;
        EnumChildWindows(parent, (hwnd, param) => {
            var text = new StringBuilder(512);
            GetWindowText(hwnd, text, text.Capacity);
            if (string.Equals(text.ToString().TrimEnd('\\'), expected.TrimEnd('\\'),
                StringComparison.OrdinalIgnoreCase) && IsWindowVisible(hwnd)) found = true;
            return true;
        }, IntPtr.Zero);
        return found;
    }
    public static void Click(IntPtr hwnd) { SendMessage(hwnd, 0x00F5, IntPtr.Zero, IntPtr.Zero); }
}
'@
$setup = Join-Path $repoRoot 'build\GenesisMediaManager-Inno-Setup.exe'
# Anders als der stille Inno-Test: echter Wizard, explizit ein Ziel mit
# Leerzeichen ausserhalb des Standardverzeichnisses.
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\Genesis Media Manager CI'
$client = Join-Path $installDir 'client\GenesisMediaManager.exe'
$uninstall = Join-Path $installDir 'unins000.exe'
$log = Join-Path $env:RUNNER_TEMP 'genesis-inno-wizard.log'
$sentinel = Join-Path $env:APPDATA 'GenesisMediaManager\ci-wizard-keep-data.txt'
if (Test-Path $installDir) { throw 'GUI-Wizard braucht einen freien Installationsordner' }
$p = $null
$wizardProcess = $null
try {
    $p = Start-Process -FilePath $setup -ArgumentList @(
        '/NORESTART', ('/DIR="' + $installDir + '"'), ('/LOG="' + $log + '"')
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
    $pathSeen = $false
    for ($i=0; $i -lt 150; $i++) {
        $p.Refresh()
        if ($p.HasExited) { break }
        if (-not $pathSeen -and [WizardControls]::HasText($handle, $installDir)) {
            $pathSeen = $true
            Write-Host '::notice::Inno-Wizard zeigt den frei gewaehlten Installationspfad mit Leerzeichen'
        }
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
    if (-not $pathSeen -or $clicks.Count -lt 3 -or -not (Test-Path $client) -or
        -not (Test-Path $uninstall)) {
        throw "Wizard-Pfad/Klicks/Installation unvollstaendig: Pfad=$pathSeen, $($clicks -join ' -> ')"
    }
    if (Test-Path (Join-Path $env:LOCALAPPDATA 'Programs\GenesisMediaManager\client\GenesisMediaManager.exe')) {
        throw 'Wizard hat unerwartet in den Standardordner installiert'
    }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $installDir 'installer\Test-OfflineRuntime.ps1') -InstallDir $installDir
    if ($LASTEXITCODE -ne 0) { throw 'Offline-Runtime nach Wizard-Installation fehlgeschlagen' }
    New-Item -ItemType Directory -Force -Path (Split-Path $sentinel) | Out-Null
    Set-Content -Path $sentinel -Value 'Wizard-Test: Daten erhalten'
    # Ein Update darf den bisherigen Pfad nicht stillschweigend verlassen.
    $otherDir = Join-Path $env:LOCALAPPDATA 'Programs\Genesis Media Manager Wrong Path'
    if (Test-Path $otherDir) { throw "Negativtest braucht freien Ordner: $otherDir" }
    $move = Start-Process -FilePath $setup -ArgumentList @(
        '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
        ('/DIR="' + $otherDir + '"')
    ) -PassThru -Wait
    if ($move.ExitCode -eq 0 -or (Test-Path (Join-Path $otherDir 'client\GenesisMediaManager.exe')) -or
        -not (Test-Path $client) -or -not (Test-Path $sentinel)) {
        throw "Inno hat einen nicht autorisierten Pfadwechsel zugelassen: Code $($move.ExitCode)"
    }
    Write-Host '::notice::Inno blockiert Umzug per Update ohne vorherige Deinstallation'
    $update = Start-Process -FilePath $setup -ArgumentList @(
        '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
        ('/DIR="' + $installDir + '"')
    ) -PassThru -Wait
    if ($update.ExitCode -ne 0 -or -not (Test-Path $client) -or
        -not (Test-Path $sentinel)) {
        throw "Update am gewaehlten Pfad fehlgeschlagen: $($update.ExitCode)"
    }
    Write-Host '::notice::Inno-Update am benutzergewaehlten Pfad bestanden'
    # Derselbe Startmenue-Pfad muss den lokalen Core auch mit Leerzeichen
    # im Installationsort erreichen. Der Uninstaller stoppt danach Core/UI.
    $startBat = Join-Path $installDir 'Start-GenesisMediaManager.bat'
    & $env:ComSpec /d /c ('"' + $startBat + '"')
    if ($LASTEXITCODE -ne 0) { throw "Wizard-Launcher fehlgeschlagen: $LASTEXITCODE" }
    $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8420/health' -TimeoutSec 5 -NoProxy
    if ($health.status -ne 'ok') { throw 'Wizard-Launcher hat keinen Core gestartet' }
    $u = Start-Process -FilePath $uninstall -ArgumentList @(
        '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'
    ) -PassThru -Wait
    if ($u.ExitCode -ne 0 -or (Test-Path $client) -or (Test-Path (Join-Path $installDir 'runtime\python\python.exe')) -or
        -not (Test-Path $sentinel)) {
        throw 'Wizard-Installation nicht sauber deinstalliert oder Benutzerdaten geloescht'
    }
    Write-Host "Wizard-Pfad-/Klicktest bestanden: $installDir; $($clicks -join ' -> ')"
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
    Remove-Item $sentinel -ErrorAction SilentlyContinue
}
