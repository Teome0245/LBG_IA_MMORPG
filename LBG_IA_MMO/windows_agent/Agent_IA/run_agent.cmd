@echo off
cd /d C:\Agent_IA

REM Lancement de l’agent IA Windows
REM -----------------------------------------------------------------------------
REM Desktop (hybride) — config externalisée + hot-reload
REM -----------------------------------------------------------------------------
set LBG_DESKTOP_ENV_PATH=C:\Agent_IA\desktop.env

REM Préférence : venv local si présent, sinon python du PATH.
set PYEXE=python
if exist "C:\Agent_IA\.venv\Scripts\python.exe" set PYEXE="C:\Agent_IA\.venv\Scripts\python.exe"

%PYEXE% -m uvicorn main:app --host 0.0.0.0 --port 5005

