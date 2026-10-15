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
. (Join-Path $repoRoot 'deploy\installer\Set-OfflineTestEnvironment.ps1')
$setup = Join-Path $repoRoot 'build\GenesisMediaManager-Inno-Setup.exe'
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\GenesisMediaManager'
$uninstall = Join-Path $installDir 'unins000.exe'
$python = Join-Path $installDir 'runtime\python\python.exe'
$dataDir = Join-Path $env:APPDATA 'GenesisMediaManager'
$sentinel = Join-Path $dataDir 'ci-keep-user-data.txt'
$log = Join-Path $env:RUNNER_TEMP 'genesis-inno-install.log'
$msiConflictLog = Join-Path $env:RUNNER_TEMP 'genesis-msi-conflict.log'
$apiError = Join-Path $env:RUNNER_TEMP 'genesis-inno-api-stderr.log'
$apiOutput = Join-Path $env:RUNNER_TEMP 'genesis-inno-api-stdout.log'
$testData = Join-Path $env:RUNNER_TEMP 'genesis-smoke-data'
$apiProcess = $null
$startBat = Join-Path $installDir 'Start-GenesisMediaManager.bat'

function Get-InstalledCoreProcesses {
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$installDir*backend*run_api.py*" }
}

function Stop-InstalledProcesses {
    # Vor Update/Deinstallation nur die Prozesse DIESER Testinstallation
    # beenden; keine fremden lokalen Python-Services stoppen.
    Get-Process -Name GenesisMediaManager -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Get-InstalledCoreProcesses |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

if (-not (Test-Path $setup)) { throw "Setup-EXE fehlt: $setup" }
if (Test-Path $installDir) { throw "CI-Test braucht ein frisches Benutzerprofil: $installDir existiert bereits" }

try {
    Write-Host "Installiere Inno-Setup-EXE: $setup"
    # PowerShell wartet bei GUI-EXEs mit dem Call-Operator nicht immer auf
    # das Prozessende; -Wait/-PassThru liefert den echten Installer-Code.
    Write-Host '::notice::Inno-Offline-Test: Starte Setup-EXE ohne System-Python/Internet'
    $installProcess = Start-Process -FilePath $setup -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/LOG="' + $log + '"')
    ) -PassThru
    $finished = $false
    for ($minute = 1; $minute -le 16; $minute++) {
        if ($installProcess.WaitForExit(60000)) { $finished = $true; break }
        $clientCopied = Test-Path (Join-Path $installDir 'client\GenesisMediaManager.exe')
        $pythonCopied = Test-Path $python
        $toolsCopied = Test-Path (Join-Path $installDir 'runtime\tools\ffmpeg\ffmpeg.exe')
        Write-Host "::notice::Inno-Setup $minute min aktiv; Client=$clientCopied Python=$pythonCopied FFmpeg=$toolsCopied"
    }
    if (-not $finished) {
        $children = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'Test-OfflineRuntime' } |
            ForEach-Object { $_.CommandLine }
        Write-Host "::error::Inno-Setup Zeitlimit; Offline-Pruefprozesse: $($children -join '; ')"
        throw 'Inno-Setup hat nach 16 Minuten noch nicht abgeschlossen'
    }
    if ($installProcess.ExitCode -ne 0) { throw "Setup-EXE: Exit-Code $($installProcess.ExitCode)" }
    Write-Host '::notice::Inno-Offline-Test: Setup-EXE erfolgreich abgeschlossen'

    foreach ($path in @(
        (Join-Path $installDir 'client\GenesisMediaManager.exe'),
        (Join-Path $installDir 'backend\run_api.py'),
        (Join-Path $installDir 'Start-GenesisMediaManager.bat'),
        (Join-Path $installDir 'runtime\tools\ffmpeg\ffmpeg.exe'),
        (Join-Path $installDir 'runtime\tools\ffmpeg\ffprobe.exe'),
        (Join-Path $installDir 'runtime\tools\chromaprint\fpcalc.exe'),
        $python,
        $uninstall
    )) {
        if (-not (Test-Path $path)) { throw "Fehlende Installationsdatei: $path" }
    }

    # Negativer Konflikttest: Ein MSI im selben Zielordner muss die
    # bestehende Inno-Installation ablehnen, BEVOR es Dateien veraendert.
    $msi = Join-Path $repoRoot 'build\package\GenesisMediaManager-Setup.msi'
    if (-not (Test-Path $msi)) { throw "MSI fuer Konflikttest fehlt: $msi" }
    Write-Host 'Pruefe MSI-Sperre gegen bestehende Inno-Installation'
    $msiAttempt = Start-Process -FilePath 'msiexec.exe' -ArgumentList @(
        '/i', ('"' + $msi + '"'), '/qn', '/norestart', '/l*v', ('"' + $msiConflictLog + '"')
    ) -Wait -PassThru
    if ($msiAttempt.ExitCode -eq 0) { throw 'MSI wurde trotz bestehender Inno-Installation installiert' }
    if (-not (Test-Path $msiConflictLog) -or
        -not (Select-String -Path $msiConflictLog -Pattern 'GENESIS Media Manager ist bereits per Inno Setup' -Quiet)) {
        throw "MSI wurde nicht eindeutig durch die Inno-Konfliktsperre abgewiesen (Code $($msiAttempt.ExitCode))"
    }
    if (-not (Test-Path $uninstall)) { throw 'MSI-Konflikttest hat den Inno-Uninstaller veraendert' }

    Write-Host 'Pruefe Offline-Runtime ohne globales Python, Internet oder pip'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $installDir 'installer\Test-OfflineRuntime.ps1') -InstallDir $installDir
    if ($LASTEXITCODE -ne 0) { throw 'Mitgelieferte Offline-Runtime unvollstaendig' }

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
    # Windows-venv-Python kann beim Start noch einen Interpreter-Kindprozess
    # erzeugen; den ebenfalls beenden, bevor der eigentliche Launcher laeuft.
    Stop-InstalledProcesses

    # Auch ohne Core muss das Hauptfenster zeitnah erscheinen. Die
    # Sprach-Einstellung ist optional; bei Ausfall zeigt das Dashboard
    # spaeter einen Fehler statt den UI-Thread zu blockieren.
    Write-Host 'Pruefe Client-Fenster ohne laufende Core-API'
    $offlineClient = Start-Process -FilePath (Join-Path $installDir 'client\GenesisMediaManager.exe') -PassThru
    $offlineWindowReady = $false
    for ($i = 0; $i -lt 10; $i++) {
        $offlineClient.Refresh()
        if ($offlineClient.HasExited) { throw 'Client ohne Core direkt nach Start beendet' }
        if ($offlineClient.MainWindowHandle -ne [IntPtr]::Zero) {
            $offlineWindowReady = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $offlineWindowReady) { throw 'Client ohne Core hat nach zehn Sekunden kein Hauptfenster' }
    Stop-Process -Id $offlineClient.Id -Force -ErrorAction SilentlyContinue
    if (-not $offlineClient.WaitForExit(10000)) { throw 'Offline-Client konnte nicht beendet werden' }
    $offlineClient = $null

    # Entscheidend fuer den Nutzer: den per Startmenue verlinkten Batch-Pfad
    # pruefen, nicht nur run_api.py direkt. Die WPF-UI kann auf einem
    # CI-Runner nicht visuell abgenommen werden.
    Write-Host 'Starte den mitgelieferten Start-GenesisMediaManager.bat'
    & $env:ComSpec /d /c ('"' + $startBat + '"')
    if ($LASTEXITCODE -ne 0) { throw "Startskript: Exit-Code $LASTEXITCODE" }
    $startedHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8420/health' -TimeoutSec 5
    if ($startedHealth.status -ne 'ok') { throw 'Startskript hat den Core-Service nicht gestartet' }
    Write-Host 'Startskript: lokale Core-API antwortet mit status ok'

    # Die API allein beweist noch nicht, dass auch der WPF-Client startet.
    # In CI ist keine visuelle Abnahme moeglich, wohl aber Prozess-Liveness
    # und der eigene Crash-Log des Clients.
    $clientExe = Join-Path $installDir 'client\GenesisMediaManager.exe'
    $clientCrashLog = Join-Path $dataDir 'client-crash.log'
    $clientReady = $false
    for ($i = 0; $i -lt 10; $i++) {
        if (Test-Path $clientCrashLog) { throw "Client hat einen Startfehler protokolliert: $clientCrashLog" }
        $client = @(Get-Process -Name GenesisMediaManager -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -eq $clientExe })
        if ($client.Count -gt 0) { $clientReady = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $clientReady) { throw 'Client-Prozess startet nach dem Launcher nicht' }
    Start-Sleep -Seconds 2
    $clientAlive = @(Get-Process -Name GenesisMediaManager -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $clientExe })
    if ((Test-Path $clientCrashLog) -or ($clientAlive.Count -eq 0)) {
        throw 'Client-Prozess ist unmittelbar nach dem Start abgestuerzt/beendet'
    }
    Write-Host 'WPF-Client-Prozess gestartet und nach zwei Sekunden noch aktiv'

    # MainWindow.Show() muss ausserdem ein echtes Top-Level-HWND erzeugen.
    # Das ist staerker als reine Prozess-Liveness, aber keine Pruefung von
    # Farben, Layout oder Bedienbarkeit auf dem Nutzer-Desktop.
    $windowReady = $false
    for ($i = 0; $i -lt 12; $i++) {
        if (Test-Path $clientCrashLog) { throw "Client-Startfehler: $clientCrashLog" }
        $windows = @(Get-Process -Name GenesisMediaManager -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -eq $clientExe })
        foreach ($candidate in $windows) {
            $candidate.Refresh()
            if ($candidate.MainWindowHandle -ne [IntPtr]::Zero) {
                $windowReady = $true
                Write-Host "WPF-Hauptfenster angelegt (PID $($candidate.Id), HWND $($candidate.MainWindowHandle))"
                break
            }
        }
        if ($windowReady) { break }
        Start-Sleep -Seconds 1
    }
    if (-not $windowReady) { throw 'WPF-Client-Prozess laeuft, aber kein Hauptfenster-Handle gefunden' }

    # Die Oberflaeche wirklich ueber ihre UI-Automation-Navigation
    # bedienen, nicht nur einen Prozess oder ein HWND zaehlen.
    & (Join-Path $repoRoot 'deploy\inno\Smoke-Test-UI.ps1') -ClientProcessId $candidate.Id

    # Zweiter Doppelklick bei laufendem Service darf keinen zweiten
    # pythonw-Prozess starten oder dessen Logdatei ueberschreiben.
    $coreBefore = @(Get-InstalledCoreProcesses)
    if ($coreBefore.Count -lt 1) { throw 'Kein installierter Core-Prozess nach erstem Start gefunden' }
    # venv-Launcher + Interpreter koennen als zwei Windows-Prozesse sichtbar
    # sein. Entscheidend ist, dass beim Zweitstart KEINE neuen PIDs entstehen.
    $pidsBefore = @(($coreBefore | ForEach-Object { $_.ProcessId }) | Sort-Object)
    Write-Host "Core-PIDs vor Zweitstart: $($pidsBefore -join ', ')"
    # Nicht per @(...)-Pipeline auffangen: von cmd gestartete GUI-Prozesse
    # koennen die geerbte stdout-Pipe offen halten und CI blockieren.
    & $env:ComSpec /d /c ('"' + $startBat + '"')
    if ($LASTEXITCODE -ne 0) { throw "Zweiter Start: Exit-Code $LASTEXITCODE" }
    $pidsAfter = @((Get-InstalledCoreProcesses | ForEach-Object { $_.ProcessId }) | Sort-Object)
    if (($pidsAfter -join ',') -ne ($pidsBefore -join ',')) {
        throw "Zweiter Start hat die Core-Prozesse veraendert: vorher $($pidsBefore -join ',') / nachher $($pidsAfter -join ',')"
    }
    Write-Host 'Zweiter Start: dieselben Core-Prozesse bleiben aktiv'
    Stop-InstalledProcesses

    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    Set-Content -Path $sentinel -Value 'Mediathek-Daten erhalten'

    # Ein zweiter Setup-Lauf muss als Update funktionieren, ohne die unter
    # %APPDATA% gespeicherten Nutzerdaten oder den Uninstaller zu beschaedigen.
    Write-Host 'Pruefe erneute Installation (Update)'
    $updateProcess = Start-Process -FilePath $setup -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/LOG="' + $log + '"')
    ) -Wait -PassThru
    if ($updateProcess.ExitCode -ne 0) { throw "Update: Exit-Code $($updateProcess.ExitCode)" }
    if (-not (Test-Path $python)) { throw 'Portable Python-Runtime nach Update nicht vorhanden' }
    if (-not (Test-Path $sentinel)) { throw 'Update hat Benutzerdaten geloescht' }

    # Anders als bisher: Bei der Deinstallation laufen App UND Core noch.
    # Inno muss den Core vor dem Entfernen des nicht getrackten venv stoppen.
    Write-Host 'Starte App/Core fuer den Deinstallations-Test erneut'
    & $env:ComSpec /d /c ('"' + $startBat + '"')
    if ($LASTEXITCODE -ne 0) { throw "Start vor Deinstallation: Exit-Code $LASTEXITCODE" }
    $healthBeforeUninstall = Invoke-RestMethod -Uri 'http://127.0.0.1:8420/health' -TimeoutSec 5
    if ($healthBeforeUninstall.status -ne 'ok' -or @(Get-InstalledCoreProcesses).Count -lt 1) {
        throw 'Core-Service laeuft vor dem Uninstall-Test nicht'
    }

    Write-Host 'Deinstalliere Inno-Setup-Paket bei laufender App und laufendem Core'
    $uninstallProcess = Start-Process -FilePath $uninstall -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
    ) -Wait -PassThru
    if ($uninstallProcess.ExitCode -ne 0) { throw "Deinstallation: Exit-Code $($uninstallProcess.ExitCode)" }
    if (Test-Path $python) { throw 'Uninstaller hat die portable Python-Runtime nicht entfernt' }
    if (Test-Path (Join-Path $installDir 'runtime\tools\ffmpeg\ffmpeg.exe')) {
        throw 'Uninstaller hat ffmpeg hinterlassen'
    }
    if (Test-Path (Join-Path $installDir 'client\GenesisMediaManager.exe')) { throw 'Uninstaller hat den Client nicht entfernt' }
    if (@(Get-InstalledCoreProcesses).Count -gt 0) { throw 'Uninstaller hat einen laufenden Core-Prozess hinterlassen' }
    if (-not (Test-Path $sentinel)) { throw 'Uninstaller hat Benutzerdaten geloescht' }
    Write-Host 'Smoke-Test erfolgreich: Installation, Startskript, Core-API, Update, Deinstallation, Benutzerdaten erhalten.'
} catch {
    Write-Host "::error::$($_.Exception.Message)"
    if (Test-Path $log) { Get-Content $log -Tail 70 }
    if (Test-Path $msiConflictLog) {
        Select-String -Path $msiConflictLog -Pattern 'Launch|GENESIS|Error|Fehler' |
            Select-Object -Last 30 | ForEach-Object { Write-Host $_.Line }
    }
    if (Test-Path $apiError) { Get-Content $apiError -Tail 70 }
    $coreLog = Join-Path $dataDir 'core-service.log'
    if (Test-Path $coreLog) { Get-Content $coreLog -Tail 70 }
    $clientCrashLog = Join-Path $dataDir 'client-crash.log'
    if (Test-Path $clientCrashLog) { Get-Content $clientCrashLog -Tail 70 }
    throw
} finally {
    if ($apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Stop-InstalledProcesses
    Remove-Item $sentinel -ErrorAction SilentlyContinue
}
