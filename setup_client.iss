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

[Code]
// ═══════════════════════════════════════════════════════════════════════════════
// TỰ ĐỘNG GỬI TELEMETRY KHI NGƯỜI DÙNG GỠ CÀI ĐẶT (UNINSTALL)
// ═══════════════════════════════════════════════════════════════════════════════

function GetMachineGuid(): String;
var
  GuidVal: String;
begin
  GuidVal := '';
  // Thử đọc MachineGuid từ Registry 32-bit hoặc 64-bit
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\Cryptography', 'MachineGuid', GuidVal) then
  begin
    RegQueryStringValue(HKEY_LOCAL_MACHINE_64, 'SOFTWARE\Microsoft\Cryptography', 'MachineGuid', GuidVal);
  end;
  if GuidVal = '' then
    GuidVal := 'UNKNOWN_HWID';
  Result := GuidVal;
end;

procedure SendUninstallTelemetry();
var
  WinHttpReq: Variant;
  MachineGuid: String;
  Payload: String;
  ApiUrl: String;
begin
  try
    MachineGuid := GetMachineGuid();
    ApiUrl := 'http://douyn-api.muabanwebsite.io.vn/api/telemetry/uninstall';

    // Tạo chuỗi JSON gửi ngầm lên Server
    Payload := '{"action_type": "UNINSTALL", "hwid": "' + MachineGuid + '", "app_version": "1.0", "details": "Nguoi dung da go cai dat phan mem qua Windows Uninstaller"}';

    // Khởi tạo WinHttpRequest của Windows
    WinHttpReq := CreateOleObject('WinHttp.WinHttpRequest.5.1');
    WinHttpReq.Open('POST', ApiUrl, False); // Synchronous với giới hạn timeout ngắn
    WinHttpReq.SetRequestHeader('Content-Type', 'application/json');
    
    // Đặt timeout: 2s Resolve, 2s Connect, 3s Send, 3s Receive (không bao giờ treo máy user)
    WinHttpReq.SetTimeouts(2000, 2000, 3000, 3000);
    WinHttpReq.Send(Payload);
  except
    // Bỏ qua ngoại lệ nếu máy tính không có kết nối internet
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // usUninstall: Được gọi ngay khi người dùng xác nhận gỡ cài đặt (trước khi xóa files)
  if CurUninstallStep = usUninstall then
  begin
    SendUninstallTelemetry();
  end;
end;
