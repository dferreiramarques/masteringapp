@echo off
cd /d "%~dp0"

rem primeira vez: cria o venv e instala as dependencias automaticamente
if not exist ".venv\Scripts\python.exe" (
    echo [run.bat] venv nao encontrado - a criar .venv e instalar dependencias ^(so na primeira vez^)...
    python -m venv .venv
    if errorlevel 1 goto :erro
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 goto :erro
)

start "" http://localhost:7860
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 7860
goto :eof

:erro
echo [run.bat] falhou a preparacao do ambiente. Confirma se o Python esta no PATH: "python --version"
pause
