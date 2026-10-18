; Build through scripts/build-windows.ps1 so assets and AppVersion are current.
#ifndef AppVersion
  #error AppVersion must be supplied by the Windows build script.
#endif

[Setup]
AppId={{873B0856-64BD-4907-B42F-E0BC84D1F250}
AppName=Training Planner
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\TrainingPlanner
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UsePreviousTasks=no
OutputDir=..\dist
OutputBaseFilename=TrainingPlanner-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\TrainingPlanner.exe
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "startmenuicon"; Description: "Create a Start menu shortcut"; Flags: unchecked
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
; Only packaged application files: never include a developer or user database.
Source: "..\dist\TrainingPlanner\TrainingPlanner.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\TrainingPlanner\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Training Planner"; Filename: "{app}\TrainingPlanner.exe"; Tasks: startmenuicon
Name: "{userdesktop}\Training Planner"; Filename: "{app}\TrainingPlanner.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TrainingPlanner.exe"; Description: "Launch Training Planner"; Flags: postinstall nowait skipifsilent unchecked

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if not Exec(ExpandConstant('{app}\TrainingPlanner.exe'), '--init-db',
      ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      RaiseException('Could not initialize the Training Planner database.');
    if ResultCode <> 0 then
      RaiseException('Database initialization failed. Choose a writable destination folder.');
  end;
end;

{ No recursive uninstall deletion: application-created data is preserved. }
