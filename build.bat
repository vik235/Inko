@echo off
REM Build Inko into dist\Inko\Inko.exe
REM Then optionally compile installer\Inko-Setup.exe with Inno Setup.

setlocal
cd /d "%~dp0"

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv || goto :err
)

call .venv\Scripts\activate.bat || goto :err

echo Installing dependencies...
REM Use python -m pip so pip can upgrade itself on Windows
python -m pip install --quiet --upgrade pip || goto :err
python -m pip install --quiet -r requirements.txt pyinstaller || goto :err

echo Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building with PyInstaller...
pyinstaller --noconfirm Inko.spec || goto :err

echo.
echo Build complete: dist\Inko\Inko.exe
echo.
echo To create the installer, run:  iscc installer.iss
echo (requires Inno Setup 6 on PATH: https://jrsoftware.org/isdl.php)
echo.
exit /b 0

:err
echo BUILD FAILED.
exit /b 1
