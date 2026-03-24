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
