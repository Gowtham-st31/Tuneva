@echo off
SETLOCAL

REM Run from repo root regardless of invocation location
pushd "%~dp0\.."

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller -q

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist local_server.spec del /f /q local_server.spec

pyinstaller --onefile --paths . --name local_server desktop\local_server.py

if not exist static\downloads mkdir static\downloads
copy /y dist\local_server.exe static\downloads\Tuneva.exe >nul

echo Build complete: static\downloads\Tuneva.exe
popd
ENDLOCAL
