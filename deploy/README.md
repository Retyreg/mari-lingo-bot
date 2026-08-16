# Деплой Mari Lingo Bot

Бот работает через **long polling** (`application.run_polling()`) — это
блокирующий процесс. Запуск руками из SSH-сессии означает, что бот умрёт
вместе с сессией, при падении и при перезагрузке сервера, ничего никому не
сказав. Поэтому единственный поддерживаемый способ — systemd-юнит.

## Установка

Путь и владелец в юните — `/home/deploy/apps/mari-lingo-bot`, `User=deploy`.
Если у вас другие — поправьте `mari-lingo-bot.service` перед копированием.

```bash
# 1. Код и venv (под тем же пользователем, что и в юните)
sudo -u deploy git clone https://github.com/Retyreg/mari-lingo-bot.git \
  /home/deploy/apps/mari-lingo-bot
cd /home/deploy/apps/mari-lingo-bot
sudo -u deploy python3 -m venv venv
sudo -u deploy venv/bin/pip install -r bot_requirements.txt

# 2. Секреты
sudo -u deploy cp .env.example .env
sudo -u deploy nano .env          # TELEGRAM_BOT_TOKEN + OPENROUTER_API_KEY
sudo -u deploy chmod 600 .env

# 3. Юнит
cp deploy/mari-lingo-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mari-lingo-bot
systemctl status mari-lingo-bot --no-pager
```

> `EnvironmentFile` systemd парсит сам, без кавычек и подстановок shell —
> формат `.env.example` (`KEY=value`, без пробелов вокруг `=`) ему подходит.
> `load_dotenv()` в коде остаётся для локального запуска.

## Обновление

```bash
cd /home/deploy/apps/mari-lingo-bot
sudo -u deploy git fetch origin main
sudo -u deploy git merge --ff-only origin/main
sudo -u deploy venv/bin/pip install -r bot_requirements.txt
systemctl restart mari-lingo-bot
```

`fetch` + `merge --ff-only` вместо `git pull`: при расхождении с `main` merge
упадёт громко, а не сделает молча merge-коммит в проде. `sudo -u deploy` —
чтобы git из-под root не оставлял root-owned файлы в рабочем дереве.

## Диагностика

```bash
systemctl status mari-lingo-bot --no-pager
journalctl -u mari-lingo-bot -n 100 --no-pager
journalctl -u mari-lingo-bot -f
```

Что искать в логах при «бот не отвечает»:

| Строка в логе | Причина |
|---|---|
| `TELEGRAM_BOT_TOKEN не установлен!` | нет `.env` или пустая переменная |
| `OPENROUTER_API_KEY не установлен!` | то же для ключа LLM |
| `Conflict: terminated by other getUpdates` | запущено два экземпляра бота |
| `RAG база не найдена` / `RAG-зависимости не установлены` | degraded-режим, бот **работает**, но без контекста базы знаний |

Проверка со стороны Telegram (токен из `.env`):

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getMe"
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

`getWebhookInfo` важен: если на боте висит webhook, `run_polling()` конфликтует
с ним и не получает ни одного апдейта — бот молчит при живом процессе.
Лечится `curl -s "https://api.telegram.org/bot<TOKEN>/deleteWebhook"`.
