"""
Mari Lingo Bot - Telegram бот для изучения марийского языка
Версия с Groq API (бесплатная модель)
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Импорт RAG компонентов
import sys
sys.path.append('.')
from rag_search import RAGSearcher

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RAG_DB_PATH = os.getenv("RAG_DB_PATH", "./rag_database")
USER_DATA_PATH = "./user_data"

# Инициализация клиентов
groq_client = Groq(api_key=GROQ_API_KEY)
rag_searcher = RAGSearcher(db_path=RAG_DB_PATH)

# Создание директории для данных пользователей
Path(USER_DATA_PATH).mkdir(exist_ok=True)


class UserProgress:
    """Класс для отслеживания прогресса пользователя"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.file_path = Path(USER_DATA_PATH) / f"{user_id}.json"
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Загрузка данных пользователя"""
        if self.file_path.exists():
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "user_id": self.user_id,
            "started_at": datetime.now().isoformat(),
            "total_questions": 0,
            "correct_answers": 0,
            "words_learned": [],
            "quiz_history": [],
            "chat_history": [],
            "current_lesson": None,
            "streak_days": 0,
            "last_activity": datetime.now().isoformat()
        }
    
    def save(self):
        """Сохранение данных пользователя"""
        self.data["last_activity"] = datetime.now().isoformat()
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def add_question(self, correct: bool):
        """Добавление результата вопроса"""
        self.data["total_questions"] += 1
        if correct:
            self.data["correct_answers"] += 1
        self.save()
    
    def add_word(self, word: str):
        """Добавление изученного слова"""
        if word not in self.data["words_learned"]:
            self.data["words_learned"].append(word)
            self.save()
    
    def get_accuracy(self) -> float:
        """Получение точности ответов"""
        if self.data["total_questions"] == 0:
            return 0.0
        return (self.data["correct_answers"] / self.data["total_questions"]) * 100


class MariLingoBot:
    """Основной класс Telegram бота"""
    
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
    
    def get_session(self, user_id: int) -> Dict:
        """Получение или создание сессии пользователя"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "mode": "chat",  # chat, quiz, flashcard
                "quiz_state": None,
                "flashcard_state": None,
                "progress": UserProgress(user_id)
            }
        return self.user_sessions[user_id]
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        user_id = user.id
        
        session = self.get_session(user_id)
        progress = session["progress"]
        
        welcome_text = f"""
👋 Привет, {user.first_name}!

Я **Mari Lingo Bot** - твой помощник в изучении марийского языка! 🎓

🔹 **Что я умею:**

📚 **Чат-помощник** - задавай любые вопросы о марийском языке
🎴 **Карточки** - учи новые слова и фразы
📝 **Упражнения** - практикуй грамматику
🎯 **Тесты** - проверь свои знания
📊 **Прогресс** - отслеживай свои успехи

У меня есть доступ к обширной базе знаний по марийскому языку!

⚡ **Powered by Groq AI** - быстрые и точные ответы

**Начнем?** Выбери действие ниже 👇
"""
        
        keyboard = [
            [
                InlineKeyboardButton("💬 Задать вопрос", callback_data="mode_chat"),
                InlineKeyboardButton("🎴 Карточки", callback_data="mode_flashcard")
            ],
            [
                InlineKeyboardButton("📝 Упражнение", callback_data="mode_exercise"),
                InlineKeyboardButton("🎯 Тест", callback_data="mode_quiz")
            ],
            [
                InlineKeyboardButton("📊 Мой прогресс", callback_data="show_progress"),
                InlineKeyboardButton("ℹ️ Помощь", callback_data="show_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
📖 **Как использовать бота:**

**Режимы работы:**

💬 **/chat** - Режим чата
Задавайте любые вопросы о марийском языке, грамматике, словах, культуре.

🎴 **/flashcard** - Карточки
Учите новые слова с переводом и примерами использования.

📝 **/exercise** - Упражнения
Практикуйте грамматику с интерактивными заданиями.

🎯 **/quiz** - Тесты
Проверьте свои знания викториной.

📊 **/progress** - Прогресс
Посмотрите статистику обучения.

**Команды:**
/start - Начать сначала
/help - Эта справка
/cancel - Отменить текущее действие

**Совет:** Просто пишите вопросы, и я отвечу используя базу знаний!

⚡ Работает на Groq AI (бесплатно и быстро)
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def progress_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать прогресс пользователя"""
        user_id = update.effective_user.id
        session = self.get_session(user_id)
        progress = session["progress"]
        
        accuracy = progress.get_accuracy()
        
        progress_text = f"""
📊 **Твой прогресс обучения**

📅 Начало: {progress.data['started_at'][:10]}
🔥 Дней подряд: {progress.data['streak_days']}

**Статистика:**
✅ Правильных ответов: {progress.data['correct_answers']}
📝 Всего вопросов: {progress.data['total_questions']}
🎯 Точность: {accuracy:.1f}%

📚 Изучено слов: {len(progress.data['words_learned'])}
🎓 Пройдено тестов: {len(progress.data['quiz_history'])}

{"🌟 Отличная работа!" if accuracy > 80 else "💪 Продолжай практиковаться!"}
"""
        await update.message.reply_text(progress_text, parse_mode="Markdown")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_id = update.effective_user.id
        user_message = update.message.text
        session = self.get_session(user_id)
        
        mode = session.get("mode", "chat")
        
        if mode == "chat":
            await self.handle_chat_message(update, context, user_message)
        elif mode == "quiz":
            await self.handle_quiz_answer(update, context, user_message)
        elif mode == "exercise":
            await self.handle_exercise_answer(update, context, user_message)
    
    async def handle_chat_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
        """Обработка сообщения в режиме чата с RAG"""
        user_id = update.effective_user.id
        
        # Показываем индикатор печати
        await update.message.chat.send_action("typing")
        
        # Поиск релевантной информации в RAG базе
        try:
            # Временно отключаем вывод в консоль для RAG поиска
            import io
            import contextlib
            
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                rag_results = rag_searcher.search(message, n_results=3)
            
            # Формирование контекста из RAG
            context_parts = []
            if rag_results and rag_results.get('documents') and rag_results['documents'][0]:
                for i, (doc, metadata) in enumerate(zip(
                    rag_results['documents'][0],
                    rag_results['metadatas'][0]
                ), 1):
                    context_parts.append(f"[Источник {i} - {metadata['filename']}]:\n{doc[:500]}")
            
            rag_context = "\n\n".join(context_parts) if context_parts else "Контекст не найден в базе знаний."
            
            # Запрос к Groq с контекстом
            system_prompt = """Ты - Mari Lingo Bot, помощник по изучению марийского языка.

Используй предоставленный контекст из базы знаний для ответа на вопросы пользователя.

Твои задачи:
- Отвечать точно и информативно о марийском языке
- Объяснять грамматику, слова, произношение
- Приводить примеры использования
- Быть дружелюбным и мотивирующим
- Если в контексте нет ответа, честно скажи об этом

Отвечай на русском языке, используй марийские слова где уместно.
Будь кратким но информативным."""

            user_prompt = f"""Вопрос пользователя: {message}

Контекст из базы знаний:
{rag_context}

Ответь на вопрос, используя контекст."""

            # Используем Groq API
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                model="llama-3.3-70b-versatile",  # Быстрая и качественная модель
                temperature=0.7,
                max_tokens=1024,
            )
            
            bot_response = chat_completion.choices[0].message.content
            
            # Отправка ответа
            await update.message.reply_text(bot_response)
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            
            # Если API не работает, отправляем результаты RAG
            if rag_results and rag_results['documents'][0]:
                fallback_response = "📚 **Информация из базы знаний:**\n\n"
                fallback_response += rag_context[:1000]
                await update.message.reply_text(fallback_response, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    "Извини, произошла ошибка. Попробуй переформулировать вопрос! 🙏"
                )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = self.get_session(user_id)
        
        data = query.data
        
        if data == "mode_chat":
            session["mode"] = "chat"
            await query.edit_message_text(
                "💬 **Режим чата активирован!**\n\nЗадавай любые вопросы о марийском языке! 📚",
                parse_mode="Markdown"
            )
        
        elif data == "mode_flashcard":
            await self.start_flashcard_mode(query, session)
        
        elif data == "mode_quiz":
            await self.start_quiz_mode(query, session)
        
        elif data == "mode_exercise":
            await self.start_exercise_mode(query, session)
        
        elif data == "show_progress":
            progress = session["progress"]
            accuracy = progress.get_accuracy()
            
            progress_text = f"""
📊 **Твой прогресс**

✅ Правильно: {progress.data['correct_answers']}
📝 Всего: {progress.data['total_questions']}
🎯 Точность: {accuracy:.1f}%
📚 Слов изучено: {len(progress.data['words_learned'])}
"""
            await query.edit_message_text(progress_text, parse_mode="Markdown")
        
        elif data == "show_help":
            await query.edit_message_text(
                "📖 Используй команды:\n/chat - Чат\n/flashcard - Карточки\n/quiz - Тест\n/progress - Прогресс",
                parse_mode="Markdown"
            )
    
    async def start_flashcard_mode(self, query, session):
        """Запуск режима карточек"""
        session["mode"] = "flashcard"
        
        try:
            # Получаем случайное слово из RAG базы
            import io
            import contextlib
            
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                rag_results = rag_searcher.search("марийское слово перевод", n_results=1)
            
            if rag_results and rag_results['documents'][0]:
                context = rag_results['documents'][0][0][:300]
                
                # Используем Groq для извлечения слова
                chat_completion = groq_client.chat.completions.create(
                    messages=[{
                        "role": "user",
                        "content": f"Из этого текста найди марийское слово и его перевод на русский. Ответь кратко в формате: Слово | Перевод\n\n{context}"
                    }],
                    model="llama-3.3-70b-versatile",
                    temperature=0.3,
                    max_tokens=100,
                )
                
                flashcard_text = chat_completion.choices[0].message.content
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Следующее слово", callback_data="mode_flashcard")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="mode_chat")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"🎴 **Карточка**\n\n{flashcard_text}",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("Не удалось найти слово. Попробуй позже!")
                
        except Exception as e:
            logger.error(f"Ошибка в режиме карточек: {e}")
            await query.edit_message_text("Произошла ошибка. Попробуй позже!")
    
    async def start_quiz_mode(self, query, session):
        """Запуск режима теста"""
        session["mode"] = "quiz"
        await query.edit_message_text(
            "🎯 **Режим теста активирован!**\n\n(Функция в разработке)\n\nПопробуй задать вопрос в режиме чата!",
            parse_mode="Markdown"
        )
    
    async def start_exercise_mode(self, query, session):
        """Запуск режима упражнений"""
        session["mode"] = "exercise"
        await query.edit_message_text(
            "📝 **Режим упражнений активирован!**\n\n(Функция в разработке)\n\nПопробуй задать вопрос в режиме чата!",
            parse_mode="Markdown"
        )
    
    async def handle_quiz_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str):
        """Обработка ответа в режиме теста"""
        pass
    
    async def handle_exercise_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str):
        """Обработка ответа в упражнении"""
        pass


def main():
    """Запуск бота"""
    
    # Проверка переменных окружения
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY не установлен!")
        logger.info("Получите бесплатный ключ на: https://console.groq.com/")
        return
    
    # Создание приложения
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Создание бота
    bot = MariLingoBot()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("progress", bot.progress_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    # Запуск бота
    logger.info("🚀 Mari Lingo Bot запущен (Groq AI)!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
