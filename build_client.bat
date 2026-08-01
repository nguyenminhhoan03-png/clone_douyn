@echo off
echo ===================================================
echo     DONG GOI TIKTOK UPLOADER PRO (CHO KHACH HANG)
echo ===================================================
echo.

echo [1] Kiem tra va cai dat PyInstaller...
pip install pyinstaller

echo.
echo [2] Dang dong goi (Build) ung dung. Vui long doi...
echo.

:: Xóa thư mục build cũ nếu có
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

:: Lệnh PyInstaller đóng gói Client (KHÔNG bao gồm backend, file .env, database db cũ, hay cookie)
python -m PyInstaller --noconfirm --onedir --windowed ^
    --name "TikTok_Uploader_Client" ^
    --add-data "config/flows.json;config/" ^
    --hidden-import "pymysql" ^
    --hidden-import "httpx" ^
    --hidden-import "loguru" ^
    --hidden-import "customtkinter" ^
    --collect-all "edge_tts" ^
    --collect-all "faster_whisper" ^
    --collect-all "ctranslate2" ^
    --hidden-import "av" ^
    --collect-all "onnxruntime" ^
    --hidden-import "tokenizers" ^
    --hidden-import "pysrt" ^
    --hidden-import "pydub" ^
    --hidden-import "googleapiclient" ^
    --hidden-import "google_auth_oauthlib" ^
    --hidden-import "playwright" ^
    --hidden-import "yt_dlp" ^
    --hidden-import "cryptography" ^
    --hidden-import "keyring" ^
    --hidden-import "mutagen" ^
    --hidden-import "websockets" ^
    --hidden-import "certifi" ^
    --hidden-import "brotli" ^
    gui.py

echo.
echo ===================================================
echo   HOAN THANH! File chay nam trong thu muc: 
echo   dist\TikTok_Uploader_Client\TikTok_Uploader_Client.exe
echo ===================================================
echo   LUU Y QUAN TRONG TRUOC KHI BAN CHO KHACH HANG:
echo   Khach hang chi can bo ffmpeg.exe va ffprobe.exe vao
echo   cung thu muc voi TikTok_Uploader_Client.exe de chay.
echo ===================================================
pause
