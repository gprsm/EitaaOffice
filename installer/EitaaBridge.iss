#define MyAppName "Eitaa Bridge"
#define MyAppVersion "0.8.0-rc1"
#define MyAppPublisher "Eitaa Bridge Project"
#define MyAppExeName "EitaaBridge.exe"
#define StageDir "..\release\windows\EitaaBridge-0.8.0-rc1"

[Setup]
AppId={{D670CA98-019E-4C36-8BD7-8E7F94522060}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\EitaaBridge
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=..\release\installer
OutputBaseFilename=EitaaBridge-0.8.0-rc1-Setup-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion=0.8.0.1
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a Desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Backup Eitaa Bridge"; Filename: "{app}\bridge-runtime\backup_now.bat"; WorkingDir: "{app}\bridge-runtime"
Name: "{group}\Safe Diagnostics"; Filename: "{app}\bridge-runtime\create_diagnostics.bat"; WorkingDir: "{app}\bridge-runtime"

[Run]
Filename: "{cmd}"; Parameters: "/C ""{app}\bridge-runtime\setup_venv.bat"" /silent"; WorkingDir: "{app}\bridge-runtime"; StatusMsg: "Preparing the local backend..."; Flags: runhidden waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\bridge-runtime\.venv"
Type: filesandordirs; Name: "{app}\bridge-runtime\runtime"

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('py', '-3.13 -c "import sys; assert sys.version_info[:2] == (3,13)"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
  if not Result then
    MsgBox('Python 3.13 x64 is required. Install it before running this installer.', mbError, MB_OK);
end;
