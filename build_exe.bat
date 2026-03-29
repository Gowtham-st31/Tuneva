@echo off
REM Build Tuneva local executable using PyInstaller
REM Usage: run this in activated venv on Windows

SETLOCAL ENABLEDELAYEDEXPANSION

if not exist "%~dp0\venv" (
  echo "No venv detected. Activating project's venv if present."
)

REM Ensure pyinstaller is installed
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

REM Clean previous build artifacts
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist local_server.spec del /f /q local_server.spec

REM Build one-file executable
pyinstaller --onefile --paths . --name local_server local_server.py

if exist dist\local_server.exe (
    if not exist static\downloads mkdir static\downloads
    copy /y dist\local_server.exe static\downloads\Tuneva.exe >nul
    echo Built static\downloads\Tuneva.exe
) else (
    echo Build failed. Check PyInstaller output.
)

ENDLOCAL