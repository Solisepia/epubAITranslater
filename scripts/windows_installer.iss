#define MyAppName "epub2zh-faithful-client"
#ifndef MyAppVersion
  #define MyAppVersion "0.1.1"
#endif
#ifndef MySourceDir
  #define MySourceDir "..\dist\epub2zh-faithful-client"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\dist\installer"
#endif
#ifndef MyOutputBaseName
  #define MyOutputBaseName "epub2zh-faithful-client-setup"
#endif

[Setup]
AppId={{8B3E8C40-B9B0-42E7-93A3-F1F5B64686ED}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=epub2zh-faithful
AppPublisherURL=https://github.com/Solisepia/epubAITranslater
AppSupportURL=https://github.com/Solisepia/epubAITranslater/issues
AppUpdatesURL=https://github.com/Solisepia/epubAITranslater/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyOutputBaseName}-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\epub2zh-faithful-client.exe
UninstallDisplayName={#MyAppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs; Excludes: "cache.sqlite,cache.sqlite-journal"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\epub2zh-faithful-client.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\epub2zh-faithful-client.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\epub2zh-faithful-client.exe"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\epub2zh-faithful-client.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssDone then
  begin
    MsgBox('Installation completed successfully!' + #13#10 + #13#10 + 'You can now start epub2zh-faithful-client from the Start Menu or Desktop.', mbInformation, MB_OK);
  end;
end;
