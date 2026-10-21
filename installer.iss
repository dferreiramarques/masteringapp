; MasteringApp — instalador Windows (Inno Setup 6)
; build: ISCC.exe installer.iss  (a partir da pasta mastering-app)

#define AppName "MasteringApp"
#define AppVersion "1.0.0.0"
#define AppPublisher "Mastering Suite"

[Setup]
AppId={{B7E3F2A9-5C4D-4E8A-9F61-2A8C7D3E5B10}}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\MasteringApp
DisableDirPage=no
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=MasteringApp-Setup-1.0.0
SetupIconFile=static\app_icon.ico
UninstallDisplayIcon={app}\MasteringApp.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription=MasteringApp - masterizacao de audio local
VersionInfoCompany=Mastering Suite
VersionInfoCopyright=(c) 2026 Mastering Suite

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho no &Desktop"; \
  GroupDescription: "Atalhos:"; Flags: checkedonce

[Files]
Source: "dist\MasteringApp\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\MasteringApp.exe"; \
  IconFilename: "{app}\MasteringApp.exe"; Tasks: desktopicon
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\MasteringApp.exe"; \
  IconFilename: "{app}\MasteringApp.exe"
Name: "{autoprograms}\{#AppName}\Desinstalar {#AppName}"; \
  Filename: "{uninstallexe}"

[Run]
Filename: "{app}\MasteringApp.exe"; Description: "Executar o &{#AppName}"; \
  Flags: nowait postinstall skipifsilent
