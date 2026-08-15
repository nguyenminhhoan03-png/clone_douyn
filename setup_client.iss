[Setup]
AppName=DouyinBot SaaS
AppVersion=1.0
DefaultDirName={pf}\DouyinBot
DefaultGroupName=DouyinBot SaaS
OutputDir=dist\setup
OutputBaseFilename=DouyinBot_Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=compiler:SetupClassicIcon.ico

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\TikTok_Uploader_Client\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Nếu có thêm file ffmpeg.exe, ffprobe.exe ở ngoài thì có thể thêm vào đây:
; Source: "ffmpeg.exe"; DestDir: "{app}"; Flags: ignoreversion
; Source: "ffprobe.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\DouyinBot SaaS"; Filename: "{app}\TikTok_Uploader_Client.exe"
Name: "{commondesktop}\DouyinBot SaaS"; Filename: "{app}\TikTok_Uploader_Client.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TikTok_Uploader_Client.exe"; Description: "{cm:LaunchProgram,DouyinBot SaaS}"; Flags: nowait postinstall skipifsilent
