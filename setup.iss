; Forsaken Realms AI — Inno Setup Script
; Compile: open in Inno Setup 6, press Ctrl+F9
; Output: ForsakenRealmsAI_Setup.exe

#define MyAppName      "Forsaken Realms AI"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "Forsaken Realms"
#define MyAppExeName   "app.exe"
#define MyAppDir       "D:\AI Assistant"
#define MyScriptsDir   "D:\AI Assistant\scripts"
#define MyDistDir      "D:\AI Assistant\scripts\dist"

[Setup]
AppId={{FR-AI-2026-UNIQUE-GUID}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName=D:\Astra My Partner
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableDirPage=no
OutputDir={#MyAppDir}
OutputBaseFilename=ForsakenRealmsAI_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
SetupIconFile={#MyScriptsDir}\icons\icon.ico
UninstallDisplayIcon={app}\scripts\icons\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startupicon"; Description: "Launch on Windows startup";  GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; Main executable
Source: "{#MyDistDir}\app.exe";               DestDir: "{app}\scripts";       Flags: ignoreversion

; Backend scripts
Source: "{#MyScriptsDir}\server.py";          DestDir: "{app}\scripts";       Flags: ignoreversion
Source: "{#MyScriptsDir}\watcher.py";         DestDir: "{app}\scripts";       Flags: ignoreversion
Source: "{#MyScriptsDir}\ingest.py";          DestDir: "{app}\scripts";       Flags: ignoreversion
Source: "{#MyScriptsDir}\query.py";           DestDir: "{app}\scripts";       Flags: ignoreversion
Source: "{#MyScriptsDir}\config.py";          DestDir: "{app}\scripts";       Flags: ignoreversion

; Icons
Source: "{#MyScriptsDir}\icons\icon.ico";     DestDir: "{app}\scripts\icons"; Flags: ignoreversion
Source: "{#MyScriptsDir}\icons\icon.png";     DestDir: "{app}\scripts\icons"; Flags: ignoreversion
Source: "{#MyScriptsDir}\icons\splash.png";   DestDir: "{app}\scripts\icons"; Flags: ignoreversion

; Extras
Source: "{#MyAppDir}\models\model_info.txt";  DestDir: "{app}\models";        Flags: ignoreversion
Source: "{#MyAppDir}\README.txt";             DestDir: "{app}";               Flags: ignoreversion isreadme

[Dirs]
Name: "{app}\data"
Name: "{app}\db\faiss_index"
Name: "{app}\Memories"
Name: "{app}\models"
Name: "{app}\scripts"
Name: "{app}\scripts\icons"

[Icons]
Name: "{group}\{#MyAppName}";           Filename: "{app}\scripts\app.exe"; IconFilename: "{app}\scripts\icons\icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\scripts\app.exe"; IconFilename: "{app}\scripts\icons\icon.ico"; Tasks: desktopicon
Name: "{autostartup}\{#MyAppName}";     Filename: "{app}\scripts\app.exe"; Tasks: startupicon

[Run]
Filename: "{app}\scripts\app.exe"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files;          Name: "{app}\scripts\config.json"
Type: filesandordirs; Name: "{app}\db"
Type: filesandordirs; Name: "{app}\Memories"

[Code]
procedure InitializeWizard();
var
  PreReqPage: TWizardPage;
  Lbl: TNewStaticText;
begin
  PreReqPage := CreateCustomPage(
    wpWelcome,
    'Before You Begin - Required Software',
    'Please install these before continuing.'
  );

  Lbl := TNewStaticText.Create(PreReqPage);
  Lbl.Parent   := PreReqPage.Surface;
  Lbl.Left     := 0;
  Lbl.Top      := 0;
  Lbl.Width    := PreReqPage.SurfaceWidth;
  Lbl.AutoSize := True;
  Lbl.WordWrap := True;
  Lbl.Caption  :=
    '1. OLLAMA - download from https://ollama.com' + Chr(13) + Chr(10) +
    '   Then run:  ollama pull qwen3:8b' + Chr(13) + Chr(10) +
    Chr(13) + Chr(10) +
    '2. PYTHON 3.10+ - download from https://www.python.org' + Chr(13) + Chr(10) +
    '   Tick "Add Python to PATH" during install, then run:' + Chr(13) + Chr(10) +
    '   py -m pip install flask flask-cors watchdog sentence-transformers faiss-cpu' + Chr(13) + Chr(10) +
    Chr(13) + Chr(10) +
    'Once both are done, click Next to continue.';
end;
