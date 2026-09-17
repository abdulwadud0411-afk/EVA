; =====================================================================
; EVA — Inno Setup Installer Script (Phase 22 Batch 4)
; =====================================================================
; Requires: Inno Setup 6.x  (https://jrsoftware.org/isdl.php)
; Usage:    scripts\build_installer.bat
; =====================================================================

#define MyAppName "EVA"
#define MyAppVersion "0.22.0"
#define MyAppPublisher "EVA Labs"
#define MyAppURL "https://example.com/eva"
#define MyAppExeName "EVA.exe"

[Setup]
AppId={{9F3A5B2C-4D6E-4B8A-9C1F-E7A2B3C4D5E6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=EVA_Setup_{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startmenu"; Description: "Create a Start Menu entry"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\EVA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
  OllamaFound: Boolean;
begin
  Result := True;
  OllamaFound := Exec(
    'cmd.exe',
    '/c where ollama >nul 2>nul',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode
  ) and (ResultCode = 0);

  if not OllamaFound then
  begin
    if MsgBox(
      'EVA works best with Ollama (free, local AI).' + #13#10 +
      'Ollama is NOT installed on this PC.' + #13#10#13#10 +
      'Download Ollama from:  https://ollama.com/download' + #13#10 +
      'After installing Ollama, run this command in PowerShell:' + #13#10#13#10 +
      '     ollama pull qwen2.5:3b' + #13#10#13#10 +
      'Continue installing EVA anyway?',
      mbConfirmation, MB_YESNO
    ) = IDNO then
      Result := False;
  end;
end;