@echo off
title Gerador de Atividades - SENAI
cd /d "%~dp0"
echo ========================================================
echo   Iniciando o Gerador de Atividades e Planejamento SENAI
echo ========================================================
echo.
.\venv\Scripts\python.exe iniciar_servidor.py
pause
