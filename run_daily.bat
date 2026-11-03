@echo off
cd /d "%~dp0"
python -m jobhunter.main >> run.log 2>&1
