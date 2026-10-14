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
Source: "{#ProjectDir}\deploy\ensure-tailscale.ps1"; Flags: dontcopy

[Icons]
Name: "{group}\Cloud Game"; Filename: "{app}\Moonlight.exe"
Name: "{autodesktop}\Cloud Game"; Filename: "{app}\Moonlight.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Criar atalho na área de trabalho"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  ResultCode := -1;
  ExtractTemporaryFile('ensure-tailscale.ps1');
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{tmp}\ensure-tailscale.ps1') + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := 'Não foi possível preparar a rede privada Tailscale.';
  if ResultCode <> 0 then
    Result := 'A instalação do Tailscale não foi concluída. Verifique a internet e autorize a instalação administrativa. Nenhuma chave compartilhada é necessária.';
end;
