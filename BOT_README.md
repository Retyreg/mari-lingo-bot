# 🤖 Mari Lingo Bot - Telegram бот для изучения марийского языка

Telegram бот с AI-помощником и RAG базой знаний для изучения марийского языка.

## 🌟 Возможности

✅ **Интерактивный чат-помощник** - отвечает на вопросы о марийском языке
✅ **Карточки слов** - интерактивное изучение новых слов
✅ **Грамматические упражнения** - практика с обратной связью
✅ **Тесты и викторины** - проверка знаний
✅ **Аудио произношение** - правильное произношение слов
✅ **Отслеживание прогресса** - статистика обучения
✅ **RAG система** - использует вашу базу знаний из PDF

## 📋 Требования

- Python 3.9+
- RAG база данных (создана через `pdf_to_rag.py`)
- Telegram Bot Token
- Anthropic API Key

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
# Установите зависимости для бота
pip install -r bot_requirements.txt

# Или используйте conda
conda install -c conda-forge python-telegram-bot anthropic python-dotenv aiohttp
```

### 2. Создание Telegram бота

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Введите название бота: **Mari Lingo Bot**
4. Введите username: `MariLingoBot` (или другой доступный)
5. Скопируйте токен бота

**Дополнительные настройки в BotFather:**

```
/setdescription - Бот для изучения марийского языка
/setabouttext - AI-помощник с базой знаний по марийскому языку
/setuserpic - Загрузите иконку бота
/setcommands - Установите команды (см. ниже)
```

**Команды для бота:**
```
start - Начать работу с ботом
help - Справка по использованию
chat - Режим чата с AI
flashcard - Карточки слов
quiz - Тест знаний
exercise - Грамматические упражнения
progress - Показать прогресс обучения
cancel - Отменить текущее действие
```

### 3. Получение Anthropic API ключа

1. Зайдите на [console.anthropic.com](https://console.anthropic.com/)
2. Создайте аккаунт или войдите
3. Перейдите в раздел **API Keys**
4. Создайте новый ключ
5. Скопируйте ключ

### 4. Настройка конфигурации

```bash
# Скопируйте пример конфигурации
cp .env.example .env

# Отредактируйте .env файл
nano .env
```

Заполните переменные:

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
RAG_DB_PATH=./rag_database
USER_DATA_PATH=./user_data
```

### 5. Убедитесь, что RAG база создана

```bash
# Проверьте, что база существует
ls -la rag_database/

# Если нет - создайте её
python3 pdf_to_rag.py ~/Desktop/1AI/Projects/Mari\ Lingo/PDF/
```

### 6. Запуск бота

```bash
# Запуск бота
python3 mari_lingo_bot.py

# Запуск в фоне (для серверов)
nohup python3 mari_lingo_bot.py > bot.log 2>&1 &

# Просмотр логов
tail -f bot.log
```

## 📱 Использование бота

### Основные команды

- `/start` - Приветствие и главное меню
- `/help` - Справка по командам
- `/chat` - Режим чата с AI
- `/flashcard` - Карточки для изучения слов
- `/quiz` - Тест знаний
- `/exercise` - Грамматические упражнения
- `/progress` - Статистика обучения

### Режимы работы

**💬 Режим чата**
```
Пользователь: Как сказать "привет" на марийском?
Бот: На марийском языке "привет" - "Салам лийже" или 
     просто "Салам". Это распространенное приветствие.
```

**🎴 Карточки слов**
- Бот показывает марийское слово
- Пользователь видит перевод
- Примеры использования в предложениях
- Возможность озвучки

**🎯 Тесты**
- Выбор ответа из вариантов
- Проверка грамматики
- Перевод слов и фраз
- Мгновенная обратная связь

**📊 Прогресс**
- Количество изученных слов
- Точность ответов
- Серия дней обучения
- Пройденные тесты

## 🏗️ Архитектура

```
┌─────────────────┐
│  Telegram Bot   │
└────────┬────────┘
         │
    ┌────▼────────────────────────┐
    │   Mari Lingo Bot Handler    │
    └──┬──────────────────────┬───┘
       │                      │
  ┌────▼─────┐         ┌─────▼──────┐
  │ RAG      │         │  Claude    │
  │ Searcher │         │  API       │
  └──────────┘         └────────────┘
       │
  ┌────▼──────────┐
  │  ChromaDB     │
  │  (База PDF)   │
  └───────────────┘
```

### Компоненты

1. **MariLingoBot** - основной класс бота
2. **RAGSearcher** - поиск по базе знаний
3. **UserProgress** - отслеживание прогресса
4. **Claude API** - генерация ответов

### Поток обработки сообщения

```
Пользователь отправляет вопрос
    ↓
RAG ищет релевантную информацию в PDF
    ↓
Claude генерирует ответ на основе контекста
    ↓
Бот отправляет ответ пользователю
    ↓
Прогресс сохраняется
```

## 📁 Структура данных

### Прогресс пользователя (`user_data/{user_id}.json`)

```json
{
  "user_id": 123456789,
  "started_at": "2024-01-18T10:00:00",
  "total_questions": 50,
  "correct_answers": 42,
  "words_learned": ["салам", "тау", "мемнан"],
  "quiz_history": [...],
  "chat_history": [...],
  "streak_days": 7,
  "last_activity": "2024-01-18T15:30:00"
}
```

## 🔧 Настройка и расширение

### Добавление новых команд

```python
async def my_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Описание команды"""
    await update.message.reply_text("Текст ответа")

# Регистрация в main()
application.add_handler(CommandHandler("mycommand", bot.my_command))
```

### Изменение промптов Claude

Отредактируйте `system_prompt` в методе `handle_chat_message()`:

```python
system_prompt = """Твой персонализированный промпт"""
```

### Настройка RAG поиска

```python
# Изменить количество результатов
rag_results = rag_searcher.search(message, n_results=5)

# Изменить минимальную релевантность
# (добавить фильтрацию в rag_search.py)
```

## 🚀 Деплой на сервер

### VPS (Ubuntu/Debian)

```bash
# 1. Установка зависимостей
sudo apt update
sudo apt install python3-pip

# 2. Клонирование проекта
git clone your-repo
cd mari-lingo-bot

# 3. Установка библиотек
pip3 install -r bot_requirements.txt

# 4. Настройка .env
nano .env

# 5. Запуск как сервис
sudo nano /etc/systemd/system/mari-lingo-bot.service
```

**Содержимое сервиса:**

```ini
[Unit]
Description=Mari Lingo Telegram Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/bot
ExecStart=/usr/bin/python3 mari_lingo_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Запуск сервиса
sudo systemctl enable mari-lingo-bot
sudo systemctl start mari-lingo-bot
sudo systemctl status mari-lingo-bot
```

### Heroku

```bash
# 1. Создайте Procfile
echo "worker: python3 mari_lingo_bot.py" > Procfile

# 2. Создайте runtime.txt
echo "python-3.11" > runtime.txt

# 3. Деплой
heroku create mari-lingo-bot
git push heroku main
heroku config:set TELEGRAM_BOT_TOKEN=your_token
heroku config:set ANTHROPIC_API_KEY=your_key
```

### GitHub Actions (бесплатно)

Создайте `.github/workflows/bot.yml`:

```yaml
name: Mari Lingo Bot

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 */6 * * *'  # Каждые 6 часов

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r bot_requirements.txt
      - run: python3 mari_lingo_bot.py
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## 🔐 Безопасность

- ✅ Никогда не коммитьте `.env` файл
- ✅ Добавьте `.env` в `.gitignore`
- ✅ Храните токены в секретах (GitHub Secrets, Heroku Config)
- ✅ Ограничьте доступ к API ключам
- ✅ Регулярно ротируйте токены

## 📊 Мониторинг

```bash
# Просмотр логов
tail -f bot.log

# Статистика пользователей
ls -la user_data/ | wc -l

# Размер базы данных
du -sh rag_database/
```

## 🐛 Устранение проблем

### Бот не отвечает

```bash
# Проверьте, запущен ли бот
ps aux | grep mari_lingo_bot

# Проверьте логи
tail -n 100 bot.log

# Проверьте токен
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('TELEGRAM_BOT_TOKEN'))"
```

### Ошибки RAG поиска

```bash
# Проверьте базу данных
python3 rag_search.py --stats

# Пересоздайте базу
python3 pdf_to_rag.py ~/Desktop/1AI/Projects/Mari\ Lingo/PDF/
```

### Ошибки Claude API

```bash
# Проверьте ключ
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"

# Проверьте лимиты
# https://console.anthropic.com/settings/limits
```

## 💰 Стоимость

**Anthropic API (Claude):**
- Sonnet 4: ~$3 за 1M входных токенов, ~$15 за 1M выходных
- ~100-300 токенов на запрос
- ~1000 запросов = $0.30-0.60

**Рекомендация:** Начните с лимитом $5-10/месяц

## 📈 Следующие шаги

- [ ] Добавить генерацию аудио (Text-to-Speech)
- [ ] Интеграция с базой данных (PostgreSQL)
- [ ] Расширенные тесты и упражнения
- [ ] Геймификация (достижения, уровни)
- [ ] Мультиязычный интерфейс
- [ ] Веб-панель администратора
- [ ] Экспорт прогресса в PDF

## 🤝 Вклад

Приветствуются предложения и улучшения!

## 📄 Лицензия

MIT License - свободное использование

---

**Создано для изучения марийского языка** 🎓
