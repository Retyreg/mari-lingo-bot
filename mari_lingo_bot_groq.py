"""
Mari Lingo Bot - Telegram бот для изучения марийского языка
Версия с Groq API и системой геймификации
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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

# Импорт компонентов
import sys
sys.path.append('.')
from rag_search import RAGSearcher
from quiz_system import QuizGenerator, QuizSession
from spaced_repetition import SpacedRepetitionSystem, FlashCard
from gamification import GamificationSystem, LEVELS, get_leaderboard, format_leaderboard

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
    
    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Получение постоянной клавиатуры с кнопкой меню"""
        keyboard = [
            [KeyboardButton("📋 Меню")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    def get_session(self, user_id: int) -> Dict:
        """Получение или создание сессии пользователя"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "mode": "chat",
                "quiz_state": None,
                "flashcard_state": None,
                "sr_state": None,
                "progress": UserProgress(user_id),
                "sr_system": SpacedRepetitionSystem(user_id, USER_DATA_PATH),
                "gamification": GamificationSystem(user_id, USER_DATA_PATH)
            }
        return self.user_sessions[user_id]
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        user_id = user.id
        
        session = self.get_session(user_id)
        gamification = session["gamification"]
        
        # Бонус за ежедневный вход
        login_result = gamification.claim_daily_login_bonus()
        level_info = gamification.get_level_info()
        
        welcome_text = f"""
👋 Привет, {user.first_name}!

Я **Mari Lingo Bot** - твой помощник в изучении марийского языка! 🎓

{level_info['emoji']} **Уровень {level_info['level']}:** {level_info['name']}
⭐ **XP:** {level_info['xp']}
🔥 **Серия:** {gamification.data['stats']['current_streak']} дней
"""
        
        if login_result['claimed']:
            welcome_text += f"\n✨ **+{login_result['xp']} XP** за ежедневный вход!"
            
            if login_result.get('streak') and login_result['streak'].get('streak_bonus'):
                bonus = login_result['streak']['streak_bonus']
                welcome_text += f"\n🎁 **+{bonus['xp']} XP** за серию {bonus['days']} дней!"
        
        welcome_text += """

🔹 **Возможности:**
📚 Чат-помощник • 🎴 Карточки • 🎯 Тесты • 📊 Прогресс

**Выбери действие:**
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
                InlineKeyboardButton("📊 Профиль", callback_data="show_progress"),
                InlineKeyboardButton("🏆 Достижения", callback_data="show_achievements")
            ],
            [
                InlineKeyboardButton("📋 Цели дня", callback_data="show_daily_goals"),
                InlineKeyboardButton("🏅 Лидеры", callback_data="show_leaderboard")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            "💡 Нажми «📋 Меню» внизу, чтобы открыть меню в любой момент!",
            reply_markup=self.get_main_keyboard()
        )
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки Меню"""
        await self.show_main_menu_message(update.message)
    
    async def show_main_menu_message(self, message):
        """Показать главное меню (для message)"""
        menu_text = """
📋 **Главное меню**

Выбери действие:
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
                InlineKeyboardButton("📊 Профиль", callback_data="show_progress"),
                InlineKeyboardButton("🏆 Достижения", callback_data="show_achievements")
            ],
            [
                InlineKeyboardButton("📋 Цели дня", callback_data="show_daily_goals"),
                InlineKeyboardButton("🏅 Лидеры", callback_data="show_leaderboard")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(
            menu_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def show_main_menu_query(self, query):
        """Показать главное меню (для callback query)"""
        menu_text = """
📋 **Главное меню**

Выбери действие:
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
                InlineKeyboardButton("📊 Профиль", callback_data="show_progress"),
                InlineKeyboardButton("🏆 Достижения", callback_data="show_achievements")
            ],
            [
                InlineKeyboardButton("📋 Цели дня", callback_data="show_daily_goals"),
                InlineKeyboardButton("🏅 Лидеры", callback_data="show_leaderboard")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            menu_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
📖 **Как использовать бота:**

**Режимы работы:**

💬 **Чат** - задавай любые вопросы о марийском языке
🎴 **Карточки** - учи новые слова с переводом
📝 **Упражнения** - практикуй грамматику
🎯 **Тесты** - проверь свои знания

**Геймификация:**

⭐ **XP** - получай очки за активность
📈 **Уровни** - расти от Новичка до Легенды
🏆 **Достижения** - собирай награды
📋 **Ежедневные цели** - выполняй задания
🔥 **Серии** - занимайся каждый день

**Команды:**
/start - Главное меню
/help - Эта справка
/progress - Твой профиль

⚡ Powered by Groq AI
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def progress_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать прогресс пользователя"""
        user_id = update.effective_user.id
        session = self.get_session(user_id)
        gamification = session["gamification"]
        
        profile_text = gamification.get_profile_summary()
        
        keyboard = [
            [
                InlineKeyboardButton("🏆 Достижения", callback_data="show_achievements"),
                InlineKeyboardButton("📋 Цели дня", callback_data="show_daily_goals")
            ],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            profile_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_id = update.effective_user.id
        user_message = update.message.text
        session = self.get_session(user_id)
        
        # Обработка кнопки "Меню"
        if user_message == "📋 Меню":
            await self.menu_command(update, context)
            return
        
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
        session = self.get_session(user_id)
        gamification = session["gamification"]
        
        await update.message.chat.send_action("typing")
        
        try:
            import io
            import contextlib
            
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                rag_results = rag_searcher.search(message, n_results=3)
            
            context_parts = []
            if rag_results and rag_results.get('documents') and rag_results['documents'][0]:
                for i, (doc, metadata) in enumerate(zip(
                    rag_results['documents'][0],
                    rag_results['metadatas'][0]
                ), 1):
                    context_parts.append(f"[Источник {i} - {metadata['filename']}]:\n{doc[:500]}")
            
            rag_context = "\n\n".join(context_parts) if context_parts else "Контекст не найден в базе знаний."
            
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

            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=1024,
            )
            
            bot_response = chat_completion.choices[0].message.content
            
            # Записываем активность в геймификацию
            gamification.record_chat_question()
            
            await update.message.reply_text(bot_response)
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            
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
        gamification = session["gamification"]
        
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
            profile_text = gamification.get_profile_summary()
            
            keyboard = [
                [
                    InlineKeyboardButton("🏆 Достижения", callback_data="show_achievements"),
                    InlineKeyboardButton("📋 Цели дня", callback_data="show_daily_goals")
                ],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                profile_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        
        elif data == "show_achievements":
            achievements_text = gamification.get_achievements_summary()
            
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                achievements_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        
        elif data == "show_daily_goals":
            goals_text = gamification.get_daily_goals_summary()
            
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                goals_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        
        elif data == "show_leaderboard":
            leaderboard = get_leaderboard(USER_DATA_PATH)
            leaderboard_text = format_leaderboard(leaderboard)
            
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                leaderboard_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        
        elif data == "show_help":
            await query.edit_message_text(
                "📖 Используй команды:\n/start - Меню\n/help - Справка\n/progress - Профиль",
                parse_mode="Markdown"
            )
        
        elif data == "main_menu":
            await self.show_main_menu_query(query)
    
    async def start_flashcard_mode(self, query, session):
        """Запуск режима карточек"""
        session["mode"] = "flashcard"
        gamification = session["gamification"]
        
        try:
            import io
            import contextlib
            
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                rag_results = rag_searcher.search("марийское слово перевод", n_results=1)
            
            if rag_results and rag_results['documents'][0]:
                context = rag_results['documents'][0][0][:300]
                
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
                
                # Записываем в геймификацию
                game_result = gamification.record_flashcard_learned(flashcard_text)
                
                card_message = f"🎴 **Карточка**\n\n{flashcard_text}\n\n⭐ +{game_result['xp_earned']} XP"
                
                if game_result['level_up']:
                    new_level = gamification.data['level']
                    level_info = LEVELS[new_level]
                    card_message += f"\n\n🎉 **Новый уровень!** {level_info['emoji']} {level_info['name']}"
                
                if game_result['new_achievements']:
                    for ach in game_result['new_achievements']:
                        card_message += f"\n🏆 {ach['emoji']} {ach['name']}"
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Следующее слово", callback_data="mode_flashcard")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    card_message,
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
            
            questions = quiz_generator.generate_quiz(num_questions=5, difficulty=difficulty)
            quiz_session = QuizSession(query.from_user.id, questions)
            session["quiz_state"] = quiz_session
            
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
        
        progress = quiz_session.get_progress()
        question_text = f"""
📝 **Вопрос {progress}**

{question['question']}

Выберите правильный ответ:
"""
        
        keyboard = []
        for i, option in enumerate(question['options']):
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
        
        parts = callback_data.split("_", 2)
        if len(parts) < 3:
            return
        
        user_answer = parts[2]
        result = quiz_session.submit_answer(user_answer)
        
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
        
        progress = session["progress"]
        progress.add_question(result['correct'])
        
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
        gamification = session["gamification"]
        
        if not quiz_session:
            await query.edit_message_text("Ошибка: сессия квиза не найдена")
            return
        
        results = quiz_session.get_final_results()
        
        # Записываем в геймификацию
        game_result = gamification.record_quiz_completed(
            correct=results['score'],
            total=results['total']
        )
        
        progress = session["progress"]
        progress.data['quiz_history'].append(results)
        progress.save()
        
        percentage = results['percentage']
        
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

📊 **Результаты:**
✅ Правильно: {results['score']}/{results['total']}
📈 Процент: {percentage:.1f}%
⏱ Время: {results['duration_seconds']} сек

⭐ **+{game_result['xp_earned']} XP**
"""
        
        if game_result['level_up']:
            new_level = game_result['new_level']
            level_info = LEVELS[new_level]
            results_text += f"\n🎉 **НОВЫЙ УРОВЕНЬ!**\n{level_info['emoji']} Уровень {new_level}: {level_info['name']}\n"
        
        if game_result['new_achievements']:
            results_text += "\n🏆 **Новые достижения:**\n"
            for ach in game_result['new_achievements']:
                results_text += f"{ach['emoji']} {ach['name']}\n"
        
        daily = game_result['daily_goals']
        completed_count = sum(1 for g in daily['goals'] if g['completed'])
        results_text += f"\n📋 Цели дня: {completed_count}/{len(daily['goals'])}"
        
        if daily['bonus_awarded']:
            results_text += f" 🎁 +{daily['bonus_xp']} XP бонус!"
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Ещё тест", callback_data="mode_quiz"),
                InlineKeyboardButton("📊 Профиль", callback_data="show_progress")
            ],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            results_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
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
За каждый правильный ответ - XP! ⭐
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
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
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
            "📝 **Режим упражнений**\n\n(Функция в разработке)\n\nПопробуй задать вопрос в режиме чата!",
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
    
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        return
    
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY не установлен!")
        logger.info("Получите бесплатный ключ на: https://console.groq.com/")
        return
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    bot = MariLingoBot()
    
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("progress", bot.progress_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    logger.info("🚀 Mari Lingo Bot запущен (Groq AI + Gamification)!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
