@echo off
setlocal
cd /d "%~dp0"

rem Starts DeFaketive for use or for a demo:
rem   server.py (the original DeFaketive app plus a few read-only database routes) on port 5000,
rem   and the finished build of this shadcn version on port 5173 (its admin side is at /admin).
rem To change the code and see it update as you type, use dev.cmd instead.
rem The original app: DEFAKETIVE_ORIGINAL, else its own folder beside this one (the developer's PC, with the real
rem database), else backend\, the copy this repo carries so it runs on any PC (set up by setup.cmd).
set "OLD=%~dp0..\Capstone-Version-Control-Version-1.1"
if not exist "%OLD%\webapp.py" set "OLD=%~dp0backend"
if defined DEFAKETIVE_ORIGINAL set "OLD=%DEFAKETIVE_ORIGINAL%"
set "PY=%OLD%\.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo The app's Python environment was not found in:
    echo   %OLD%
    echo Run setup.cmd first ^(once per PC^), then start again.
    pause
    exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
    echo Node.js is not installed. Install the LTS version from https://nodejs.org and try again.
    pause
    exit /b 1
)
if not exist node_modules (
    echo Installing packages, first time only...
    call npm install
)

rem Already running? Then just open it. Half running? Say so instead of failing oddly.
node scripts\wait-and-open.mjs --if-running
if not errorlevel 1 (
    echo DeFaketive is already running. It is now open in your browser.
    rem A short pause so the line above can be read (ping is a pause that works without a keyboard).
    ping -n 4 127.0.0.1 >nul
    exit /b 0
)
if errorlevel 2 (
    echo Port 5000 or 5173 is already in use by something else.
    echo Close the other DeFaketive windows, then start again.
    pause
    exit /b 1
)

rem Build only when something changed since the last build.
node scripts\needs-build.mjs
if errorlevel 1 (
    echo Preparing the app, this takes about half a minute...
    call npm run build
    if errorlevel 1 (
        echo The app could not be prepared. Nothing was started.
        pause
        exit /b 1
    )
)

echo Starting DeFaketive (the original app plus the database routes) on http://127.0.0.1:5000 ...
start "DeFaketive server (keep open)" /d "%OLD%" "%PY%" "%~dp0server.py"

echo Starting the app on http://localhost:5173 ...
echo The browser opens by itself when both are ready. Keep this window open.
start "" /b node scripts\wait-and-open.mjs
rem Says so here when saved reports are older than the checker (it prints nothing when all are up to date).
start "" /b "%PY%" "%~dp0scripts\recheck_products.py" --behind
call npm run preview -- --port 5173 --strictPort
