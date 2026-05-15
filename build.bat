@echo off
REM Build the Attendance System backend into a onefile .exe using Nuitka.
REM Output: build\juteatt.exe
setlocal
cd /d "%~dp0"

REM Activate venv
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo No venv found. Create one and install deps first.
    exit /b 1
)

REM Ensure build deps are present (Nuitka[onefile] pulls zstandard for compression).
python -m pip install --quiet --upgrade "Nuitka[onefile]"

REM Resolve mysql/vendor path (contains auth plugin DLLs + libssl/libcrypto/libsasl).
REM This dir lives as sibling data to the `mysql` package and has no __init__.py.
REM Note: --include-data-dir filters out .dll files (Nuitka treats DLLs as binaries),
REM       so we must use --include-data-files with a recursive glob to bundle them.
for /f "usebackq delims=" %%i in (`python -c "import os, mysql; print(os.path.join(os.path.dirname(mysql.__file__), 'vendor'))"`) do set MYSQL_VENDOR=%%i
if not defined MYSQL_VENDOR (
    echo Failed to resolve mysql/vendor path.
    exit /b 1
)

REM Compile.
REM   --include-package-data=face_recognition_models       -> bundles the .dat weight files
REM   --include-package=face_recognition_models            -> defensive: ensures the package itself is pulled in
REM   --include-package-data=cv2                           -> defensive for opencv config/data
REM   --include-data-files=...vendor\*.dll                 -> mysql ssl/sasl DLLs (libssl, libcrypto, libsasl)
REM   --include-data-files=...vendor\plugin\*.dll          -> mysql auth plugin DLLs (mysql_native_password, etc.)
REM   --assume-yes-for-downloads                           -> auto-accept ccache/depends.exe downloads
REM   --remove-output                                      -> clean intermediate build dir after success
python -m nuitka ^
    --onefile ^
    --standalone ^
    --output-dir=build ^
    --output-filename=juteatt.exe ^
    --include-package=src ^
    --include-package=face_recognition ^
    --include-package=face_recognition_models ^
    --include-package-data=face_recognition_models ^
    --include-package-data=cv2 ^
    --include-data-files=%MYSQL_VENDOR%\*.dll=mysql/vendor/ ^
    --include-data-files=%MYSQL_VENDOR%\plugin\*.dll=mysql/vendor/plugin/ ^
    --assume-yes-for-downloads ^
    --remove-output ^
    app.py

if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo Build complete: build\juteatt.exe
endlocal
