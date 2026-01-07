@echo off
echo [1/3] Killing stuck Python processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM py.exe >nul 2>&1
echo [2/3] Processes cleaned.
print
echo [3/3] Starting Compiler...
py src/tools/compile_dataset.py
echo.
echo Done.
pause
