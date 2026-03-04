@echo off
echo Останавливаю все процессы python.exe...
taskkill /F /IM python.exe 2>nul
echo Готово. Теперь запусти run_bot.bat
pause
