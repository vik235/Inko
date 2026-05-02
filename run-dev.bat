@echo off
REM Launch Inko in DEV mode.
REM Data is stored in separate folders so dev work cannot affect prod data.

setlocal
cd /d "%~dp0"

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv || goto :err
    call .venv\Scripts\activate.bat
    pip install --quiet -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

set INKO_ENV=dev
echo.
echo  ================================
echo   Inko — DEV mode
echo  ================================
echo   Data:    %%APPDATA%%\Inko-dev\
echo   PDFs:    %%USERPROFILE%%\Documents\Inko-dev\
echo   Backups: %%USERPROFILE%%\Documents\Inko-dev\backups\
echo.

.venv\Scripts\python.exe app.py
exit /b %errorlevel%

:err
echo Setup failed.
exit /b 1
