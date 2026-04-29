@echo off
REM Cross-platform launcher for gmail-modify-mcp (Windows cmd.exe / PowerShell).
REM
REM Forwards every argument to the console-script entry point installed in the
REM project's local virtualenv (.venv\Scripts\gmail-modify-mcp.exe). From the
REM project root run:  gmail-modify-mcp status   (cmd.exe)
REM                or  .\gmail-modify-mcp status (PowerShell)
REM
REM Two things this does on top of forwarding:
REM  1. Locates the venv entry point.
REM  2. Pre-flight OAuth check: if the cached token is invalid, automatically
REM     re-runs the consent flow before forwarding the requested command, so
REM     you don't have to manually delete token.json and re-run auth yourself.
REM     The check is skipped when you explicitly invoke 'auth' (to avoid an
REM     infinite or doubled consent flow).

setlocal
set "SCRIPT_DIR=%~dp0"
set "EXE=%SCRIPT_DIR%.venv\Scripts\gmail-modify-mcp.exe"

if not exist "%EXE%" (
    echo gmail-modify-mcp: venv entry point not found under %SCRIPT_DIR%.venv 1>&2
    echo Set it up with: 1>&2
    echo   python -m venv .venv 1>&2
    echo   .venv\Scripts\python.exe -m pip install -e . 1>&2
    exit /b 1
)

REM Pre-flight: skip when the user is explicitly running 'auth'.
if /I "%~1"=="auth" goto :forward

REM Probe the cached token by running status silently.
"%EXE%" status >nul 2>&1
if errorlevel 1 (
    echo gmail-modify-mcp: cached OAuth token is invalid ^(expired/revoked/missing^). 1>&2
    echo gmail-modify-mcp: re-running consent flow... 1>&2
    if exist "%SCRIPT_DIR%token.json" del /q "%SCRIPT_DIR%token.json"
    "%EXE%" auth
    if errorlevel 1 (
        echo gmail-modify-mcp: auth failed 1>&2
        exit /b 1
    )
)

:forward
"%EXE%" %*
exit /b %errorlevel%
