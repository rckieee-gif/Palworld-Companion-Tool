#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "Palworld Companion Tools"
#define AppPublisher "Palworld Companion Tools Contributors"
#define AppUrl "https://github.com/rckieee-gif/Palworld-Companion-Tool"
#define AppExeName "PalworldCompanionTools-V" + AppVersion + "-win.exe"

[Setup]
AppId={{8E6B22E9-3E46-4AB2-9A8D-2EDCFA6B1A39}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=PalworldCompanionTools-Setup-V{#AppVersion}-win-x64
SetupIconFile=..\..\resources\assets\icons\app\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
LicenseFile=..\..\license
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Read-only Palworld companion application
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[InstallDelete]
Type: files; Name: "{app}\PalworldCompanionTools-V*-win.exe"

[Files]
Source: "..\..\dist\main.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
