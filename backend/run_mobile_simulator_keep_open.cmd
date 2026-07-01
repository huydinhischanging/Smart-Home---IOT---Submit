@echo off
cd /d "%~dp0"
call "%~dp0start_mobile_simulator.bat"
echo.
echo Launcher finished with exit code %errorlevel%.
echo Press any key to close this window...
pause >nul
