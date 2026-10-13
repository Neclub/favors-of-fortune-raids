@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

echo Choose a backup to put the site back.
%PY% "%~dp0scripts\AuditAndAmend.py" --restore
echo.
pause
exit /b %errorlevel%
