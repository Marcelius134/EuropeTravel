@echo off
rem EuropeTravel: set up on first use, then start the app and open it in the browser.
rem Double-click this file, or run it from a terminal in the project folder.
setlocal
cd /d "%~dp0"

set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% --version >nul 2>nul
if errorlevel 1 goto no_python

if exist "venv\Scripts\python.exe" goto install
echo Setting up for the first time. This takes a minute...
%PY% -m venv venv
if errorlevel 1 goto no_venv

:install
"venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto no_packages

echo.
echo EuropeTravel is starting at http://127.0.0.1:5000
echo Keep this window open. Press Ctrl+C here to stop the app.
echo.
start "" /b "venv\Scripts\python.exe" -c "import time, webbrowser; time.sleep(2.5); webbrowser.open('http://127.0.0.1:5000')"
"venv\Scripts\python.exe" -m flask run
goto end

:no_python
echo Python was not found.
echo Install Python 3.10 or newer from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during the install. Then run this file again.
goto end

:no_venv
echo Could not create the "venv" folder. Check that you can write to this folder.
goto end

:no_packages
echo Could not install the packages. Check your internet connection and run this file again.

:end
pause
