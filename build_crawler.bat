@echo off
echo ==================================================
echo      VANTAGE CRAWLER BUILDER (to .exe)
echo ==================================================
echo.

:: 1. Detect Python Command
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=python
    echo [INFO] Using 'python' command.
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PY_CMD=py
        echo [INFO] Using 'py' command (Python Launcher).
    ) else (
        echo [ERROR] neither 'python' nor 'py' found. Please install Python from python.org.
        echo         Make sure to check "Add Python to PATH" or install the "py" launcher.
        pause
        exit /b
    )
)

echo.
echo [1/3] Installing/Upgrading PyInstaller...
%PY_CMD% -m pip install pyinstaller --upgrade
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b
)

echo.
echo [2/3] Building Standalone Executable...
echo This may take a minute...
%PY_CMD% -m PyInstaller --onefile --name "VantageCrawler" --icon=NONE standalone_crawler.py

if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b
)

echo.
echo [3/3] Cleanup...
rmdir /s /q build
del /q VantageCrawler.spec

echo.
echo ==================================================
echo [SUCCESS] Crawler Executable Ready!
echo Location: dist\VantageCrawler.exe
echo ==================================================
echo.
pause
