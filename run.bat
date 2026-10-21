@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto run

echo Primeira corrida: a criar o ambiente virtual e a instalar dependencias...
set "PY="
py -3.12 -c "print(1)" >nul 2>nul && set "PY=py -3.12"
if not defined PY ( python -c "print(1)" >nul 2>nul && set "PY=python" )
if not defined PY ( if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe" )
if not defined PY (
  echo Python 3.12 nao foi encontrado. Instala-o de https://www.python.org/downloads/
  pause
  exit /b 1
)
%PY% -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

:run
start "" http://localhost:7860
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 7860
