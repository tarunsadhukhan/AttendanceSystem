@echo off
REM Restart the Attendance System Backend Server
REM Location: E:\sjm\AttendanceSystem

echo ========================================
echo Restarting Attendance System Server
echo ========================================
echo.

REM Kill existing Python processes (optional - comment out if not needed)
REM taskkill /F /IM python.exe >nul 2>&1

echo Starting server on port 5051...
cd /d E:\sjm\AttendanceSystem

REM Check if virtual environment exists
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Start the server
python app.py

pause

