@echo off
echo ===================================================
echo     DONG GOI TIKTOK UPLOADER PRO (BAN GIAO KHACH)
echo ===================================================
echo.

echo [1] Kiem tra PyInstaller...
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Dang cai dat PyInstaller...
    pip install pyinstaller
)

echo.
echo [2] Tu dong bao luu FFmpeg/FFprobe neu da co...
if exist "dist\TikTok_Uploader_Client\ffmpeg.exe" (
    if not exist "temp_bin" mkdir "temp_bin"
    copy /y "dist\TikTok_Uploader_Client\ffmpeg.exe" "temp_bin\" >nul
    copy /y "dist\TikTok_Uploader_Client\ffprobe.exe" "temp_bin\" >nul
)

echo.
echo [3] Dang dong goi code moi bang PyInstaller (Vui long doi 1-2 phut)...
echo.

if exist "build" rmdir /s /q "build"
if exist "dist\TikTok_Uploader_Client" rmdir /s /q "dist\TikTok_Uploader_Client"

python -m PyInstaller --noconfirm TikTok_Uploader_Client.spec
if %errorlevel% neq 0 (
    echo.
    echo [LOI] PyInstaller xay ra loi bien dich!
    pause
    exit /b %errorlevel%
)

echo.
echo [4] Dua FFmpeg va huong dan su dung vao thu muc phan mem...
if exist "temp_bin\ffmpeg.exe" (
    copy /y "temp_bin\ffmpeg.exe" "dist\TikTok_Uploader_Client\" >nul
    copy /y "temp_bin\ffprobe.exe" "dist\TikTok_Uploader_Client\" >nul
    rmdir /s /q "temp_bin"
) else (
    if exist "D:\ffmpeg-8.1.1-essentials_build\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe" (
        copy /y "D:\ffmpeg-8.1.1-essentials_build\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe" "dist\TikTok_Uploader_Client\" >nul
        copy /y "D:\ffmpeg-8.1.1-essentials_build\ffmpeg-8.1.1-essentials_build\bin\ffprobe.exe" "dist\TikTok_Uploader_Client\" >nul
    )
)

if exist "docs\Huong_Dan_Cai_Dat.txt" (
    copy /y "docs\Huong_Dan_Cai_Dat.txt" "dist\TikTok_Uploader_Client\" >nul
)

echo.
echo [5] Kiem tra Inno Setup de tu dong tao file Setup.exe...
set "ISCC_PATH="
if exist "D:\Inno Setup 7\ISCC.exe" set "ISCC_PATH=D:\Inno Setup 7\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"

if defined ISCC_PATH (
    echo Tim thay Inno Setup tai: %ISCC_PATH%
    echo Dang dong goi file cai dat tu dong...
    "%ISCC_PATH%" /Qp "setup_client.iss"
    if %errorlevel% equ 0 (
        echo [OK] Da tao thanh cong file cai dat Setup tai: dist\setup\DouyinBot_Setup.exe
    ) else (
        echo [!] Khong the build setup tu dong. Ban co the mo file setup_client.iss bang Inno Setup.
    )
) else (
    echo Ban co the mo file setup_client.iss bang Inno Setup va bam Compile de tao file Setup.
)

echo.
echo ===================================================
echo   HOAN THANH TOAN BO QUA TRINH BUILD!
echo.
echo   1. File Cai dat Setup (Khuyen dung de gui khach):
echo      dist\setup\DouyinBot_Setup.exe
echo.
echo   2. Thu muc giai nen (Dang portable):
echo      dist\TikTok_Uploader_Client\
echo ===================================================
pause
