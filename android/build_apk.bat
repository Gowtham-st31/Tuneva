@echo off
SETLOCAL

pushd "%~dp0"

if exist gradlew.bat (
  call gradlew.bat clean assembleRelease
) else (
  echo gradlew.bat not found. Open this folder in Android Studio and build once to generate wrapper.
  exit /b 1
)

if not exist "..\static\downloads" mkdir "..\static\downloads"

set APK_PATH=app\build\outputs\apk\release\app-release.apk
if exist "%APK_PATH%" (
  copy /y "%APK_PATH%" "..\static\downloads\Tuneva.apk" >nul
  echo Copied ..\static\downloads\Tuneva.apk
) else (
  echo APK not found at %APK_PATH%
  exit /b 1
)

popd
ENDLOCAL
