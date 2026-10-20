; GENESIS Media Manager - Inno Setup 6 (Windows x64, Installation pro Benutzer).
; Vor dem Kompilieren im Repository: pwsh -File deploy\Build-Package.ps1 -SkipZip
; Danach: ISCC.exe deploy\inno\GenesisMediaManager.iss
; Die .iss ist das REZEPT; ohne build\package\client, backend usw. ist sie kein Installer.
;
; Bitte nicht parallel mit MSI-/PowerShell-Installer installieren:
; unabhaengig vom frei waehllbaren Pfad verschiedene Deinstallierer.
#define AppName "GENESIS Media Manager"
#define AppVersion "0.2.0"
#define Payload "..\..\build\package"

[Setup]
AppId={{D9F1FF8F-8DD4-4C55-A656-6B3B01B79466}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=GENESIS Media Manager Projekt
DefaultDirName={localappdata}\Programs\GenesisMediaManager
DefaultGroupName={#AppName}
DisableDirPage=no
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
; Pro-Benutzer unter HKCU\...\Uninstall registrieren, damit Windows
; 'Installierte Apps' und der Deinstallierer einen eigenen Eintrag haben.
Uninstallable=yes
CreateUninstallRegKey=yes
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\client\GenesisMediaManager.exe
OutputDir=..\..\build
OutputBaseFilename=GenesisMediaManager-Inno-Setup

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknuepfung erstellen"; GroupDescription: "Zusaetzliche Aufgaben:"; Flags: unchecked

[Files]
; Das Payload wird ausschliesslich von deploy/Build-Package.ps1 gebaut.
; Kein Quellcode-ZIP als Ersatz fuer den veroeffentlichten .NET-Client.
Source: "{#Payload}\client\*"; DestDir: "{app}\client"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Payload}\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Payload}\i18n\*"; DestDir: "{app}\i18n"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Payload}\runtime\*"; DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Payload}\installer\Test-OfflineRuntime.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "{#Payload}\installer\Stop-GenesisProcesses.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "{#Payload}\installer\Start-GenesisMediaManager.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\Start-GenesisMediaManager.bat"; WorkingDir: "{app}"; IconFilename: "{app}\client\GenesisMediaManager.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Start-GenesisMediaManager.bat"; WorkingDir: "{app}"; IconFilename: "{app}\client\GenesisMediaManager.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Start-GenesisMediaManager.bat"; Description: "{#AppName} jetzt starten"; Flags: postinstall skipifsilent nowait; Check: RuntimeReady

[UninstallDelete]
; Von pip erzeugte Dateien sind nicht Teil der [Files]-Liste. Niemals
; Nutzerdaten/Einstellungen unter %APPDATA%\GenesisMediaManager loeschen!
Type: filesandordirs; Name: "{app}\.venv"

[Code]
var
  PythonReady: Boolean;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  TargetPath, DefaultPath, ExistingInnoPath: String;
  InnoKey, ScriptKey: String;
begin
  Result := '';
  TargetPath := ExpandConstant('{app}');
  DefaultPath := ExpandConstant('{localappdata}\Programs\GenesisMediaManager');
  InnoKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{D9F1FF8F-8DD4-4C55-A656-6B3B01B79466}_is1';
  ScriptKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\GenesisMediaManager';

  { Erst NACH der Verzeichnisauswahl pruefen: InitializeSetup sieht nur
    den DefaultDirName und wuerde fremde Dateien in einem frei gewaehlten
    Ziel uebersehen. Auch /SILENT /DIR=... durchlaeuft diese Pruefung. }
  if (FileExists(TargetPath + '\client\GenesisMediaManager.exe') and
      not FileExists(TargetPath + '\unins000.exe')) or
     FileExists(TargetPath + '\MsiOwnership.txt') then
  begin
    Result := 'Im gewaehlten Ordner liegen GENESIS-Dateien ohne Inno-' +
      'Deinstaller oder ein MSI-Marker. Das koennen auch Reste sein. ' +
      'Bitte Ursache pruefen; keine Dateien blind loeschen.';
    Exit;
  end;
  { MSI und start.bat verwenden den Standardordner. Das PowerShell-Skript
    kann auch anderswo installieren; dessen Registry-Eintrag sperrt dann
    ebenfalls jede parallele Inno-Installation. }
  if (FileExists(DefaultPath + '\client\GenesisMediaManager.exe') and
      not FileExists(DefaultPath + '\unins000.exe')) or
     FileExists(DefaultPath + '\MsiOwnership.txt') or
     RegKeyExists(HKCU, ScriptKey) then
  begin
    Result := 'Im Standardordner liegen GENESIS-Dateien ohne Inno-' +
      'Deinstaller, ein MSI-Marker oder ein ZIP-Deinstallationsschluessel. ' +
      'Das beweist keine aktive Installation. Bitte Ursache pruefen; ' +
      'keine Dateien blind loeschen.';
    Exit;
  end;
  { Eine bestehende Inno-Installation nur an IHREM bisherigen Pfad
    aktualisieren. Ein Umzug per Update liesse sonst Dateien zurueck. }
  if RegQueryStringValue(HKCU, InnoKey, 'InstallLocation', ExistingInnoPath) and
     (CompareText(AddBackslash(TargetPath), AddBackslash(ExistingInnoPath)) <> 0) then
  begin
    Result := 'Eine Inno-Installation liegt bereits unter ' + ExistingInnoPath +
      '. Bitte dort aktualisieren oder sie vor einem Umzug deinstallieren.';
    Exit;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ExitCode: Integer;
  Params: string;
  Succeeded: Boolean;
begin
  if CurStep <> ssPostInstall then
    Exit;

  { Validate the INCLUDED Python and media tools, without pip/network. }
  ExitCode := -1;
  Params := '-NoProfile -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\installer\Test-OfflineRuntime.ps1') +
    '" -InstallDir "' + ExpandConstant('{app}') + '"';
  WizardForm.StatusLabel.Caption := 'Mitgelieferte Offline-Runtime wird geprueft ...';
  WizardForm.Repaint;
  Succeeded := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Params, ExpandConstant('{app}'), SW_SHOW, ewWaitUntilTerminated, ExitCode);
  PythonReady := Succeeded and (ExitCode = 0) and
    FileExists(ExpandConstant('{app}\runtime\python\python.exe'));
  if not PythonReady then
  begin
    Log('Offline-Runtime fehlgeschlagen (Exit-Code ' + IntToStr(ExitCode) + ')');
    { Ein modales MsgBox in einem stillen CI-Lauf wuerde unbegrenzt warten. }
    if not WizardSilent then
      MsgBox('Die Programmdateien wurden kopiert, aber die enthaltene ' +
        'Offline-Runtime ist unvollstaendig oder konnte nicht gestartet werden ' +
        '(Exit-Code ' + IntToStr(ExitCode) + '). Bitte die Setup-EXE ' +
        'erneut herunterladen. Die App wird jetzt nicht gestartet.', mbError, MB_OK);
  end;
end;

function RuntimeReady(): Boolean;
begin
  Result := PythonReady;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ExitCode: Integer;
  Params: string;
begin
  if CurUninstallStep <> usUninstall then
    Exit;

  { Vor dem Entfernen von .venv die Prozesse DIESER Installation beenden.
    CloseApplications erkennt nicht zwingend das dynamisch per pip erstellte
    pythonw.exe; sonst bleiben gesperrte DLLs nach der Deinstallation liegen. }
  ExitCode := -1;
  Params := '-NoProfile -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\installer\Stop-GenesisProcesses.ps1') +
    '" -InstallDir "' + ExpandConstant('{app}') + '"';
  if (not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      Params, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ExitCode)) or
      (ExitCode <> 0) then
  begin
    MsgBox('GENESIS-Prozesse konnten nicht beendet werden. Bitte die App ' +
      'schliessen und die Deinstallation erneut starten. Exit-Code ' +
      IntToStr(ExitCode), mbError, MB_OK);
    Abort;
  end;
end;
