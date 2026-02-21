#define MyAppName "epub2zh-faithful-client"
#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#ifndef MySourceDir
  #define MySourceDir "..\\dist\\epub2zh-faithful-client"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\\dist\\installer"
#endif
#ifndef MyOutputBaseName
  #define MyOutputBaseName "epub2zh-faithful-client-setup"
#endif

[Setup]
AppId={{8B3E8C40-B9B0-42E7-93A3-F1F5B64686ED}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=epub2zh-faithful
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyOutputBaseName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\epub2zh-faithful-client.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\epub2zh-faithful-client.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\epub2zh-faithful-client.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\epub2zh-faithful-client.exe"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
