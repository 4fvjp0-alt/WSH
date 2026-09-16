@echo off
REM Launches the simulator without changing PowerShell's execution policy.
REM Double-click this file, or run  Run-Windows.cmd  from any shell.
REM Arguments are passed through, e.g.  Run-Windows.cmd -Test
setlocal
cd /d "%~dp0"
where pwsh >nul 2>nul
if %errorlevel%==0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-Windows.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-Windows.ps1" %*
)
set EXITCODE=%errorlevel%
if not "%EXITCODE%"=="0" (
    echo.
    echo [!] Exited with code %EXITCODE%.
    pause
)
endlocal & exit /b %EXITCODE%
