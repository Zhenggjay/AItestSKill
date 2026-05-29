@echo off
title API Test Automation Platform Runner
echo ====================================================
echo   API Test Automation and Visualization Platform
echo ====================================================
echo.

echo [1/2] Checking and installing Python dependencies...
python -m pip install -r requirements.txt

if %ERRORLEVEL% neq 0 (
    echo [WARNING] Pip failed to install packages. Trying standard pip install fastapi uvicorn...
    pip install fastapi uvicorn
)

echo.
echo [2/2] Launching the FastAPI server...
echo Server starting at http://127.0.0.1:8000
echo.

:: Open browser automatically
start http://127.0.0.1:8000

:: Start uvicorn
uvicorn main:app --reload --host 127.0.0.1 --port 8000

pause
