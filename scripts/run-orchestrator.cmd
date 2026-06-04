@echo off
REM Bot Squad Orchestrator — runs every 2 hours
REM Wrapper batch file for Windows Task Scheduler
chcp 65001 > nul
cd /d "%USERPROFILE%\AgentShared"
set PYTHONIOENCODING=utf-8
"C:\Users\franz\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" "scripts\orchestrator.py" >> logs\orchestrator-cron.log 2>&1
