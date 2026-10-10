; GENESIS Media Manager - Inno Setup 6 (Windows x64, Installation pro Benutzer).
; Vor dem Kompilieren im Repository: pwsh -File deploy\Build-Package.ps1 -SkipZip
; Danach: ISCC.exe deploy\inno\GenesisMediaManager.iss
; Die .iss ist das REZEPT; ohne build\package\client, backend usw. ist sie kein Installer.
;
; Bitte nicht parallel mit dem bisherigen MSI-/PowerShell-Installer installieren:
; gleicher Zielordner, aber verschiedene Deinstallationsmechanismen.
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
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
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
Source: "{#Payload}\installer\Setup-PythonRuntime.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
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

function InitializeSetup(): Boolean;
var
  InstallPath: string;
begin
  Result := True;
  InstallPath := ExpandConstant('{localappdata}\Programs\GenesisMediaManager');
  if FileExists(InstallPath + '\client\GenesisMediaManager.exe') and
     not FileExists(InstallPath + '\unins000.exe') then
  begin
    MsgBox('Hier ist bereits GENESIS Media Manager mit einem anderen Installer ' +
      '(MSI oder PowerShell) installiert. Bitte diese Version zuerst ueber ' +
      'Windows-Einstellungen > Apps deinstallieren. Deine Mediathek-Daten bleiben erhalten.',
      mbError, MB_OK);
    Result := False;
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

  { Synchronously run the SAME Python runtime setup as the ZIP/MSI.
    The installer cannot claim success or offer to launch until pip finishes. }
  ExitCode := -1;
  Params := '-NoProfile -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\installer\Setup-PythonRuntime.ps1') +
    '" -InstallDir "' + ExpandConstant('{app}') + '"';
  WizardForm.StatusLabel.Caption := 'Python-Umgebung fuer den Core-Service wird eingerichtet ...';
  WizardForm.Repaint;
  Succeeded := Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Params, ExpandConstant('{app}'), SW_SHOW, ewWaitUntilTerminated, ExitCode);
  PythonReady := Succeeded and (ExitCode = 0) and
    FileExists(ExpandConstant('{app}\.venv\Scripts\python.exe'));
  if not PythonReady then
  begin
    MsgBox('Die Programmdateien wurden kopiert, aber die Python-Einrichtung ' +
      'ist fehlgeschlagen (Exit-Code ' + IntToStr(ExitCode) + '). ' +
      'Bitte Python 3.11 oder neuer installieren (mit "Add python.exe to PATH"), ' +
      'Internetverbindung pruefen und das Setup danach erneut starten. ' +
      'Die App wird jetzt nicht gestartet.', mbError, MB_OK);
  end;
end;

function RuntimeReady(): Boolean;
begin
  Result := PythonReady;
end;
