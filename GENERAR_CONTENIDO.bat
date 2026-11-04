@echo off
chcp 65001 >nul
title Speech V2 - Generando contenido (puedes minimizar esta ventana)
cd /d "%~dp0"
echo.
echo  Genera o completa el contenido de todos los idiomas con la IA de Groq:
echo   - Vocabulario, frases y paquetes: modelo pequeno (gpt-oss-20b).
echo   - Gramatica: modelo grande (gpt-oss-120b), maximo 10 lecciones al dia
echo     para que la app conserve el resto del limite diario para tus conversaciones.
echo.
echo  Si se agota el limite diario, ESPERA y sigue solo. Puedes cerrar la ventana
echo  cuando quieras: la proxima vez continua donde se quedo.
echo  (Para ir mas rapido sin tope: backend\.venv\Scripts\python.exe scripts\build_content.py --fast)
echo.
backend\.venv\Scripts\python.exe scripts\build_content.py
pause
