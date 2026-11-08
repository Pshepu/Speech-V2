@echo off
chcp 65001 >nul
title Speech V2 - Entrenador de idiomas
cd /d "%~dp0"
REM Nota: este script evita los bloques "if (...)" a proposito. Dentro de ellos, rutas del
REM PATH como "C:\Program Files (x86)" rompen el script. Se usan saltos (goto) en su lugar.

set "PY=backend\.venv\Scripts\python.exe"

REM ============ 0. Si la app ya esta abierta, solo abrimos el navegador ============
netstat -ano | findstr /r /c:":3000 .*LISTENING" >nul
if not errorlevel 1 goto :ya_abierta

REM ============ 1. Clave de IA (Groq) ============
if exist ".env" goto :entorno
copy ".env.example" ".env" >nul
echo.
echo  PRIMER USO: falta tu clave GRATIS de Groq.
echo  1. Entra a https://console.groq.com  -^>  API Keys  -^>  Create API Key
echo  2. Se abrira el Bloc de Notas: pega la clave despues de GROQ_API_KEY=
echo  3. Guarda (Ctrl+S) y cierra el Bloc de Notas para continuar.
echo.
pause
notepad ".env"

:entorno
REM ============ 2. Entorno de Python (solo la primera vez) ============
if exist "%PY%" goto :interfaz
echo.
echo  Instalando dependencias de Python por primera vez (puede tardar varios minutos)...
where uv >nul 2>nul
if not errorlevel 1 goto :uv_listo
echo  Instalando "uv" (gestor de Python)...
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
:uv_listo
uv venv --python 3.13 backend\.venv
if errorlevel 1 goto :error
uv pip install --python "%PY%" -r backend\requirements.txt
if errorlevel 1 goto :error
echo  Instalando PyTorch (CPU) para la evaluacion por fonemas...
uv pip install --python "%PY%" torch --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 echo  [Aviso] Sin PyTorch: se usara el modo basico de pronunciacion.

:interfaz
REM ============ 3. Interfaz web (solo si no esta compilada) ============
if exist "frontend\dist\index.html" goto :arrancar
where npm >nul 2>nul
if errorlevel 1 goto :sin_node
pushd frontend
call npm install
if errorlevel 1 goto :error_popd
call npm run build
if errorlevel 1 goto :error_popd
popd

:arrancar
REM ============ 4. Arrancar ============
echo.
echo  Iniciando Speech V2 en http://localhost:3000
echo  La primera vez se descarga el modelo de fonemas (unos 1,2 GB): la evaluacion de
echo  pronunciacion estara lista cuando termine.
echo.
echo  *** Para DETENER la app, cierra esta ventana. ***
echo.
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:3000"
"%PY%" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 3000
echo.
echo  La app se detuvo. Si ves un error arriba, copialo para revisarlo.
pause
goto :eof

:ya_abierta
echo  La app ya esta en marcha. Abriendo el navegador...
start http://localhost:3000
timeout /t 3 /nobreak >nul
goto :eof

:sin_node
echo.
echo  [Error] Falta compilar la interfaz y no se encontro Node.js (https://nodejs.org).
goto :error

:error_popd
popd
:error
echo.
echo  Algo fallo. Revisa los mensajes de arriba.
pause
