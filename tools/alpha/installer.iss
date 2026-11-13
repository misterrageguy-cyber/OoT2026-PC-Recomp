; Ocarina Reborn Alpha installer (Inno Setup 6). build_alpha.ps1 passes /DStage=<stage folder> /DOut=<dist folder>.
; Per-user install, no administrator rights. Player data in %LOCALAPPDATA%\Ocarina Reborn is never removed.

#define AppName "Ocarina Reborn"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#ifndef AppFileVersion
  #define AppFileVersion "0.0.0.0"
#endif

[Setup]
AppId={{6E0B5C1A-0C9B-4C3F-9E52-0CA81A2B7F11}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion={#AppFileVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Ocarina Reborn
DefaultDirName={localappdata}\Programs\Ocarina Reborn
DefaultGroupName=Ocarina Reborn
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Out}
OutputBaseFilename=Ocarina-Reborn-Alpha-Setup
SetupIconFile={#Stage}\OcarinaReborn.ico
UninstallDisplayIcon={app}\OcarinaReborn.exe
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
; the compressor in its own 64-bit process: ISCC itself is 32-bit and ran out of memory on the ~900 MB of tools
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
WizardStyle=modern
DiskSpanning=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; an update replaces the program files only; player data lives elsewhere
Type: filesandordirs; Name: "{app}\src"
Type: filesandordirs; Name: "{app}\launcher"

[Icons]
Name: "{group}\Ocarina Reborn"; Filename: "{app}\OcarinaReborn.exe"; IconFilename: "{app}\OcarinaReborn.ico"
Name: "{group}\Uninstall Ocarina Reborn"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Ocarina Reborn"; Filename: "{app}\OcarinaReborn.exe"; IconFilename: "{app}\OcarinaReborn.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\OcarinaReborn.exe"; Description: "Launch Ocarina Reborn"; Flags: nowait postinstall skipifsilent
