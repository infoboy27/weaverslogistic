@echo off
rem Daily discovery run (scheduled task "Weavers FBA Discovery"). Output appended to data\discovery_log.txt
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
echo ===== %date% %time% >> data\discovery_log.txt
.venv\Scripts\python.exe -m scripts.discover >> data\discovery_log.txt 2>&1
