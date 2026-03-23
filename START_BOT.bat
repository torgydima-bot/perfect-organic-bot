@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Perfect Organic Bot
echo Окно можно свернуть — не закрывай, пока бот нужен онлайн.
echo Остановка: STOP_BOT.bat или закрой это окно.
echo.

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "%~dp0telegram_bot\run_bot.py"
) else (
  echo Виртуальное окружение не найдено. Сначала запусти setup_windows.bat
  pause
  exit /b 1
)

pause
