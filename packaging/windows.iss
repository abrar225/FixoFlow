#ifndef AppVersion
  #error AppVersion must come from fixoflow.version
#endif
[Setup]
AppId={{CC0937BA-D0BC-4B0A-96CE-84646D8E5A3C}
AppName=Fixo Flow
AppVersion={#AppVersion}
AppPublisher=Fixo Flow
AppPublisherURL=https://github.com/abrar225/FixoFlow
DefaultDirName={localappdata}\Programs\FixoFlow
DefaultGroupName=Fixo Flow
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19045
OutputDir=..\dist
OutputBaseFilename=Fixoflow-{#AppVersion}-windows-x64-setup
Compression=lzma2/max
SolidCompression=yes
SetupIconFile=..\fixoflow\ui\assets\flow-fold.ico
UninstallDisplayIcon={app}\Fixoflow.exe
CloseApplications=yes
RestartApplications=no
WizardStyle=modern
[Files]
Source: "..\dist\Fixoflow\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Fixo Flow"; Filename: "{app}\Fixoflow.exe"
Name: "{autodesktop}\Fixo Flow"; Filename: "{app}\Fixoflow.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\Fixoflow.exe"; Description: "Open Fixo Flow"; Flags: nowait postinstall skipifsilent
