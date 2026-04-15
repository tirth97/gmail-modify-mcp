@echo off
REM Cross-platform launcher for gmail-modify-mcp (Windows cmd.exe / PowerShell).
REM
REM Forwards every argument to the console-script entry point installed in the
REM project's local virtualenv (.venv\Scripts\gmail-modify-mcp.exe). From the
REM project root run:  gmail-modify-mcp status   (cmd.exe)
REM                or  .\gmail-modify-mcp status (PowerShell)
REM
REM This avoids "command not found" when the venv isn't activated.

setlocal
set "SCRIPT_DIR=%~dp0"

if exist "%SCRIPT_DIR%.venv\Scripts\gmail-modify-mcp.exe" (
    "%SCRIPT_DIR%.venv\Scripts\gmail-modify-mcp.exe" %*
    exit /b %errorlevel%
)

echo gmail-modify-mcp: venv entry point not found under %SCRIPT_DIR%.venv 1>&2
echo Set it up with: 1>&2
echo   python -m venv .venv 1>&2
echo   .venv\Scripts\python.exe -m pip install -e . 1>&2
exit /b 1
