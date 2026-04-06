# Стабильный запуск на VPS (без зависаний)

Ниже команды для Ubuntu/systemd. Выполнять на сервере под root.

## 1) Установить service-файлы

```bash
cp /opt/bot/deploy/systemd/perfectorganic-bot.service /etc/systemd/system/
cp /opt/bot/deploy/systemd/perfectorganic-dashboard.service /etc/systemd/system/
```

Если репозиторий у тебя не в `/opt/bot`, поправь пути в `WorkingDirectory`, `ExecStart`, `ReadWritePaths`.

## 2) Перечитать systemd и включить автозапуск

```bash
systemctl daemon-reload
systemctl enable perfectorganic-bot
systemctl enable perfectorganic-dashboard
systemctl restart perfectorganic-bot
systemctl restart perfectorganic-dashboard
```

## 3) Проверка статуса и логов

```bash
systemctl status perfectorganic-bot --no-pager -l
systemctl status perfectorganic-dashboard --no-pager -l
journalctl -u perfectorganic-bot -n 80 --no-pager
journalctl -u perfectorganic-dashboard -n 80 --no-pager
```

## 4) Если админка с телефона (без домена)

- Открывай: `http://IP:8080`
- Это будет "небезопасно" (HTTP), но работать будет.
- **Важно:** при доступе по `http://` в юните должно быть `SESSION_COOKIE_SECURE=0`. Если стоит `1`, браузер не сохранит сессию и вход «не работает».
- Для безопасности лучше закрыть доступ по firewall только для своего IP.

Пример (ufw):

```bash
ufw allow from YOUR_IP to any port 8080 proto tcp
ufw deny 8080/tcp
ufw status
```

## 5) Антизависание

- `Restart=always` + `RestartSec=5` автоматически поднимут процесс после падения.
- `StartLimit*` ограничивают "флаппинг", но не блокируют обычные рестарты.
- Логи читать только через `journalctl`, так проще ловить причину падения.

## 6) Дашборд «не открывается» или сразу отваливается

1. **Статус и ошибка Python:**  
   `systemctl status perfectorganic-dashboard --no-pager -l`  
   `journalctl -u perfectorganic-dashboard -n 100 --no-pager`

2. **Порт 8080:**  
   `ss -tlnp | grep 8080` — слушает ли процесс.  
   Если nginx проксирует на 8080, проверь `nginx -t` и логи сайта.

3. **Запись в каталог бота:** в юните должны быть **оба** пути в `ReadWritePaths`:  
   `/opt/dashboard` **и** `/opt/bot/telegram_bot` (иначе сохранение очереди/статистики даёт ошибки или краш).

4. **Вход в админку по HTTPS:** если в юните `SESSION_COOKIE_SECURE=1`, а открываешь по **http://**, cookie сессии не сохранится — «как будто не работает». Либо HTTPS, либо `SESSION_COOKIE_SECURE=0`.

5. **После `git pull`:** синтаксическая ошибка в `app.py` — сервис уйдёт в restart loop; смотри последние строки `journalctl`.
