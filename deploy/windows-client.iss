; One per-user installer. Moonlight's engine is part of the installed application.
#ifndef ClientDir
  #error ClientDir is required
#endif
#ifndef ProjectDir
  #error ProjectDir is required
#endif
[Setup]
AppId={{A63BEEB1-4B0C-4F6F-B6DF-B546FF9AC531}
AppName=Cloud Game
AppVersion=0.1.0
AppPublisher=CloudGame
AppPublisherURL=https://github.com/FaelSemW/CloudGame
DefaultDirName={localappdata}\Programs\CloudGame
DefaultGroupName=Cloud Game
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=CloudGame-Setup
OutputDir={#ProjectDir}\dist
Compression=lzma2
SolidCompression=yes
LicenseFile={#ProjectDir}\LICENSE
UninstallDisplayIcon={app}\Moonlight.exe

[Files]
Source: "{#ClientDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ProjectDir}\LICENSE"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "{#ProjectDir}\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Cloud Game"; Filename: "{app}\Moonlight.exe"
Name: "{autodesktop}\Cloud Game"; Filename: "{app}\Moonlight.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Criar atalho na área de trabalho"; Flags: unchecked
