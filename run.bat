@echo off
cd /d "%~dp0"

rem primeira vez: cria o venv e instala as dependencias automaticamente
if exist ".venv\Scripts\python.exe" goto :run

echo [run.bat] venv nao encontrado - a criar .venv e instalar dependencias (so na primeira vez)...

rem procura o Python: launcher py, depois o python do PATH, depois instalacoes comuns
set "PYEXE="
py -3.12 --version >nul 2>&1 && set "PYEXE=py -3.12"
if not defined PYEXE py --version >nul 2>&1 && set "PYEXE=py"
if not defined PYEXE python --version >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYEXE goto :erro

%PYEXE% -m venv .venv
if errorlevel 1 goto :erro
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :erro

:run
start "" http://localhost:7860/app
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 7860
goto :eof

:erro
echo [run.bat] falhou a preparacao do ambiente. Instala o Python 3.12 e volta a tentar.
pause
