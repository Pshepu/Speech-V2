@echo off
chcp 65001 >nul
title Speech V2 - Entrenador de idiomas
cd /d "%~dp0"

REM ============ 1. Clave de IA (Groq) ============
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo  PRIMER USO: falta tu clave GRATIS de Groq.
    echo  1. Entra a https://console.groq.com  -^>  API Keys  -^>  Create API Key
    echo  2. Se abrira el Bloc de Notas: pega la clave despues de GROQ_API_KEY=
    echo  3. Guarda (Ctrl+S) y cierra el Bloc de Notas para continuar.
    echo.
    pause
    notepad ".env"
)

REM ============ 2. Entorno de Python (solo la primera vez) ============
set "PY=backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo.
    echo  Instalando dependencias de Python por primera vez (puede tardar varios minutos^)...
    where uv >nul 2>nul
    if errorlevel 1 (
        echo  Instalando "uv" ^(gestor de Python^)...
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    )
    uv venv --python 3.13 backend\.venv || goto :error
    uv pip install --python "%PY%" -r backend\requirements.txt || goto :error
    echo  Instalando PyTorch ^(CPU^) para la evaluacion por fonemas...
    uv pip install --python "%PY%" torch --index-url https://download.pytorch.org/whl/cpu || echo  [Aviso] Sin PyTorch: se usara el modo basico de pronunciacion.
)

REM ============ 3. Interfaz web (solo si no esta compilada) ============
if not exist "frontend\dist\index.html" (
    where npm >nul 2>nul
    if errorlevel 1 (
        echo  [Error] Falta compilar la interfaz y no se encontro Node.js ^(https://nodejs.org^).
        goto :error
    )
    pushd frontend
    call npm install || goto :error
    call npm run build || goto :error
    popd
)

REM ============ 4. Arrancar ============
echo.
echo  Iniciando Speech V2 en http://localhost:3000
echo  La primera vez se descarga el modelo de fonemas (~1,2 GB^): la evaluacion de pronunciacion
echo  estara lista cuando termine. Para DETENER la app, cierra esta ventana.
echo.
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:3000"
"%PY%" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 3000
goto :eof

:error
echo.
echo  Algo fallo. Revisa los mensajes de arriba.
pause
