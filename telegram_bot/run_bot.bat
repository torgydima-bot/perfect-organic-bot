@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "ROOT=%~dp0.."
title Perfect Organic Bot (автоперезапуск)
echo ============================================
echo  Запускаю бот с автоперезапуском...
echo  НЕ закрывай это окно!
echo ============================================
if exist "%ROOT%\.venv\Scripts\python.exe" (
  "%ROOT%\.venv\Scripts\python.exe" "%~dp0run_bot.py"
) else (
  echo Нет .venv в корне проекта. Запусти из корня: setup_windows.bat
  echo Пробую системный python...
  python "%~dp0run_bot.py"
)
pause
