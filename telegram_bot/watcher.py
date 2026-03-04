"""
Следит за изменениями файлов бота и автоматически перезапускает его.
Запусти watcher.bat один раз — дальше перезапуск происходит автоматически.
"""
import time
import os
import subprocess

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
WATCH_FILES = ['bot.py', 'content_plan.py', 'products.py', 'config.py']
DEBOUNCE = 4  # секунд ожидания после последнего изменения перед перезапуском


def get_mtime(f):
    path = os.path.join(BOT_DIR, f)
    return os.path.getmtime(path) if os.path.exists(path) else 0


def kill_bot():
    """Останавливает процесс python bot.py через wmic."""
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where',
             'name="python.exe" and CommandLine like "%bot.py%"',
             'get', 'ProcessId'],
            capture_output=True, text=True, timeout=5
        )
        killed = False
        for line in result.stdout.splitlines():
            pid = line.strip()
            if pid.isdigit():
                subprocess.run(['taskkill', '/f', '/pid', pid],
                               capture_output=True, timeout=5)
                print(f"  ⛔ Остановлен PID {pid}")
                killed = True
        return killed
    except Exception as e:
        print(f"  ⚠️ kill_bot ошибка: {e}")
        return False


mtimes = {f: get_mtime(f) for f in WATCH_FILES}
last_change_time = 0

print("👀 Watcher запущен. Слежу за:", ", ".join(WATCH_FILES))
print("🔄 При изменении — автоперезапуск через", DEBOUNCE, "сек\n")

while True:
    time.sleep(1)

    for f in WATCH_FILES:
        new_mtime = get_mtime(f)
        if new_mtime > mtimes[f]:
            mtimes[f] = new_mtime
            last_change_time = time.time()
            print(f"📝 Изменён: {f}")

    if last_change_time and (time.time() - last_change_time) >= DEBOUNCE:
        last_change_time = 0
        print("🔄 Перезапускаю бот...")
        kill_bot()
        # Сбрасываем mtimes чтобы не сработало повторно
        time.sleep(2)
        mtimes = {f: get_mtime(f) for f in WATCH_FILES}
        print("✅ Бот перезапущен (restart_bot.bat поднимет его автоматически)\n")
