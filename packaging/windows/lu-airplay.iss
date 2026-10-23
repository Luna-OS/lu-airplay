; Installer für Lu AirPlay Receiver (Inno Setup 6)
;   iscc /DAppVersion=1.0.0 /DSourceDir=..\..\dist\LuAirPlay /DOutputDir=..\..\dist packaging\windows\lu-airplay.iss

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\LuAirPlay"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{6E2B7F1C-2D5A-4B8E-9C3F-4C55AF1A0B7E}
AppName=Lu AirPlay Receiver
AppVersion={#AppVersion}
AppPublisher=Luna OS
AppPublisherURL=https://github.com/Luna-OS/lu-airplay
DefaultDirName={autopf}\Lu AirPlay
DefaultGroupName=Lu AirPlay
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\Lu AirPlay.exe
SetupIconFile=..\..\launcher\luairplay\assets\icon.ico
LicenseFile={#SourceDir}\LICENSE.txt
OutputDir={#OutputDir}
OutputBaseFilename=LuAirPlay-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Beim Anmelden automatisch starten"; GroupDescription: "Optionen:"; Flags: unchecked
Name: "publicnet"; Description: "Auch in Netzwerken erlauben, die Windows als „Öffentlich“ einstuft (oft bei Heim-WLANs nötig)"; GroupDescription: "Firewall:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Lu AirPlay Receiver"; Filename: "{app}\Lu AirPlay.exe"
Name: "{autodesktop}\Lu AirPlay Receiver"; Filename: "{app}\Lu AirPlay.exe"; Tasks: desktopicon
Name: "{userstartup}\Lu AirPlay Receiver"; Filename: "{app}\Lu AirPlay.exe"; Tasks: autostart

[Run]
; Firewall freigeben, damit iPhone/iPad den Empfänger finden und verbinden können
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Lu AirPlay"""; Flags: runhidden; StatusMsg: "Firewall wird eingerichtet ..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Lu AirPlay (public)"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""Lu AirPlay"" dir=in action=allow program=""{app}\engine\bin\uxplay.exe"" enable=yes profile=private,domain"; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""Lu AirPlay (public)"" dir=in action=allow program=""{app}\engine\bin\uxplay.exe"" enable=yes profile=public"; Flags: runhidden; Tasks: publicnet
Filename: "{app}\Lu AirPlay.exe"; Description: "{cm:LaunchProgram,Lu AirPlay Receiver}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Lu AirPlay"""; Flags: runhidden; RunOnceId: "RemoveFirewallRule"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Lu AirPlay (public)"""; Flags: runhidden; RunOnceId: "RemoveFirewallRulePublic"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Lu AirPlay (App)"""; Flags: runhidden; RunOnceId: "RemoveFirewallRuleApp"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\engine"
