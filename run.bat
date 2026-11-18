@echo off
rem Run from Windows Task Scheduler: move to this folder and run main.py with the venv Python.
rem (Comments are in English because cmd.exe misreads UTF-8 Japanese text.)
cd /d "%~dp0"
set PYTHONUTF8=1
".venv\Scripts\python.exe" src\main.py --scheduled >> run.log 2>&1
