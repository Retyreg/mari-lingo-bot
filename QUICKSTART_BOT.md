# 🚀 Быстрый старт - Mari Lingo Bot

## За 5 минут до запуска бота

### Шаг 1: Создайте Telegram бота (2 минуты)

1. Откройте Telegram, найдите [@BotFather](https://t.me/BotFather)
2. Отправьте `/newbot`
3. Введите имя: `Mari Lingo Bot`
4. Введите username: `YourMariLingoBot` (придумайте уникальный)
5. **СКОПИРУЙТЕ ТОКЕН** (выглядит так: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Шаг 2: Получите Claude API ключ (2 минуты)

1. Откройте https://console.anthropic.com/
2. Создайте аккаунт или войдите
3. Раздел **API Keys** → **Create Key**
4. **СКОПИРУЙТЕ КЛЮЧ** (начинается с `sk-ant-api03-...`)

### Шаг 3: Установка и настройка (1 минута)

```bash
# Установите зависимости
pip install -r bot_requirements.txt

# Создайте .env файл
cp .env.example .env

# Откройте .env в редакторе
nano .env
# (или любым текстовым редактором)
```

В файле `.env` вставьте ваши ключи:

```bash
TELEGRAM_BOT_TOKEN=ваш_токен_от_botfather
ANTHROPIC_API_KEY=ваш_ключ_от_anthropic
RAG_DB_PATH=./rag_database
```

Сохраните файл (Ctrl+O, Enter, Ctrl+X в nano)

### Шаг 4: Проверьте RAG базу

```bash
# Проверьте, что база создана
ls -la rag_database/

# Если базы нет - создайте
python3 pdf_to_rag.py ~/Desktop/1AI/Projects/Mari\ Lingo/PDF/
```

### Шаг 5: Запустите бота! 🎉

```bash
python3 mari_lingo_bot.py
```

Вы должны увидеть:
```
🚀 Mari Lingo Bot запущен!
```

### Шаг 6: Протестируйте

1. Откройте Telegram
2. Найдите вашего бота по username
3. Отправьте `/start`
4. Попробуйте задать вопрос о марийском языке!

---

## 🧪 Тестирование без Telegram (опционально)

Перед запуском бота можете протестировать локально:

```bash
# Тест RAG поиска
python3 test_bot.py --query "Как сказать привет на марийском?"

# Интерактивный режим
python3 test_bot.py --interactive
```

---

## ❓ Проблемы?

### "ModuleNotFoundError: No module named 'telegram'"

```bash
pip install python-telegram-bot
```

### "TELEGRAM_BOT_TOKEN не установлен"

Проверьте файл `.env`:
```bash
cat .env
```

Убедитесь, что токен правильный и нет лишних пробелов.

### "База данных не найдена"

```bash
# Создайте RAG базу
python3 pdf_to_rag.py ~/Desktop/1AI/Projects/Mari\ Lingo/PDF/
```

### Бот запустился, но не отвечает

1. Проверьте, что токен правильный
2. Проверьте, что бот НЕ запрещен в Telegram
3. Попробуйте отправить `/start` снова

---

## 📱 Что дальше?

После запуска бота:

1. **Протестируйте все функции:**
   - Задайте вопросы о языке
   - Попробуйте карточки
   - Проверьте прогресс

2. **Настройте под себя:**
   - Измените приветствие в коде
   - Добавьте свои команды
   - Настройте промпты Claude

3. **Деплой на сервер** (для 24/7 работы):
   - См. раздел "Деплой" в BOT_README.md

---

## 💡 Полезные команды

```bash
# Запустить бота
python3 mari_lingo_bot.py

# Запустить в фоне
nohup python3 mari_lingo_bot.py > bot.log 2>&1 &

# Посмотреть логи
tail -f bot.log

# Остановить бота
pkill -f mari_lingo_bot.py

# Обновить зависимости
pip install -r bot_requirements.txt --upgrade
```

---

## 🎯 Быстрые команды бота

В Telegram после `/start`:

- **💬 Чат** - Задавайте любые вопросы
- **🎴 Карточки** - Учите новые слова
- **🎯 Тест** - Проверьте знания
- **📊 Прогресс** - Смотрите статистику

---

**Готово! Ваш бот работает! 🎉**

Полная документация: [BOT_README.md](BOT_README.md)
