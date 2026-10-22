@echo off
rem Daily discovery run (scheduled task "Weavers FBA Discovery"). Output appended to data\discovery_log.txt
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
echo ===== %date% %time% >> data\discovery_log.txt
.venv\Scripts\python.exe -m scripts.discover >> data\discovery_log.txt 2>&1
rem Publish the scan's data to GitHub (data only, [skip ci]); failures are logged and retried next day
.venv\Scripts\python.exe -m scripts.publish_data >> data\discovery_log.txt 2>&1
