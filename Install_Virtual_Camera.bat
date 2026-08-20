@echo off
title Face Swap Virtual Camera Installer
echo ========================================================
echo Installing Lightweight Virtual Camera Driver for Face Swap
echo ========================================================
echo.

:: Check for admin privileges and elevate if needed
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo Requesting Administrator Permission...
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\elevate_vcam.vbs"
    echo UAC.ShellExecute "cmd.exe", "/c """"%~f0""""", "", "runas", 1 >> "%temp%\elevate_vcam.vbs"
    "%temp%\elevate_vcam.vbs"
    del "%temp%\elevate_vcam.vbs"
    exit /B
)

cd /d "%~dp0backend\drivers\unitycapture"
echo Registering 64-bit Virtual Camera Filter...
regsvr32 /s "UnityCaptureFilter64.dll"

echo Registering 32-bit Virtual Camera Filter...
regsvr32 /s "UnityCaptureFilter32.dll"

echo.
echo ========================================================
echo SUCCESS: Virtual Camera Registered Successfully!
echo You can now use "Start Virtual Camera" in Face Swap!
echo ========================================================
echo.
pause
