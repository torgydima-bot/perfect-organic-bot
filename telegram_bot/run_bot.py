"""
Запускает бот + следит за изменениями файлов + автоперезапуск.
Заменяет restart_bot.bat и watcher.bat — достаточно одного окна.
"""
import subprocess
import time
import os
import sys

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
WATCH_FILES = ['bot.py', 'content_plan.py', 'products.py', 'config.py']
DEBOUNCE = 4   # сек ожидания после последнего изменения
CRASH_WAIT = 5 # сек паузы если бот упал сам

bot_process = None


def get_mtime(f):
    path = os.path.join(BOT_DIR, f)
    return os.path.getmtime(path) if os.path.exists(path) else 0


def start_bot():
    global bot_process
    print("\n🚀 Запускаю бот...")
    bot_process = subprocess.Popen(
        [sys.executable, 'bot.py'],
        cwd=BOT_DIR
    )
    print(f"   PID: {bot_process.pid}")


def stop_bot():
    global bot_process
    if bot_process and bot_process.poll() is None:
        print("⛔ Останавливаю бот...")
        bot_process.terminate()
        try:
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bot_process.kill()
    bot_process = None


print("=" * 50)
print("  Perfect Organic Bot — автоперезапуск")
print("  Закрой окно чтобы остановить всё")
print("=" * 50)

mtimes = {f: get_mtime(f) for f in WATCH_FILES}
start_bot()

print(f"\n👀 Слежу за: {', '.join(WATCH_FILES)}")
print("🔄 Автоперезапуск при изменении файлов\n")

last_change = 0

while True:
    time.sleep(1)

    # Если бот упал сам — перезапустить
    if bot_process and bot_process.poll() is not None:
        print(f"⚠️  Бот завершился (код {bot_process.returncode}). Жду {CRASH_WAIT} сек...")
        time.sleep(CRASH_WAIT)
        mtimes = {f: get_mtime(f) for f in WATCH_FILES}
        start_bot()
        last_change = 0
        continue

    # Проверяем изменения файлов
    for f in WATCH_FILES:
        new_mtime = get_mtime(f)
        if new_mtime > mtimes[f]:
            mtimes[f] = new_mtime
            last_change = time.time()
            print(f"📝 Изменён: {f}")

    # После DEBOUNCE секунд без новых изменений — перезапускаем
    if last_change and (time.time() - last_change) >= DEBOUNCE:
        last_change = 0
        stop_bot()
        time.sleep(1)
        # Обновляем mtimes чтобы не сработало повторно
        mtimes = {f: get_mtime(f) for f in WATCH_FILES}
        start_bot()
        print("✅ Бот перезапущен!\n")
