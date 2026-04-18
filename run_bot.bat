@echo off
:: Navigate to the script directory to ensure relative paths work
cd /d "%~dp0"

:: detailed logging for debugging startup
echo Starting Gold Bot at %DATE% %TIME% >> Logs\startup_log.txt

:: Launch the bot using python
:: Assumes python is in PATH. If not, replace with full path to python.exe
"C:\Users\SUJI\AppData\Local\Programs\Python\Python314\python.exe" main.py >> Logs\console_output.log 2>&1

:: If it crashes, log it
if %ERRORLEVEL% NEQ 0 (
    echo Bot crashed with error level %ERRORLEVEL% >> Logs\startup_log.txt
)
