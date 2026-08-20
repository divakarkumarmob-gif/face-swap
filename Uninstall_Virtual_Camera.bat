@echo off
title Face Swap Virtual Camera Uninstaller
echo ========================================================
echo Uninstalling Virtual Camera Driver
echo ========================================================
echo.

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
regsvr32 /u /s "UnityCaptureFilter64.dll"
regsvr32 /u /s "UnityCaptureFilter32.dll"

echo.
echo Virtual Camera uninstalled successfully.
echo.
pause
