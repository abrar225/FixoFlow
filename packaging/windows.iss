#ifndef AppVersion
  #error AppVersion must come from fixoflow.version
#endif
[Setup]
AppId={{CC0937BA-D0BC-4B0A-96CE-84646D8E5A3C}
AppName=Fixo Flow
AppVersion={#AppVersion}
AppPublisher=Fixo Flow
AppPublisherURL=https://fixoflow.tech
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
#ifdef PublicRelease
; Supply /Sfixoflow=<provider signing command with $f> to ISCC.
; Inno signs both setup and its embedded uninstaller; missing signer fails build.
SignTool=fixoflow
SignedUninstaller=yes
#endif
[Files]
Source: "..\dist\Fixoflow\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Fixo Flow"; Filename: "{app}\Fixoflow.exe"
Name: "{autodesktop}\Fixo Flow"; Filename: "{app}\Fixoflow.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\Fixoflow.exe"; Description: "Open Fixo Flow"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command: String;
begin
  if CurUninstallStep = usUninstall then
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'FixoFlow', Command) then
      if (Command = '"' + ExpandConstant('{app}\Fixoflow.exe') + '" --background') or
         (Command = ExpandConstant('{app}\Fixoflow.exe') + ' --background') then
        RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'FixoFlow');
end;
