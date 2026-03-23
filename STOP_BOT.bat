@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Останавливаю процессы Python, в командной строке которых есть bot.py ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'bot\\.py' }; if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('PID ' + $_.ProcessId + ' остановлен') } } else { Write-Host 'Процесс bot.py не найден.' }"
echo.
pause
