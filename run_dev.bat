@echo off
cd /d "%~dp0"
echo Starting Django at http://127.0.0.1:18080/
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:18080
