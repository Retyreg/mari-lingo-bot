# 🎓 Mari Lingo Bot

> AI-powered Telegram bot for learning Mari language with RAG knowledge base and interactive quizzes

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-20.0+-blue.svg)](https://python-telegram-bot.org/)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-LLM-green.svg)](https://openrouter.ai/)

Mari Lingo Bot - интеллектуальный Telegram бот для изучения марийского языка.

## 🌟 Возможности

- 🤖 AI Чат-помощник (LLM через OpenRouter)
- 🎯 Интерактивные тесты (5 типов вопросов, 3 уровня сложности)
- 🎴 Карточки слов
- 📊 Отслеживание прогресса

## 🚀 Быстрый старт (локально)
```bash
git clone https://github.com/Retyreg/mari-lingo-bot.git
cd mari-lingo-bot
python3 -m venv venv && source venv/bin/activate
pip install -r bot_requirements.txt
cp .env.example .env
# Отредактируйте .env: TELEGRAM_BOT_TOKEN и OPENROUTER_API_KEY
python3 mari_lingo_bot_groq.py
```

> Установка тянет `sentence-transformers` и, следом, torch (~2 ГБ). Без RAG-базы
> (`rag_database/`, в репозиторий не коммитится) бот стартует в degraded-режиме:
> отвечает и проводит тесты, но без контекста из базы знаний.

## 🖥 Деплой на сервер

`run_polling()` — блокирующий процесс: запуск руками из SSH-сессии переживёт
ровно до её закрытия. Юнит systemd, установка и диагностика — в
[deploy/README.md](deploy/README.md).

## 📖 Документация

- [Быстрый старт](QUICKSTART_BOT.md)
- [Деплой и диагностика](deploy/README.md)
- [Руководство по тестам](QUIZ_GUIDE.md)
- [GROQ_SETUP.md](GROQ_SETUP.md) — устарело, оставлено для истории

## 🔑 API ключи

1. **Telegram**: [@BotFather](https://t.me/BotFather)
2. **OpenRouter**: [openrouter.ai/keys](https://openrouter.ai/keys) — один ключ
   на все модели; какую использовать, задаёт `LLM_MODEL` в `.env`

## 👨‍💻 Автор

**Dmitrij Vatutov**
- GitHub: [@Retyreg](https://github.com/Retyreg)

**Сделано с ❤️ для изучения марийского языка**
