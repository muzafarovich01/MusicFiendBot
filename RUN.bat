@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Avval SETUP.bat ni ishga tushiring.
 pause
 exit /b 1
)
.venv\Scripts\python.exe bot.py
pause
