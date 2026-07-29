@echo off
echo ===================================================
echo     DONG GOI TIKTOK UPLOADER PRO (THUONG MAI)
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

:: Lệnh PyInstaller (Tùy chỉnh theo cấu trúc thư mục)
pyinstaller --noconfirm --onedir --windowed ^
    --name "TikTok_Uploader_Pro" ^
    --add-data ".env;." ^
    --add-data "qr.png;." ^
    --add-data "config;config/" ^
    --add-data "database;database/" ^
    --add-data "processor;processor/" ^
    --add-data "uploader;uploader/" ^
    --add-data "utils;utils/" ^
    --add-data "backend;backend/" ^
    --hidden-import "pymysql" ^
    --hidden-import "httpx" ^
    --hidden-import "loguru" ^
    --hidden-import "customtkinter" ^
    --hidden-import "edge_tts" ^
    --hidden-import "faster_whisper" ^
    --hidden-import "pysrt" ^
    --hidden-import "pydub" ^
    gui.py

echo.
echo ===================================================
echo   HOAN THANH! File chay nam trong thu muc: 
echo   dist\TikTok_Uploader_Pro\TikTok_Uploader_Pro.exe
echo ===================================================
pause
