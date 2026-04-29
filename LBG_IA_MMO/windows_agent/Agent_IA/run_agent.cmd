@echo off
cd /d C:\Agent_IA

REM Lancement de l’agent IA Windows
REM -----------------------------------------------------------------------------
REM Desktop (hybride) — config externalisée + hot-reload
REM -----------------------------------------------------------------------------
set LBG_DESKTOP_ENV_PATH=C:\Agent_IA\desktop.env

"C:\Users\sdesh\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 5005

