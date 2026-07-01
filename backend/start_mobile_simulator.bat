@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM One-click Android emulator + Flutter run launcher (from backend folder)

set "ANDROID_AVD_HOME=E:\AndroidAVD"
set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.10.7-hotspot"
set "PUB_CACHE=E:\pub-cache"
set "EMULATOR_ID=Pixel_7_E36"
set "ADB_EXE=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
set "EMULATOR_EXE=%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe"
set "EMULATOR_ARGS=-gpu host -no-boot-anim -no-metrics"
set "MOBILE_DIR=%~dp0..\MOBILE"
set "FLUTTER_CMD=E:\my-iot-project\Flutter\flutter\bin\flutter.bat"
set "CI=true"
set "FLUTTER_SUPPRESS_ANALYTICS=true"
set "EXIT_CODE=0"

for %%I in ("%MOBILE_DIR%") do set "MOBILE_DIR=%%~fI"

echo ==================================================
echo  Android Simulator One-Click Launcher
echo ==================================================
echo MOBILE_DIR      = %MOBILE_DIR%
echo ANDROID_AVD_HOME= %ANDROID_AVD_HOME%
echo JAVA_HOME       = %JAVA_HOME%
echo PUB_CACHE       = %PUB_CACHE%
echo EMULATOR_ID     = %EMULATOR_ID%
echo FLUTTER_CMD     = %FLUTTER_CMD%
echo EMULATOR_EXE    = %EMULATOR_EXE%
echo EMULATOR_ARGS   = %EMULATOR_ARGS%
echo ==================================================

if not exist "%MOBILE_DIR%\pubspec.yaml" (
  echo [ERROR] Cannot find Flutter project at %MOBILE_DIR%
  set "EXIT_CODE=1"
  goto end
)

if not exist "%JAVA_HOME%\bin\java.exe" (
  echo [ERROR] JAVA_HOME is invalid: %JAVA_HOME%
  set "EXIT_CODE=1"
  goto end
)

set "PATH=%JAVA_HOME%\bin;%PATH%"

if not exist "%ANDROID_AVD_HOME%" (
  mkdir "%ANDROID_AVD_HOME%" >nul 2>nul
)

cd /d "%MOBILE_DIR%"

echo.
echo [1/5] Checking Flutter...
if not exist "%FLUTTER_CMD%" (
  echo [ERROR] Flutter not found at: %FLUTTER_CMD%
  set "EXIT_CODE=1"
  goto end
)

for %%I in ("%FLUTTER_CMD%") do set "PATH=%%~dpI;%PATH%"

call "%FLUTTER_CMD%" --suppress-analytics --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Flutter command exists but failed to run: %FLUTTER_CMD%
  set "EXIT_CODE=1"
  goto end
)
echo Flutter OK: %FLUTTER_CMD%

echo.
echo [2/5] Ensuring emulator exists...
call "%FLUTTER_CMD%" emulators | findstr /I /C:"%EMULATOR_ID%" >nul
if errorlevel 1 (
  echo Emulator %EMULATOR_ID% not found. Creating...
  call "%FLUTTER_CMD%" emulators --create --name %EMULATOR_ID%
  if errorlevel 1 (
    echo [ERROR] Failed to create emulator %EMULATOR_ID%.
    set "EXIT_CODE=1"
    goto end
  )
)

echo.
echo [3/5] Launching emulator...
set "EMULATOR_ALREADY_ONLINE="
if exist "%ADB_EXE%" (
  "%ADB_EXE%" start-server >nul 2>nul
  "%ADB_EXE%" devices > "%TEMP%\_smh_adb_existing.txt" 2>nul
  findstr /R /C:"^emulator-[0-9][0-9][0-9][0-9][ ]*device" "%TEMP%\_smh_adb_existing.txt" >nul 2>nul
  if not errorlevel 1 set "EMULATOR_ALREADY_ONLINE=1"
)

if defined EMULATOR_ALREADY_ONLINE (
  echo Emulator already online. Reusing existing instance.
  goto after_emulator_launch
)

if exist "%ADB_EXE%" (
  "%ADB_EXE%" kill-server >nul 2>nul
  "%ADB_EXE%" start-server >nul 2>nul
)

if exist "%EMULATOR_EXE%" (
  start "Android Emulator" "%EMULATOR_EXE%" -avd %EMULATOR_ID% %EMULATOR_ARGS%
  timeout /t 2 >nul
  tasklist | findstr /I "emulator.exe" >nul
  if errorlevel 1 (
    echo [ERROR] Emulator process did not start.
    echo Try launching manually: "%EMULATOR_EXE%" -avd %EMULATOR_ID%
    set "EXIT_CODE=1"
    goto end
  )
) else (
  start "Android Emulator" cmd /c "set ANDROID_AVD_HOME=%ANDROID_AVD_HOME%&& call \"%FLUTTER_CMD%\" emulators --launch %EMULATOR_ID%"
)

:after_emulator_launch

echo.
echo [4/5] Waiting for emulator to become online...
set "ANDROID_DEVICE="
set /a retries=0

if defined EMULATOR_ALREADY_ONLINE goto wait_loop

REM Wait for emulator snapshot to finish loading, then restart ADB
REM (snapshot load triggers ADB offline - must restart AFTER it finishes)
echo Waiting for emulator snapshot to load (15s)...
timeout /t 15 >nul
echo Restarting ADB server to reconnect emulator...
if exist "%ADB_EXE%" (
  "%ADB_EXE%" kill-server >nul 2>nul
  timeout /t 2 >nul
  "%ADB_EXE%" start-server >nul 2>nul
  timeout /t 3 >nul
)

:wait_loop
set /a retries+=1
set "ANDROID_DEVICE="

if exist "%ADB_EXE%" (
  "%ADB_EXE%" devices > "%TEMP%\_smh_adb.txt" 2>nul
  for /f "skip=1 tokens=1,2 delims=	 " %%A in ('type "%TEMP%\_smh_adb.txt"') do (
    if /I "%%B"=="device" set "ANDROID_DEVICE=%%A"
  )
  if not defined ANDROID_DEVICE (
    findstr /I "offline" "%TEMP%\_smh_adb.txt" >nul 2>nul
    if not errorlevel 1 (
      echo ADB device offline - restarting ADB server...
      "%ADB_EXE%" kill-server >nul 2>nul
      timeout /t 2 >nul
      "%ADB_EXE%" start-server >nul 2>nul
      timeout /t 3 >nul
    )
  )
) else (
  for /f "tokens=1" %%A in ('call "%FLUTTER_CMD%" devices ^| findstr /R /C:"emulator-[0-9][0-9][0-9][0-9]"') do (
    set "ANDROID_DEVICE=%%A"
  )
)

if defined ANDROID_DEVICE goto got_device

if %retries% geq 120 (
  echo [ERROR] Emulator did not come online in time.
  echo Tip: close emulator window and run this file again.
  set "EXIT_CODE=1"
  goto end
)

echo Waiting... (%retries%/120)
timeout /t 3 >nul
goto wait_loop

:got_device
echo Emulator online: %ANDROID_DEVICE%

if exist "%ADB_EXE%" (
  echo Waiting for ADB handshake...
  "%ADB_EXE%" -s %ANDROID_DEVICE% wait-for-device >nul 2>nul

  echo Verifying ADB device state...
  set /a state_retries=0
  :state_wait_loop
  set /a state_retries+=1
  set "ADB_STATE="
  for /f %%S in ('"%ADB_EXE%" -s %ANDROID_DEVICE% get-state 2^>nul') do set "ADB_STATE=%%S"
  if /I "!ADB_STATE!"=="device" goto state_ready
  if !state_retries! geq 45 (
    echo [WARN] ADB still not fully online. Restarting ADB once...
    "%ADB_EXE%" kill-server >nul 2>nul
    "%ADB_EXE%" start-server >nul 2>nul
    "%ADB_EXE%" -s %ANDROID_DEVICE% wait-for-device >nul 2>nul
    set "ADB_STATE="
    for /f %%S in ('"%ADB_EXE%" -s %ANDROID_DEVICE% get-state 2^>nul') do set "ADB_STATE=%%S"
    if /I "!ADB_STATE!"=="device" goto state_ready
    echo [ERROR] ADB state is still '!ADB_STATE!'.
    set "EXIT_CODE=1"
    goto end
  )
  timeout /t 2 >nul
  goto state_wait_loop

  :state_ready

  echo Waiting Android boot completion...
  set /a boot_retries=0
  :boot_wait_loop
  set /a boot_retries+=1
  set "BOOT_DONE="
  for /f %%B in ('"%ADB_EXE%" -s %ANDROID_DEVICE% shell getprop sys.boot_completed 2^>nul') do set "BOOT_DONE=%%B"
  if "!BOOT_DONE!"=="1" goto boot_ready
  if !boot_retries! geq 60 (
    echo [WARN] Boot completion timeout. Continue anyway.
    goto boot_ready
  )
  timeout /t 2 >nul
  goto boot_wait_loop

  :boot_ready
  "%ADB_EXE%" -s %ANDROID_DEVICE% shell input keyevent 82 >nul 2>nul
  "%ADB_EXE%" -s %ANDROID_DEVICE% shell settings put secure show_ime_with_hard_keyboard 1 >nul 2>nul
)

echo.
echo [5/5] Running app on emulator...
call "%FLUTTER_CMD%" pub get
if errorlevel 1 (
  echo [ERROR] flutter pub get failed.
  set "EXIT_CODE=1"
  goto end
)

call "%FLUTTER_CMD%" run -d %ANDROID_DEVICE% --no-dds
if errorlevel 1 (
  echo [ERROR] flutter run failed.
  set "EXIT_CODE=1"
  goto end
)

echo.
echo [DONE] App launched successfully.

:end
echo.
if "%EXIT_CODE%"=="0" (
  echo [DONE] Script completed successfully.
) else (
  echo [ERROR] Script ended with errors. Exit code: %EXIT_CODE%
)
echo.
echo === Nhan phim bat ky de dong ===
pause >nul

endlocal
