@echo off
REM Restart the Attendance System Backend Server
REM Location: E:\sjm\AttendanceSystem

echo ========================================
echo Restarting Attendance System Server
echo ========================================
echo.

REM Kill any process already listening on port 5051
echo Clearing port 5051...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5051 " ^| findstr "LISTENING"') do (
    echo Killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo Starting server on port 5051...
cd /d E:\sjm\AttendanceSystem

REM Activate virtual environment
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM Start the server
python app.py

pause

