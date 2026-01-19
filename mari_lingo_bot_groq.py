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
from quiz_system import QuizGenerator, QuizSession
from spaced_repetition import SpacedRepetitionSystem, FlashCard

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

# Инициализация генератора квизов
quiz_generator = QuizGenerator(rag_searcher, groq_client)

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
                "mode": "chat",  # chat, quiz, flashcard, sr_review
                "quiz_state": None,
                "flashcard_state": None,
                "sr_state": None,  # Состояние SR повторения
                "progress": UserProgress(user_id),
                "sr_system": SpacedRepetitionSystem(user_id, USER_DATA_PATH)  # SR система
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
        
        # Обработчики квизов
        elif data.startswith("quiz_"):
            difficulty = data.replace("quiz_", "")
            await self.start_quiz_session(query, session, difficulty)
        
        elif data.startswith("answer_"):
            await self.handle_quiz_answer_callback(query, session, data)
        
        elif data == "quiz_next":
            await self.show_next_quiz_question(query, session)
        
        elif data == "quiz_finish":
            await self.finish_quiz(query, session)
        
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
    
    async def start_quiz_session(self, query, session, difficulty: str):
        """Начало новой сессии теста"""
        try:
            await query.edit_message_text(
                "⏳ Генерирую вопросы...\n\nПодожди немного!",
                parse_mode="Markdown"
            )
            
            # Генерация вопросов
            questions = quiz_generator.generate_quiz(num_questions=5, difficulty=difficulty)
            
            # Создание сессии квиза
            quiz_session = QuizSession(query.from_user.id, questions)
            session["quiz_state"] = quiz_session
            
            # Показываем первый вопрос
            await self.show_quiz_question(query, session)
            
        except Exception as e:
            logger.error(f"Ошибка создания квиза: {e}")
            await query.edit_message_text(
                "Произошла ошибка при генерации теста. Попробуй еще раз!",
                parse_mode="Markdown"
            )
    
    async def show_quiz_question(self, query, session):
        """Показать текущий вопрос"""
        quiz_session = session.get("quiz_state")
        
        if not quiz_session or quiz_session.is_finished():
            await self.finish_quiz(query, session)
            return
        
        question = quiz_session.get_current_question()
        
        if not question:
            await self.finish_quiz(query, session)
            return
        
        # Формируем текст вопроса
        progress = quiz_session.get_progress()
        question_text = f"""
📝 **Вопрос {progress}**

{question['question']}

Выберите правильный ответ:
"""
        
        # Создаем кнопки с вариантами ответов
        keyboard = []
        for i, option in enumerate(question['options']):
            # Используем эмодзи для обозначения вариантов
            emoji = ['🅰️', '🅱️', '🅲', '🅳'][i]
            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} {option}", 
                    callback_data=f"answer_{i}_{option}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            question_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def handle_quiz_answer_callback(self, query, session, callback_data: str):
        """Обработка ответа на вопрос квиза"""
        quiz_session = session.get("quiz_state")
        
        if not quiz_session:
            await query.edit_message_text("Ошибка: сессия квиза не найдена")
            return
        
        # Извлекаем ответ из callback_data
        parts = callback_data.split("_", 2)
        if len(parts) < 3:
            return
        
        user_answer = parts[2]
        
        # Отправляем ответ
        result = quiz_session.submit_answer(user_answer)
        
        # Формируем сообщение с результатом
        if result['correct']:
            result_emoji = "✅"
            result_text = "**Правильно!**"
        else:
            result_emoji = "❌"
            result_text = f"**Неправильно!**\n\nПравильный ответ: **{result['correct_answer']}**"
        
        feedback_text = f"""
{result_emoji} {result_text}

💡 {result['explanation']}

📊 Счет: {result['score']}/{result['total']}
"""
        
        # Обновляем прогресс пользователя
        progress = session["progress"]
        progress.add_question(result['correct'])
        
        # Кнопка для следующего вопроса или завершения
        if quiz_session.is_finished():
            keyboard = [[InlineKeyboardButton("📊 Показать результаты", callback_data="quiz_finish")]]
        else:
            keyboard = [[InlineKeyboardButton("➡️ Следующий вопрос", callback_data="quiz_next")]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            feedback_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def show_next_quiz_question(self, query, session):
        """Показать следующий вопрос"""
        await self.show_quiz_question(query, session)
    
    async def finish_quiz(self, query, session):
        """Завершение квиза и показ результатов"""
        quiz_session = session.get("quiz_state")
        
        if not quiz_session:
            await query.edit_message_text("Ошибка: сессия квиза не найдена")
            return
        
        # Получаем итоговые результаты
        results = quiz_session.get_final_results()
        
        # Сохраняем в историю пользователя
        progress = session["progress"]
        progress.data['quiz_history'].append(results)
        progress.save()
        
        # Формируем итоговое сообщение
        percentage = results['percentage']
        
        # Выбираем эмодзи в зависимости от результата
        if percentage >= 90:
            emoji = "🌟"
        elif percentage >= 70:
            emoji = "👍"
        elif percentage >= 50:
            emoji = "💪"
        else:
            emoji = "📚"
        
        results_text = f"""
{emoji} **Тест завершен!**

📊 **Ваши результаты:**

✅ Правильных ответов: {results['score']}/{results['total']}
📈 Процент: {percentage:.1f}%
⏱ Время: {results['duration_seconds']} сек

{results['level']}

{'🏆 Отличная работа! Продолжай в том же духе!' if percentage >= 80 else '💪 Хорошая попытка! Продолжай практиковаться!'}
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Пройти еще раз", callback_data="mode_quiz"),
                InlineKeyboardButton("📊 Мой прогресс", callback_data="show_progress")
            ],
            [
                InlineKeyboardButton("🏠 Главное меню", callback_data="mode_chat")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            results_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # Очищаем состояние квиза
        session["quiz_state"] = None
        session["mode"] = "chat"
    
    async def start_quiz_mode(self, query, session):
        """Запуск режима теста - выбор сложности"""
        session["mode"] = "quiz"
        
        quiz_text = """
🎯 **Режим теста**

Выберите уровень сложности:

📗 **Легкий** - базовые слова и фразы
📘 **Средний** - обычная лексика и грамматика
📕 **Сложный** - продвинутые темы

Каждый тест содержит 5 вопросов.
За каждый правильный ответ - 1 балл! 🌟
"""
        
        keyboard = [
            [
                InlineKeyboardButton("📗 Легкий", callback_data="quiz_easy"),
                InlineKeyboardButton("📘 Средний", callback_data="quiz_medium"),
            ],
            [
                InlineKeyboardButton("📕 Сложный", callback_data="quiz_hard"),
            ],
            [
                InlineKeyboardButton("🏠 Главное меню", callback_data="mode_chat")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            quiz_text,
            reply_markup=reply_markup,
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
