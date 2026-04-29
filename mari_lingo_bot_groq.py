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

from openai import OpenAI
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
from flashcard_system import FlashcardDeck, FlashcardManager, FlashCard as FC, format_flashcard_message, format_session_stats

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-3.5-haiku")
RAG_DB_PATH = os.getenv("RAG_DB_PATH", "./rag_database")
USER_DATA_PATH = "./user_data"

# Инициализация LLM-клиента (OpenRouter, OpenAI-совместимый).
# Плейсхолдер вместо None, чтобы SDK не падал на импорте — отсутствие ключа
# проверяется в main() и приводит к корректному выходу с понятной ошибкой.
llm_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY or "missing-openrouter-key",
)

_OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/Retyreg/mari-lingo-bot",
    "X-Title": "Mari Lingo Bot",
}


def _llm_kwargs() -> Dict:
    """Доп. параметры: заголовки и пиннинг провайдера для llama-моделей."""
    kwargs: Dict = {"extra_headers": _OPENROUTER_HEADERS}
    if LLM_MODEL.startswith("meta-llama/"):
        kwargs["extra_body"] = {"provider": {"order": ["Groq"]}}
    return kwargs


rag_searcher = RAGSearcher(db_path=RAG_DB_PATH)

# Инициализация генератора квизов
quiz_generator = QuizGenerator(rag_searcher, llm_client, model=LLM_MODEL, llm_kwargs=_llm_kwargs())

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
                "gamification": GamificationSystem(user_id, USER_DATA_PATH),
                "flashcard_deck": None,
                "flashcard_session": {"knew": 0, "total": 0}
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

            chat_completion = llm_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=LLM_MODEL,
                temperature=0.7,
                max_tokens=1024,
                **_llm_kwargs(),
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
        
        # Карточки - обработчики
        elif data == "fc_review":
            await self.start_flashcard_session(query, session, mode="review")
        
        elif data == "fc_new":
            await self.start_flashcard_session(query, session, mode="new")
        
        elif data == "fc_categories":
            await self.show_flashcard_categories(query, session)
        
        elif data.startswith("fc_cat_"):
            category = data.replace("fc_cat_", "")
            await self.start_flashcard_session(query, session, mode="mixed", category=category)
        
        elif data == "fc_start":
            await self.start_flashcard_session(query, session, mode="mixed")
        
        elif data == "fc_show":
            await self.show_flashcard_answer(query, session)
        
        elif data == "fc_yes":
            await self.handle_flashcard_answer(query, session, knew=True)
        
        elif data == "fc_no":
            await self.handle_flashcard_answer(query, session, knew=False)
        
        elif data == "fc_stats":
            await self.show_flashcard_stats(query, session)
        
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
        """Запуск режима карточек - главное меню"""
        session["mode"] = "flashcard"
        gamification = session.get("gamification")
        
        # Инициализируем колоду если нет
        if not session.get("flashcard_deck"):
            deck = FlashcardDeck(query.from_user.id, USER_DATA_PATH)
            session["flashcard_deck"] = deck
        else:
            deck = session["flashcard_deck"]
        
        # Инициализируем колоду базовым словарём если пустая
        if len(deck.cards) == 0:
            added = FlashcardManager.initialize_deck(deck)
            init_msg = "\n\n✨ Добавлено " + str(added) + " слов!"
        else:
            init_msg = ""
        
        stats = deck.get_stats()
        
        text = f"""
🎴 **Карточки**

📊 **Твоя колода:**
📖 Всего: {stats['total']}
🆕 Новых: {stats['new']}
📗 Изучаю: {stats['learning']}
⭐ Выучено: {stats['mastered']}
📆 Повторить: {stats['due_today']}{init_msg}

Выбери режим:
"""
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Повторение", callback_data="fc_review"),
                InlineKeyboardButton("🆕 Новые", callback_data="fc_new")
            ],
            [
                InlineKeyboardButton("📚 Категории", callback_data="fc_categories")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="fc_stats"),
                InlineKeyboardButton("🏠 Меню", callback_data="mode_chat")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    
    async def show_flashcard_categories(self, query, session):
        """Показать категории"""
        categories = FlashcardManager.get_categories()
        
        emoji_map = {
            "приветствия": "👋", "семья": "👨‍👩‍👧", "природа": "🌿",
            "еда": "🍞", "дом": "🏠", "цвета": "🎨",
            "животные": "🐾", "числа": "🔢", "глаголы": "🏃"
        }
        
        text = "📚 **Выбери категорию:**"
        
        keyboard = []
        row = []
        for cat in categories:
            emoji = emoji_map.get(cat, "📖")
            row.append(InlineKeyboardButton(f"{emoji} {cat.title()}", callback_data=f"fc_cat_{cat}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="mode_flashcard")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    async def start_flashcard_session(self, query, session, mode: str = "mixed", category: str = None):
        """Начать сессию карточек"""
        deck = session.get("flashcard_deck")
        if not deck:
            deck = FlashcardDeck(query.from_user.id, USER_DATA_PATH)
            session["flashcard_deck"] = deck
        
        # Добавляем слова из категории если указана
        if category:
            words = FlashcardManager.get_words_by_category(category)
            for w in words:
                card = FC(
                    word_mari=w["mari"], word_russian=w["russian"],
                    example_mari=w.get("example_mari", ""),
                    example_russian=w.get("example_russian", ""),
                    category=w.get("category", ""), difficulty=w.get("difficulty", "easy")
                )
                deck.add_card(card)
        
        # Запускаем сессию
        card = deck.start_session(mode=mode, limit=10)
        
        if not card:
            text = "📭 Нет карточек!\n\n"
            if mode == "review":
                text += "Все слова повторены, приходи позже!"
            else:
                text += "Добавь новые слова через категории."
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="mode_flashcard")]])
            )
            return
        
        session["flashcard_session"] = {"knew": 0, "total": len(deck.current_session)}
        await self.show_flashcard(query, session, card, show_answer=False)
    
    async def show_flashcard(self, query, session, card, show_answer: bool = False):
        """Показать карточку"""
        deck = session["flashcard_deck"]
        progress = f"📍 {deck.session_index + 1}/{len(deck.current_session)}"
        
        text = format_flashcard_message(card, show_answer)
        text = progress + "\n" + text
        
        if not show_answer:
            keyboard = [[InlineKeyboardButton("👀 Показать ответ", callback_data="fc_show")]]
        else:
            keyboard = [[
                InlineKeyboardButton("❌ Не знал", callback_data="fc_no"),
                InlineKeyboardButton("✅ Знал", callback_data="fc_yes")
            ]]
        
        keyboard.append([InlineKeyboardButton("🏠 Выйти", callback_data="mode_flashcard")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    async def show_flashcard_answer(self, query, session):
        """Показать ответ"""
        deck = session.get("flashcard_deck")
        card = deck.get_current_card() if deck else None
        
        if card:
            await self.show_flashcard(query, session, card, show_answer=True)
        else:
            await self.finish_flashcard_session(query, session)
    
    async def handle_flashcard_answer(self, query, session, knew: bool):
        """Обработка ответа"""
        deck = session.get("flashcard_deck")
        gamification = session.get("gamification")
        
        deck.answer_current(knew)
        
        if knew:
            session["flashcard_session"]["knew"] += 1
            if gamification:
                gamification.add_xp(5, "flashcard_correct")
        
        if deck.is_session_finished():
            await self.finish_flashcard_session(query, session)
        else:
            card = deck.get_current_card()
            if card:
                await self.show_flashcard(query, session, card, show_answer=False)
            else:
                await self.finish_flashcard_session(query, session)
    
    async def finish_flashcard_session(self, query, session):
        """Завершение сессии"""
        deck = session.get("flashcard_deck")
        gamification = session.get("gamification")
        
        knew = session.get("flashcard_session", {}).get("knew", 0)
        total = session.get("flashcard_session", {}).get("total", 0)
        
        if gamification and total > 0:
            gamification.add_xp(20, "flashcard_session")
            gamification.update_daily_goal("flashcards", total)
            if knew == total and total >= 5:
                gamification.check_achievement("perfect_recall")
        
        text = format_session_stats(deck, knew, total)
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Ещё", callback_data="fc_start"),
                InlineKeyboardButton("📊 Статистика", callback_data="fc_stats")
            ],
            [InlineKeyboardButton("🏠 Меню", callback_data="mode_flashcard")]
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    async def show_flashcard_stats(self, query, session):
        """Статистика карточек"""
        deck = session.get("flashcard_deck")
        if not deck:
            deck = FlashcardDeck(query.from_user.id, USER_DATA_PATH)
            session["flashcard_deck"] = deck
        
        stats = deck.get_stats()
        
        categories_count = {}
        for card in deck.cards.values():
            cat = card.category
            if cat not in categories_count:
                categories_count[cat] = {"total": 0, "mastered": 0}
            categories_count[cat]["total"] += 1
            if card.repetitions >= 5:
                categories_count[cat]["mastered"] += 1
        
        text = f"""
📊 **Статистика карточек**

📖 Всего: {stats['total']}
🆕 Новых: {stats['new']}
📗 Изучаю: {stats['learning']}
⭐ Выучено: {stats['mastered']}
📆 К повторению: {stats['due_today']}

📂 **По категориям:**
"""
        
        emoji_map = {"приветствия": "👋", "семья": "👨‍👩‍👧", "природа": "🌿",
                     "еда": "🍞", "дом": "🏠", "цвета": "🎨",
                     "животные": "🐾", "числа": "🔢", "глаголы": "🏃"}
        
        for cat, c in sorted(categories_count.items()):
            emoji = emoji_map.get(cat, "📖")
            text += emoji + " " + cat + ": " + str(c["mastered"]) + "/" + str(c["total"]) + "\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="mode_flashcard")]]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


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
    
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY не установлен!")
        logger.info("Получите ключ на: https://openrouter.ai/keys")
        return
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    bot = MariLingoBot()
    
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("progress", bot.progress_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    logger.info(f"🚀 Mari Lingo Bot запущен (OpenRouter / {LLM_MODEL} + Gamification)!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
