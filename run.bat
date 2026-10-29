@echo off
cd /d "%~dp0"

rem primeira vez: cria o venv e instala as dependencias automaticamente.
rem O venv EXISTENTE e' validado antes de ser usado: um .venv criado noutra
rem instalacao/maca (python desinstalado, pasta movida) existe mas nao funciona.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "pass" >nul 2>&1
    if not errorlevel 1 goto :run
    echo [run.bat] .venv existente nao funciona - a recriar...
    rmdir /s /q ".venv"
)

echo [run.bat] venv nao encontrado - a criar .venv e instalar dependencias (so na primeira vez)...

rem procura o Python: launcher py, depois o python do PATH, depois instalacoes comuns
set "PYEXE="
py -3.12 --version >nul 2>&1 && set "PYEXE=py -3.12"
if not defined PYEXE py -3.13 --version >nul 2>&1 && set "PYEXE=py -3.13"
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
rem o browser abre SO quando o backend já aceita ligações (antes abria logo,
rem antes do uvicorn arrancar, e a 1.ª carga falhava com "Failed to fetch")
start "" /min cmd /c "powershell -NoProfile -Command "for ($i=0; $i -lt 240; $i++) { if (Get-NetTCPConnection -LocalPort 7860 -State Listen -ErrorAction SilentlyContinue) { Start-Process 'http://localhost:7860/app'; exit }; Start-Sleep -Milliseconds 500 }""
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 7860
goto :eof

:erro
echo [run.bat] falhou a preparacao do ambiente. Instala o Python 3.12 (ou 3.13 com o launcher py) e volta a tentar.
pause
