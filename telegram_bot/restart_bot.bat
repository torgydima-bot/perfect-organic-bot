@echo off
cd /d "%~dp0"
:restart
echo ====================================
echo  Perfect Organic Bot запускается...
echo  Закрой окно чтобы остановить бота
echo ====================================
python bot.py
echo.
echo Бот остановился. Перезапуск через 5 сек...
timeout /t 5 /nobreak >nul
goto restart
