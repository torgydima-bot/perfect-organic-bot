@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  Perfect Organic — установка (Windows)
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Не найден Python. Установи с https://www.python.org/downloads/
  echo При установке включи "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Создаю виртуальное окружение .venv ...
  python -m venv .venv
  if errorlevel 1 (
    echo Ошибка создания venv.
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate.bat
echo Устанавливаю зависимости...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo Ошибка pip install.
  pause
  exit /b 1
)

if not exist "telegram_bot\config.py" (
  if exist "telegram_bot\config.example.py" (
    copy /Y "telegram_bot\config.example.py" "telegram_bot\config.py"
    echo.
    echo Создан telegram_bot\config.py — открой файл и вставь BOT_TOKEN и OWNER_CHAT_ID.
  )
)

echo.
echo ============================================
echo  Готово. Запуск бота: START_BOT.bat
echo ============================================
pause
