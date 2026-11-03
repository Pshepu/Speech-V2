@echo off
chcp 65001 >nul
title Speech V2 - Generar contenido
cd /d "%~dp0"
echo.
echo  Genera (o completa) el vocabulario, los paquetes C1 y la gramatica con la IA de Groq.
echo  Es reanudable: si se corta o se agota el limite diario gratuito, vuelve a ejecutarlo otro dia.
echo  Consejo: ejecutalo cuando NO estes usando la app (comparten el mismo limite diario).
echo.
backend\.venv\Scripts\python.exe scripts\build_content.py
pause
