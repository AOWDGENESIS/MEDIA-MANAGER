@echo off
REM Startet zuerst den lokalen Core-Service (bindet nur an 127.0.0.1, kein
REM Cloud-Zugriff - siehe ARCHITECTURE.md, ADR-0001), danach die
REM Benutzeroberflaeche. Schliessen dieses Fensters beendet NICHT den
REM Core-Service (eigener Hintergrundprozess) - zum Beenden Task-Manager
REM verwenden oder den Rechner neu starten.
setlocal enabledelayedexpansion
set "INSTALLDIR=%~dp0"
set "DATADIR=%APPDATA%\GenesisMediaManager"
if not exist "%DATADIR%" mkdir "%DATADIR%" >nul 2>&1
set "LOGFILE=%DATADIR%\core-service.log"

if not exist "%INSTALLDIR%.venv\Scripts\pythonw.exe" (
    echo [GENESIS] Python-Laufzeitumgebung fehlt - Core-Service kann nicht gestartet werden.
    echo [GENESIS] Bitte Install-GenesisMediaManager.ps1 erneut ausfuehren, nachdem Python installiert wurde.
    pause
    exit /b 1
)

REM Bei jedem erneuten Doppelklick KEINEN zweiten Core-Service starten:
REM dieser wuerde am schon belegten Port 8420 scheitern und das Log des
REM funktionierenden ersten Prozesses mit einer Fehlermeldung ueberschreiben.
REM /health muss wirklich GENESIS mit status=ok melden (nicht irgendein 200).
powershell -NoProfile -Command "try { $s = Invoke-RestMethod -Uri 'http://127.0.0.1:8420/health' -TimeoutSec 1; if ($s.status -eq 'ok') { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 (
    echo [GENESIS] Core-Service laeuft bereits - vorhandenen Prozess verwenden.
    set "READY=1"
    goto :ready
)

REM pythonw.exe zeigt bewusst kein Konsolenfenster. Fehler gehen ins Log,
REM nicht ins Leere (siehe README-INSTALL.md).
echo [GENESIS] Core-Service wird gestartet, Log: %LOGFILE%
start "" /B "%INSTALLDIR%.venv\Scripts\pythonw.exe" "%INSTALLDIR%backend\run_api.py" > "%LOGFILE%" 2>&1

REM Statt einer starren, oft zu kurzen Wartezeit (frueher: feste 2
REM Sekunden) aktiv auf Erreichbarkeit warten, maximal 60 Sekunden. Der
REM allererste Start kann deutlich laenger als 2 Sekunden dauern - u.a.
REM weil Windows Defender jede frisch installierte .venv-Datei/DLL beim
REM ersten Zugriff einzeln prueft, bevor Python sqlalchemy/fastapi/
REM onnxruntime/... ueberhaupt fertig importieren kann.
set "READY=0"
for /L %%i in (1,1,60) do (
    powershell -NoProfile -Command "try { $s = Invoke-RestMethod -Uri 'http://127.0.0.1:8420/health' -TimeoutSec 1; if ($s.status -eq 'ok') { exit 0 } } catch {}; exit 1" >nul 2>&1
    if !errorlevel! equ 0 (
        set "READY=1"
        goto :ready
    )
    timeout /t 1 /nobreak >nul
)
:ready
if "!READY!"=="0" (
    echo [GENESIS] WARNUNG: Core-Service antwortet nach 60 Sekunden immer noch nicht.
    echo [GENESIS] Fehlerdetails ^(falls vorhanden^) stehen in: %LOGFILE%
    echo [GENESIS] Die Oberflaeche wird trotzdem gestartet - ohne Core-Service zeigt sie einen klaren Fehler statt erfundener Daten.
)

start "" "%INSTALLDIR%client\GenesisMediaManager.exe"
endlocal
