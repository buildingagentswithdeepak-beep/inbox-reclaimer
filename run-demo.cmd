@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH="
set "HERMES_HOME=%~dp0.demo-profile"
set "HELPER=%LOCALAPPDATA%\hermes\hermes-agent\skills\productivity\google-workspace\scripts"
if not "%~1"=="" set "HELPER=%~1"
if not exist "%HELPER%\_hermes_home.py" (
  echo Installed google-workspace helper not found. Pass its scripts directory as the first argument.
  exit /b 2
)
if not exist ".venv\Scripts\reclaim.exe" (
  echo Run uv sync --frozen first.
  exit /b 2
)
.venv\Scripts\reclaim.exe --workspace-scripts "%HELPER%" --demo analyze --full-resync --redact-subjects --attachments --html "%HERMES_HOME%\inbox_reclaimer\reports\report-demo.html"
if errorlevel 1 exit /b %errorlevel%
.venv\Scripts\reclaim.exe --workspace-scripts "%HELPER%" --demo propose --action trash
if errorlevel 1 exit /b %errorlevel%
echo.
echo Synthetic demo only. No Google credentials loaded and no mailbox accessed.
echo Report: %HERMES_HOME%\inbox_reclaimer\reports\report-demo.html
endlocal
