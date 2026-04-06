#!/bin/bash
# Запуск на VPS от root: задаёт FLASK_SECRET_KEY, DASHBOARD_PASSWORD, SESSION_COOKIE_SECURE для perfectorganic-dashboard
set -euo pipefail
SVC="${1:-perfectorganic-dashboard}"
DROPIN="/etc/systemd/system/${SVC}.service.d"
CONF="${DROPIN}/override.conf"

if ! command -v openssl >/dev/null 2>&1; then
  echo "Нужен openssl" >&2
  exit 1
fi

SECRET="$(openssl rand -hex 32)"
read -r -p "Пароль входа в дашборд (не отображается): " -s PASS
echo
if [ -z "${PASS}" ]; then
  echo "Пароль не может быть пустым" >&2
  exit 1
fi

mkdir -p "${DROPIN}"
umask 077
cat >"${CONF}" <<EOF
# Создано install_dashboard_env.sh — не коммить в git
[Service]
Environment=FLASK_SECRET_KEY=${SECRET}
Environment=DASHBOARD_PASSWORD=${PASS}
Environment=SESSION_COOKIE_SECURE=0
EOF
chmod 600 "${CONF}"

systemctl daemon-reload
systemctl restart "${SVC}"

echo "OK: ${CONF} записан, сервис ${SVC} перезапущен."
echo "Проверка: systemctl is-active ${SVC}"
systemctl is-active "${SVC}"
