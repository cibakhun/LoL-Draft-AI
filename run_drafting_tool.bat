@echo off
TITLE Drafting Tool (Server Only)
echo Starting Drafting Tool API (No Crawler)...
set ENABLE_CRAWLER=false
py -m src.server
pause
