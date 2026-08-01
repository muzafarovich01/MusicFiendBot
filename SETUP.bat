@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv py -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
 echo.
 echo Tayyor. Endi .env faylini ochib barcha API kalitlarini kiriting.
pause
