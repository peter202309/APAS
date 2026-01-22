@echo off
REM Create a local profile directory so login persists
if not exist "chrome_data" mkdir "chrome_data"

echo Launching Chrome in Debug Mode on Port 9223...
echo You can log in to your Google Account in this window.
echo KEEP THIS WINDOW OPEN while running the scraper.

REM Launch Chrome with debugging port 9223 and specific user data dir
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 --user-data-dir="%~dp0chrome_data"

echo.
echo Chrome launched.
pause
