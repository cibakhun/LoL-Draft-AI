@echo off
TITLE Hybrid OHYBRID ORACLracle Launcher
echo .
echo ==========================================
echo        THE HYBRID ORACLE (RELEASE)
echo ==========================================
echo .
echo [1/3] Starting Profile ^& Meta Engine (Backend)...
start /min "HybridOracle_Backend" cmd /k "py -m src.server"

echo [2/3] Starting UI Renderer (Frontend)...
cd "overlay"
start /min "HybridOracle_Renderer" cmd /k "node node_modules/vite/bin/vite.js"

echo [3/3] Waiting for systems to warm up (10s)...
timeout /t 10 /nobreak >nul

echo [!] Launching Overlay Window...
:: Direct Node execution to bypass batch file issues with '&' in project path
call node "node_modules/electron/cli.js" .

echo [*] Oracle Closed.
pause
