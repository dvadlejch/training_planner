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
SetupIconFile=..\assets\icons\summit-calendar.ico
WizardImageFile=..\assets\icons\installer-panel.png
WizardSmallImageFile=..\assets\icons\summit-calendar.png
DisableWelcomePage=no
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
Name: "{userprograms}\Training Planner"; Filename: "{app}\TrainingPlanner.exe"; IconFilename: "{app}\TrainingPlanner.exe"; IconIndex: 0; Tasks: startmenuicon
Name: "{userdesktop}\Training Planner"; Filename: "{app}\TrainingPlanner.exe"; IconFilename: "{app}\TrainingPlanner.exe"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\TrainingPlanner.exe"; Description: "Launch Training Planner"; Flags: postinstall nowait skipifsilent unchecked

[Code]
const
  SHCNE_ASSOCCHANGED = $08000000;
  SHCNF_IDLIST = $0000;
  SHCNF_FLUSHNOWAIT = $2000;

procedure SHChangeNotify(EventId: Integer; Flags: Cardinal; Item1, Item2: LongWord);
external 'SHChangeNotify@shell32.dll stdcall';

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
    { Replacing an EXE at the same path can leave Explorer's old icon cached.
      Ask the Shell to invalidate its icon cache without restarting Explorer. }
    SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST or SHCNF_FLUSHNOWAIT, 0, 0);
  end;
end;

{ No recursive uninstall deletion: application-created data is preserved. }
