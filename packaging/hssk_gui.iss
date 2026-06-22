; Inno Setup script for HSSK Tools (Windows)
; Per-user install — no UAC/admin prompt required.
; Build: ISCC /DMyAppVersion=1.3.0 packaging\hssk_gui.iss
;
; The AppId GUID is fixed forever — Inno uses it to detect and replace prior installs
; on upgrade. Never change it across releases.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName      "HSSK Tools"
#define MyAppPublisher "hososuckhoe.com.vn"
#define MyAppExeName   "hssk-gui.exe"

[Setup]
AppId={{B9F46FFD-C84B-48CE-B65B-C19E41A88FAD}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppVerName={#MyAppName} {#MyAppVersion}

; Per-user install — no UAC prompt.
; {autopf} resolves to %LocalAppData%\Programs when PrivilegesRequired=lowest.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

OutputDir=..\out
OutputBaseFilename=HSSK-Tools-Setup-{#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
; The entire PyInstaller onedir — hssk-gui.exe, _internal\, and ms-playwright\
Source: "..\dist\hssk-gui\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
  Flags: nowait postinstall skipifsilent
