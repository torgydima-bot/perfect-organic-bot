@echo off
chcp 65001 >nul
echo ВНИМАНИЕ: этот скрипт убивал ВСЕ процессы python.exe — опасно при других проектах.
echo Используй в корне репозитория: STOP_BOT.bat
echo.
cd /d "%~dp0\.."
if exist "STOP_BOT.bat" (
  call STOP_BOT.bat
) else (
  powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'bot\\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
  pause
)
