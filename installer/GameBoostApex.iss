; ====================================================================
; Inno Setup script for GameBoostApex
;
; Wraps the PyInstaller --onefile output in a recognized Windows
; installer. Microsoft Partner Center, Chocolatey, and Scoop accept
; this format; raw PyInstaller .exe is rejected as "not a Win32 package".
;
; SILENT-BY-DEFAULT BEHAVIOUR
; ---------------------------
; Microsoft Store Policy 10.2.9 forbids any installer UI when launched
; without command-line arguments. The [Code] section below detects a
; no-args launch and immediately re-spawns Setup with /VERYSILENT, so
; the user never sees a wizard. Pass /UI on the command line to force
; the classic interactive wizard (developer / power-user use only).
;
; Built in CI by .github/workflows/release.yml after PyInstaller. Inno
; Setup 6 is pre-installed on GitHub's `windows-latest` runner; locally
; install from https://jrsoftware.org/isdl.php.
;
; The GUID below is fixed forever for this product so upgrade
; detection works across versions. Never regenerate.
; ====================================================================

#define MyAppName "GameBoostApex"
#define MyAppPublisher "GameBoostApex"
#define MyAppURL "https://nikolasgsg.github.io/pcBoostMax/"
#define MyAppExeName "GameBoostApex.exe"

; Version is overridden at build time via /DAppVersion=...
#ifndef AppVersion
  #define AppVersion "2.1.4"
#endif

; PyInstaller artefact path is overridden at build time via /DSourceExe=...
#ifndef SourceExe
  #define SourceExe "..\dist\GameBoostApex-2.1.4-x64.exe"
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
AppCopyright=Copyright (c) 2026 GameBoostApex. Open-source under the MIT license.
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Optimizer setup
VersionInfoCopyright=Copyright (c) 2026 GameBoostApex
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=GameBoostApex-{#AppVersion}-Setup
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
; Suppress every wizard page that's still visible in /SILENT mode so
; that even on the rare interactive launch the UI is minimal.
DisableWelcomePage=yes
DisableDirPage=yes
DisableReadyPage=yes
DisableFinishedPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
; postinstall + skipifsilent => never auto-launches under Microsoft Store install.
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
{
  Microsoft Store Policy 10.2.9: setup must complete with no UI when
  launched without arguments. We honour that by detecting whether any
  silent flag was supplied and, if not, immediately relaunching Setup
  with /VERYSILENT and aborting the current (visible) instance.

  Pass /UI on the command line to opt back into the classic wizard.
}
function CmdLineHasFlag(const Flag: string): Boolean;
var
  i: Integer;
begin
  Result := False;
  for i := 1 to ParamCount do
  begin
    if CompareText(ParamStr(i), Flag) = 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
  ForceUi: Boolean;
  AlreadySilent: Boolean;
begin
  ForceUi := CmdLineHasFlag('/UI');
  AlreadySilent := CmdLineHasFlag('/SILENT')
                or CmdLineHasFlag('/VERYSILENT');

  if (not ForceUi) and (not AlreadySilent) then
  begin
    { Re-launch ourselves silently and abort the visible instance. }
    if ShellExec('',
                 ExpandConstant('{srcexe}'),
                 '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOCANCEL',
                 '',
                 SW_HIDE,
                 ewNoWait,
                 ResultCode) then
    begin
      Result := False;
      Exit;
    end;
  end;

  Result := True;
end;
