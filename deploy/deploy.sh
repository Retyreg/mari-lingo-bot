#!/usr/bin/env bash
# Деплой Mari Lingo Bot. Запускать НА сервере из-под root:
#   sudo bash deploy/deploy.sh          # из чекаута репозитория
#
# Идемпотентен — можно гонять повторно, в том числе как способ обновиться.
# Ничего не угадывает: путь установки ищет на диске, пользователя сервиса берёт
# по владельцу каталога и останавливается там, где нужно решение человека
# (незаполненный .env, расхождение рабочего дерева с origin/main).
set -euo pipefail

REPO_URL="https://github.com/Retyreg/mari-lingo-bot.git"
DEFAULT_DIR="/home/deploy/apps/mari-lingo-bot"

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[31mОШИБКА: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "нужен root (юнит ставится в /etc/systemd/system)"

# --- 1. Находим существующую установку, а не угадываем путь -----------------
say "Ищу существующую установку"
APP_DIR=""
while IFS= read -r hit; do
  APP_DIR="$(dirname "$hit")"; break
done < <(find /home /opt /srv /root -maxdepth 5 -name mari_lingo_bot_groq.py \
           -not -path '*/.git/*' 2>/dev/null)

if [ -n "$APP_DIR" ]; then
  echo "Найдено: $APP_DIR"
else
  echo "Не найдено — ставлю с нуля в $DEFAULT_DIR"
  APP_DIR="$DEFAULT_DIR"
fi

# Владелец каталога = под кем крутить сервис. Не выдумываем deploy, если там не он.
if [ -d "$APP_DIR" ]; then
  RUN_USER="$(stat -c '%U' "$APP_DIR")"
else
  RUN_USER="deploy"
  id -u "$RUN_USER" >/dev/null 2>&1 || RUN_USER="root"
  install -d -o "$RUN_USER" -g "$RUN_USER" "$(dirname "$APP_DIR")"
fi
RUN_GROUP="$(id -gn "$RUN_USER")"
echo "Сервис будет работать под: $RUN_USER:$RUN_GROUP"

AS_USER=(sudo -u "$RUN_USER")
[ "$RUN_USER" = "root" ] && AS_USER=()

# --- 2. Код ------------------------------------------------------------------
say "Обновляю код до origin/main"
if [ -d "$APP_DIR/.git" ]; then
  "${AS_USER[@]}" git -C "$APP_DIR" fetch origin main
  # ff-only: при расхождении с main упадём громко, а не сделаем merge в проде
  "${AS_USER[@]}" git -C "$APP_DIR" merge --ff-only origin/main \
    || die "рабочее дерево разошлось с origin/main — разберитесь руками, деплой прерван"
else
  "${AS_USER[@]}" git clone "$REPO_URL" "$APP_DIR"
fi
"${AS_USER[@]}" git -C "$APP_DIR" log --oneline -1

# --- 3. Зависимости ----------------------------------------------------------
say "venv и зависимости (chromadb тянет torch, ~2 ГБ — это надолго)"
[ -d "$APP_DIR/venv" ] || "${AS_USER[@]}" python3 -m venv "$APP_DIR/venv"
"${AS_USER[@]}" "$APP_DIR/venv/bin/pip" install -q --upgrade pip
"${AS_USER[@]}" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/bot_requirements.txt"

# --- 4. Секреты --------------------------------------------------------------
say "Проверяю .env"
if [ ! -f "$APP_DIR/.env" ]; then
  "${AS_USER[@]}" cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  die "создан $APP_DIR/.env из примера — впишите TELEGRAM_BOT_TOKEN и OPENROUTER_API_KEY и запустите скрипт снова"
fi
chmod 600 "$APP_DIR/.env"
for var in TELEGRAM_BOT_TOKEN OPENROUTER_API_KEY; do
  val="$(grep -E "^${var}=" "$APP_DIR/.env" | tail -1 | cut -d= -f2-)"
  case "$val" in
    ""|your_*) die "$var не заполнен в $APP_DIR/.env" ;;
    *) echo "$var: задан (${#val} символов)" ;;
  esac
done

# --- 5. Webhook: главный тихий убийца long polling ---------------------------
say "Проверяю webhook (конфликтует с polling — бот молчит при живом процессе)"
TOKEN="$(grep -E '^TELEGRAM_BOT_TOKEN=' "$APP_DIR/.env" | tail -1 | cut -d= -f2-)"
WH="$(curl -sS --max-time 15 "https://api.telegram.org/bot${TOKEN}/getWebhookInfo" || echo '')"
WH_URL="$(printf '%s' "$WH" | grep -oE '"url":"[^"]*"' | cut -d'"' -f4 || true)"
if [ -n "${WH_URL:-}" ]; then
  echo "Висит webhook: $WH_URL — снимаю"
  curl -sS --max-time 15 "https://api.telegram.org/bot${TOKEN}/deleteWebhook" >/dev/null
  echo "Снят."
else
  echo "Webhook не установлен — polling не будет конфликтовать."
fi
# Заодно убеждаемся, что токен вообще живой
printf '%s' "$(curl -sS --max-time 15 "https://api.telegram.org/bot${TOKEN}/getMe")" \
  | grep -q '"ok":true' || die "getMe вернул не ok — токен недействителен"
echo "getMe: ok"

# --- 6. systemd --------------------------------------------------------------
say "Ставлю юнит"
sed -e "s|/home/deploy/apps/mari-lingo-bot|$APP_DIR|g" \
    -e "s|^User=deploy$|User=$RUN_USER|" \
    -e "s|^Group=deploy$|Group=$RUN_GROUP|" \
    "$APP_DIR/deploy/mari-lingo-bot.service" > /etc/systemd/system/mari-lingo-bot.service
systemctl daemon-reload
systemctl enable --now mari-lingo-bot
systemctl restart mari-lingo-bot

# --- 7. Проверка -------------------------------------------------------------
say "Проверяю, что бот действительно поднялся"
for i in $(seq 1 12); do
  sleep 5
  if journalctl -u mari-lingo-bot --since '-2min' --no-pager | grep -q 'Mari Lingo Bot запущен'; then
    echo "Бот стартовал."
    break
  fi
  systemctl is-active --quiet mari-lingo-bot || die "юнит упал: journalctl -u mari-lingo-bot -n 50"
  [ "$i" -eq 12 ] && echo "ВНИМАНИЕ: за 60с не увидел строку старта — смотрите лог ниже"
done

systemctl status mari-lingo-bot --no-pager | head -12
say "Последние логи"
journalctl -u mari-lingo-bot -n 30 --no-pager

say "Готово. Путь: $APP_DIR, пользователь: $RUN_USER"
echo "Следить дальше: journalctl -u mari-lingo-bot -f"
