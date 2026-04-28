; ====================================================================
; Inno Setup script for GameBoost
;
; Wraps the PyInstaller --onefile output in a recognized Windows
; installer. Microsoft Partner Center, Chocolatey, and Scoop accept
; this format; raw PyInstaller .exe is rejected as "not a Win32 package".
;
; Built in CI by .github/workflows/release.yml after PyInstaller. Inno
; Setup 6 is pre-installed on GitHub's `windows-latest` runner; locally
; install from https://jrsoftware.org/isdl.php.
;
; The GUID below is fixed forever for this product so upgrade
; detection works across versions. Never regenerate.
; ====================================================================

#define MyAppName "GameBoost"
#define MyAppPublisher "GameBoost"
#define MyAppURL "https://nikolasgsg.github.io/pcBoostMax/"
#define MyAppExeName "GameBoost.exe"

; Version is overridden at build time via /DAppVersion=...
#ifndef AppVersion
  #define AppVersion "2.1.1"
#endif

; PyInstaller artefact path is overridden at build time via /DSourceExe=...
#ifndef SourceExe
  #define SourceExe "..\dist\GameBoost-2.1.1-x64.exe"
#endif

[Setup]
; Stable AppId — never change this for the lifetime of the product.
AppId={{8E3F4A2C-7B1D-4A2E-9C5B-1F2A3B4C5D6E}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} {#AppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL=https://github.com/NikolasGSG/pcBoostMax/issues
AppUpdatesURL=https://github.com/NikolasGSG/pcBoostMax/releases
AppCopyright=Copyright (c) 2026 GameBoost. Open-source under the MIT license.
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Optimizer setup
VersionInfoCopyright=Copyright (c) 2026 GameBoost
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=GameBoost-{#AppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName} {#AppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
MinVersion=10.0.18363
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
