@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -U -r requirements.txt
if not exist .env copy .env.example .env
if exist temp rmdir /s /q temp
mkdir temp
python bot.py
pause
