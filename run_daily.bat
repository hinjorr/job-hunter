@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m jobhunter.main >> run.log 2>&1
