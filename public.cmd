@echo off
setlocal
cd /d "%~dp0"

rem Starts DeFaketive for the public: serve.py on http://127.0.0.1:8080, with https-only sign-in cookies and the
rem visitor's address read from Cloudflare (Cloudflare Tunnel points the public address at this port).
rem See README, "Putting it online". To use the app on this PC only, use start.cmd instead.
rem Extra options are passed on to serve.py, for example: public.cmd --port 8081
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
"%PY%" -c "import waitress" >nul 2>nul
if errorlevel 1 (
    echo Installing the web server, first time only...
    "%PY%" -m pip install --disable-pip-version-check -q "waitress==3.0.2"
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

title DeFaketive for the public (keep open)
"%PY%" "%~dp0serve.py" --https --proxy cloudflare %*
pause
