@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

echo Reading the Firefox login and checking the raids...
%PY% "%~dp0scripts\AuditAndAmend.py"
echo.
pause
exit /b %errorlevel%
