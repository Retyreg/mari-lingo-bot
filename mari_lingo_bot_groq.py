"""
Mari Lingo Bot - Telegram Ð±Ð¾Ñ‚ Ð´Ð»Ñ Ð¸Ð·ÑƒÑ‡ÐµÐ½Ð¸Ñ Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¾Ð³Ð¾ ÑÐ·Ñ‹ÐºÐ°
Ð’ÐµÑ€ÑÐ¸Ñ Ñ Groq API (Ð±ÐµÑÐ¿Ð»Ð°Ñ‚Ð½Ð°Ñ Ð¼Ð¾Ð´ÐµÐ»ÑŒ)
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

# Ð—Ð°Ð³Ñ€ÑƒÐ·ÐºÐ° Ð¿ÐµÑ€ÐµÐ¼ÐµÐ½Ð½Ñ‹Ñ… Ð¾ÐºÑ€ÑƒÐ¶ÐµÐ½Ð¸Ñ
load_dotenv()

# Ð˜Ð¼Ð¿Ð¾Ñ€Ñ‚ RAG ÐºÐ¾Ð¼Ð¿Ð¾Ð½ÐµÐ½Ñ‚Ð¾Ð²
import sys
sys.path.append('.')
from rag_search import RAGSearcher
from quiz_system import QuizGenerator, QuizSession
from spaced_repetition import SpacedRepetitionSystem, FlashCard

# ÐÐ°ÑÑ‚Ñ€Ð¾Ð¹ÐºÐ° Ð»Ð¾Ð³Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¸Ñ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ÐšÐ¾Ð½Ñ„Ð¸Ð³ÑƒÑ€Ð°Ñ†Ð¸Ñ
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RAG_DB_PATH = os.getenv("RAG_DB_PATH", "./rag_database")
USER_DATA_PATH = "./user_data"

# Ð˜Ð½Ð¸Ñ†Ð¸Ð°Ð»Ð¸Ð·Ð°Ñ†Ð¸Ñ ÐºÐ»Ð¸ÐµÐ½Ñ‚Ð¾Ð²
groq_client = Groq(api_key=GROQ_API_KEY)
rag_searcher = RAGSearcher(db_path=RAG_DB_PATH)

# Ð˜Ð½Ð¸Ñ†Ð¸Ð°Ð»Ð¸Ð·Ð°Ñ†Ð¸Ñ Ð³ÐµÐ½ÐµÑ€Ð°Ñ‚Ð¾Ñ€Ð° ÐºÐ²Ð¸Ð·Ð¾Ð²
quiz_generator = QuizGenerator(rag_searcher, groq_client)

# Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð´Ð¸Ñ€ÐµÐºÑ‚Ð¾Ñ€Ð¸Ð¸ Ð´Ð»Ñ Ð´Ð°Ð½Ð½Ñ‹Ñ… Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»ÐµÐ¹
Path(USER_DATA_PATH).mkdir(exist_ok=True)


class UserProgress:
    """ÐšÐ»Ð°ÑÑ Ð´Ð»Ñ Ð¾Ñ‚ÑÐ»ÐµÐ¶Ð¸Ð²Ð°Ð½Ð¸Ñ Ð¿Ñ€Ð¾Ð³Ñ€ÐµÑÑÐ° Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.file_path = Path(USER_DATA_PATH) / f"{user_id}.json"
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Ð—Ð°Ð³Ñ€ÑƒÐ·ÐºÐ° Ð´Ð°Ð½Ð½Ñ‹Ñ… Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ"""
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
        """Ð¡Ð¾Ñ…Ñ€Ð°Ð½ÐµÐ½Ð¸Ðµ Ð´Ð°Ð½Ð½Ñ‹Ñ… Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ"""
        self.data["last_activity"] = datetime.now().isoformat()
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def add_question(self, correct: bool):
        """Ð”Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¸Ðµ Ñ€ÐµÐ·ÑƒÐ»ÑŒÑ‚Ð°Ñ‚Ð° Ð²Ð¾Ð¿Ñ€Ð¾ÑÐ°"""
        self.data["total_questions"] += 1
        if correct:
            self.data["correct_answers"] += 1
        self.save()
    
    def add_word(self, word: str):
        """Ð”Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¸Ðµ Ð¸Ð·ÑƒÑ‡ÐµÐ½Ð½Ð¾Ð³Ð¾ ÑÐ»Ð¾Ð²Ð°"""
        if word not in self.data["words_learned"]:
            self.data["words_learned"].append(word)
            self.save()
    
    def get_accuracy(self) -> float:
        """ÐŸÐ¾Ð»ÑƒÑ‡ÐµÐ½Ð¸Ðµ Ñ‚Ð¾Ñ‡Ð½Ð¾ÑÑ‚Ð¸ Ð¾Ñ‚Ð²ÐµÑ‚Ð¾Ð²"""
        if self.data["total_questions"] == 0:
            return 0.0
        return (self.data["correct_answers"] / self.data["total_questions"]) * 100


class MariLingoBot:
    """ÐžÑÐ½Ð¾Ð²Ð½Ð¾Ð¹ ÐºÐ»Ð°ÑÑ Telegram Ð±Ð¾Ñ‚Ð°"""
    
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
    
    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Получение постоянной клавиатуры с кнопкой меню"""
        keyboard = [
            [KeyboardButton("📋 Меню")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    def get_session(self, user_id: int) -> Dict:
        """ÐŸÐ¾Ð»ÑƒÑ‡ÐµÐ½Ð¸Ðµ Ð¸Ð»Ð¸ ÑÐ¾Ð·Ð´Ð°Ð½Ð¸Ðµ ÑÐµÑÑÐ¸Ð¸ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "mode": "chat",  # chat, quiz, flashcard, sr_review
                "quiz_state": None,
                "flashcard_state": None,
                "sr_state": None,  # Ð¡Ð¾ÑÑ‚Ð¾ÑÐ½Ð¸Ðµ SR Ð¿Ð¾Ð²Ñ‚Ð¾Ñ€ÐµÐ½Ð¸Ñ
                "progress": UserProgress(user_id),
                "sr_system": SpacedRepetitionSystem(user_id, USER_DATA_PATH)  # SR ÑÐ¸ÑÑ‚ÐµÐ¼Ð°
            }
        return self.user_sessions[user_id]
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚Ñ‡Ð¸Ðº ÐºÐ¾Ð¼Ð°Ð½Ð´Ñ‹ /start"""
        user = update.effective_user
        user_id = user.id
        
        session = self.get_session(user_id)
        progress = session["progress"]
        
        welcome_text = f"""
ðŸ‘‹ ÐŸÑ€Ð¸Ð²ÐµÑ‚, {user.first_name}!

Ð¯ **Mari Lingo Bot** - Ñ‚Ð²Ð¾Ð¹ Ð¿Ð¾Ð¼Ð¾Ñ‰Ð½Ð¸Ðº Ð² Ð¸Ð·ÑƒÑ‡ÐµÐ½Ð¸Ð¸ Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¾Ð³Ð¾ ÑÐ·Ñ‹ÐºÐ°! ðŸŽ“

ðŸ”¹ **Ð§Ñ‚Ð¾ Ñ ÑƒÐ¼ÐµÑŽ:**

ðŸ“š **Ð§Ð°Ñ‚-Ð¿Ð¾Ð¼Ð¾Ñ‰Ð½Ð¸Ðº** - Ð·Ð°Ð´Ð°Ð²Ð°Ð¹ Ð»ÑŽÐ±Ñ‹Ðµ Ð²Ð¾Ð¿Ñ€Ð¾ÑÑ‹ Ð¾ Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¾Ð¼ ÑÐ·Ñ‹ÐºÐµ
ðŸŽ´ **ÐšÐ°Ñ€Ñ‚Ð¾Ñ‡ÐºÐ¸** - ÑƒÑ‡Ð¸ Ð½Ð¾Ð²Ñ‹Ðµ ÑÐ»Ð¾Ð²Ð° Ð¸ Ñ„Ñ€Ð°Ð·Ñ‹
ðŸ“ **Ð£Ð¿Ñ€Ð°Ð¶Ð½ÐµÐ½Ð¸Ñ** - Ð¿Ñ€Ð°ÐºÑ‚Ð¸ÐºÑƒÐ¹ Ð³Ñ€Ð°Ð¼Ð¼Ð°Ñ‚Ð¸ÐºÑƒ
ðŸŽ¯ **Ð¢ÐµÑÑ‚Ñ‹** - Ð¿Ñ€Ð¾Ð²ÐµÑ€ÑŒ ÑÐ²Ð¾Ð¸ Ð·Ð½Ð°Ð½Ð¸Ñ
ðŸ“Š **ÐŸÑ€Ð¾Ð³Ñ€ÐµÑÑ** - Ð¾Ñ‚ÑÐ»ÐµÐ¶Ð¸Ð²Ð°Ð¹ ÑÐ²Ð¾Ð¸ ÑƒÑÐ¿ÐµÑ…Ð¸

Ð£ Ð¼ÐµÐ½Ñ ÐµÑÑ‚ÑŒ Ð´Ð¾ÑÑ‚ÑƒÐ¿ Ðº Ð¾Ð±ÑˆÐ¸Ñ€Ð½Ð¾Ð¹ Ð±Ð°Ð·Ðµ Ð·Ð½Ð°Ð½Ð¸Ð¹ Ð¿Ð¾ Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¾Ð¼Ñƒ ÑÐ·Ñ‹ÐºÑƒ!

âš¡ **Powered by Groq AI** - Ð±Ñ‹ÑÑ‚Ñ€Ñ‹Ðµ Ð¸ Ñ‚Ð¾Ñ‡Ð½Ñ‹Ðµ Ð¾Ñ‚Ð²ÐµÑ‚Ñ‹

**ÐÐ°Ñ‡Ð½ÐµÐ¼?** Ð’Ñ‹Ð±ÐµÑ€Ð¸ Ð´ÐµÐ¹ÑÑ‚Ð²Ð¸Ðµ Ð½Ð¸Ð¶Ðµ ðŸ‘‡
"""
        
        keyboard = [
            [
                InlineKeyboardButton("ðŸ’¬ Ð—Ð°Ð´Ð°Ñ‚ÑŒ Ð²Ð¾Ð¿Ñ€Ð¾Ñ", callback_data="mode_chat"),
                InlineKeyboardButton("ðŸŽ´ ÐšÐ°Ñ€Ñ‚Ð¾Ñ‡ÐºÐ¸", callback_data="mode_flashcard")
            ],
            [
                InlineKeyboardButton("ðŸ“ Ð£Ð¿Ñ€Ð°Ð¶Ð½ÐµÐ½Ð¸Ðµ", callback_data="mode_exercise"),
                InlineKeyboardButton("ðŸŽ¯ Ð¢ÐµÑÑ‚", callback_data="mode_quiz")
            ],
            [
                InlineKeyboardButton("ðŸ“Š ÐœÐ¾Ð¹ Ð¿Ñ€Ð¾Ð³Ñ€ÐµÑÑ", callback_data="show_progress"),
                InlineKeyboardButton("â„¹ï¸ ÐŸÐ¾Ð¼Ð¾Ñ‰ÑŒ", callback_data="show_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем приветствие с inline-кнопками
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # Устанавливаем постоянную клавиатуру с кнопкой "Меню"
        await update.message.reply_text(
            "💡 Нажми кнопку «📋 Меню» внизу, чтобы открыть меню в любой момент!",
            reply_markup=self.get_main_keyboard()
        )
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки Меню"""
        user = update.effective_user
        user_id = user.id
        
        session = self.get_session(user_id)
        
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
                InlineKeyboardButton("📊 Мой прогресс", callback_data="show_progress"),
                InlineKeyboardButton("ℹ️ Помощь", callback_data="show_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            menu_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
ðŸ“– **ÐšÐ°Ðº Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÑŒ Ð±Ð¾Ñ‚Ð°:**

**Ð ÐµÐ¶Ð¸Ð¼Ñ‹ Ñ€Ð°Ð±Ð¾Ñ‚Ñ‹:**

ðŸ’¬ **/chat** - Ð ÐµÐ¶Ð¸Ð¼ Ñ‡Ð°Ñ‚Ð°
Ð—Ð°Ð´Ð°Ð²Ð°Ð¹Ñ‚Ðµ Ð»ÑŽÐ±Ñ‹Ðµ Ð²Ð¾Ð¿Ñ€Ð¾ÑÑ‹ Ð¾ Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¾Ð¼ ÑÐ·Ñ‹ÐºÐµ, Ð³Ñ€Ð°Ð¼Ð¼Ð°Ñ‚Ð¸ÐºÐµ, ÑÐ»Ð¾Ð²Ð°Ñ…, ÐºÑƒÐ»ÑŒÑ‚ÑƒÑ€Ðµ.

ðŸŽ´ **/flashcard** - ÐšÐ°Ñ€Ñ‚Ð¾Ñ‡ÐºÐ¸
Ð£Ñ‡Ð¸Ñ‚Ðµ Ð½Ð¾Ð²Ñ‹Ðµ ÑÐ»Ð¾Ð²Ð° Ñ Ð¿ÐµÑ€ÐµÐ²Ð¾Ð´Ð¾Ð¼ Ð¸ Ð¿Ñ€Ð¸Ð¼ÐµÑ€Ð°Ð¼Ð¸ Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ð½Ð¸Ñ.

ðŸ“ **/exercise** - Ð£Ð¿Ñ€Ð°Ð¶Ð½ÐµÐ½Ð¸Ñ
ÐŸÑ€Ð°ÐºÑ‚Ð¸ÐºÑƒÐ¹Ñ‚Ðµ Ð³Ñ€Ð°Ð¼Ð¼Ð°Ñ‚Ð¸ÐºÑƒ Ñ Ð¸Ð½Ñ‚ÐµÑ€Ð°ÐºÑ‚Ð¸Ð²Ð½Ñ‹Ð¼Ð¸ Ð·Ð°Ð´Ð°Ð½Ð¸ÑÐ¼Ð¸.

ðŸŽ¯ **/quiz** - Ð¢ÐµÑÑ‚Ñ‹
ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒÑ‚Ðµ ÑÐ²Ð¾Ð¸ Ð·Ð½Ð°Ð½Ð¸Ñ Ð²Ð¸ÐºÑ‚Ð¾Ñ€Ð¸Ð½Ð¾Ð¹.

ðŸ“Š **/progress** - ÐŸÑ€Ð¾Ð³Ñ€ÐµÑÑ
ÐŸÐ¾ÑÐ¼Ð¾Ñ‚Ñ€Ð¸Ñ‚Ðµ ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÑƒ Ð¾Ð±ÑƒÑ‡ÐµÐ½Ð¸Ñ.

**ÐšÐ¾Ð¼Ð°Ð½Ð´Ñ‹:**
/start - ÐÐ°Ñ‡Ð°Ñ‚ÑŒ ÑÐ½Ð°Ñ‡Ð°Ð»Ð°
/help - Ð­Ñ‚Ð° ÑÐ¿Ñ€Ð°Ð²ÐºÐ°
/cancel - ÐžÑ‚Ð¼ÐµÐ½Ð¸Ñ‚ÑŒ Ñ‚ÐµÐºÑƒÑ‰ÐµÐµ Ð´ÐµÐ¹ÑÑ‚Ð²Ð¸Ðµ

**Ð¡Ð¾Ð²ÐµÑ‚:** ÐŸÑ€Ð¾ÑÑ‚Ð¾ Ð¿Ð¸ÑˆÐ¸Ñ‚Ðµ Ð²Ð¾Ð¿Ñ€Ð¾ÑÑ‹, Ð¸ Ñ Ð¾Ñ‚Ð²ÐµÑ‡Ñƒ Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÑ Ð±Ð°Ð·Ñƒ Ð·Ð½Ð°Ð½Ð¸Ð¹!

âš¡ Ð Ð°Ð±Ð¾Ñ‚Ð°ÐµÑ‚ Ð½Ð° Groq AI (Ð±ÐµÑÐ¿Ð»Ð°Ñ‚Ð½Ð¾ Ð¸ Ð±Ñ‹ÑÑ‚Ñ€Ð¾)
"""
        await update.message.reply_text(help_text, parse_mode="Markdown")
    
    async def progress_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ÐŸÐ¾ÐºÐ°Ð·Ð°Ñ‚ÑŒ Ð¿Ñ€Ð¾Ð³Ñ€ÐµÑÑ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ"""
        user_id = update.effective_user.id
        session = self.get_session(user_id)
        progress = session["progress"]
        
        accuracy = progress.get_accuracy()
        
        progress_text = f"""
ðŸ“Š **Ð¢Ð²Ð¾Ð¹ Ð¿Ñ€Ð¾Ð³Ñ€ÐµÑÑ Ð¾Ð±ÑƒÑ‡ÐµÐ½Ð¸Ñ**

ðŸ“… ÐÐ°Ñ‡Ð°Ð»Ð¾: {progress.data['started_at'][:10]}
ðŸ”¥ Ð”Ð½ÐµÐ¹ Ð¿Ð¾Ð´Ñ€ÑÐ´: {progress.data['streak_days']}

**Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°:**
âœ… ÐŸÑ€Ð°Ð²Ð¸Ð»ÑŒÐ½Ñ‹Ñ… Ð¾Ñ‚Ð²ÐµÑ‚Ð¾Ð²: {progress.data['correct_answers']}
ðŸ“ Ð’ÑÐµÐ³Ð¾ Ð²Ð¾Ð¿Ñ€Ð¾ÑÐ¾Ð²: {progress.data['total_questions']}
ðŸŽ¯ Ð¢Ð¾Ñ‡Ð½Ð¾ÑÑ‚ÑŒ: {accuracy:.1f}%

ðŸ“š Ð˜Ð·ÑƒÑ‡ÐµÐ½Ð¾ ÑÐ»Ð¾Ð²: {len(progress.data['words_learned'])}
ðŸŽ“ ÐŸÑ€Ð¾Ð¹Ð´ÐµÐ½Ð¾ Ñ‚ÐµÑÑ‚Ð¾Ð²: {len(progress.data['quiz_history'])}

{"ðŸŒŸ ÐžÑ‚Ð»Ð¸Ñ‡Ð½Ð°Ñ Ñ€Ð°Ð±Ð¾Ñ‚Ð°!" if accuracy > 80 else "ðŸ’ª ÐŸÑ€Ð¾Ð´Ð¾Ð»Ð¶Ð°Ð¹ Ð¿Ñ€Ð°ÐºÑ‚Ð¸ÐºÐ¾Ð²Ð°Ñ‚ÑŒÑÑ!"}
"""
        await update.message.reply_text(progress_text, parse_mode="Markdown")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚Ñ‡Ð¸Ðº Ñ‚ÐµÐºÑÑ‚Ð¾Ð²Ñ‹Ñ… ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ð¹"""
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
        """ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚ÐºÐ° ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ñ Ð² Ñ€ÐµÐ¶Ð¸Ð¼Ðµ Ñ‡Ð°Ñ‚Ð° Ñ RAG"""
        user_id = update.effective_user.id
        
        # ÐŸÐ¾ÐºÐ°Ð·Ñ‹Ð²Ð°ÐµÐ¼ Ð¸Ð½Ð´Ð¸ÐºÐ°Ñ‚Ð¾Ñ€ Ð¿ÐµÑ‡Ð°Ñ‚Ð¸
        await update.message.chat.send_action("typing")
        
        # ÐŸÐ¾Ð¸ÑÐº Ñ€ÐµÐ»ÐµÐ²Ð°Ð½Ñ‚Ð½Ð¾Ð¹ Ð¸Ð½Ñ„Ð¾Ñ€Ð¼Ð°Ñ†Ð¸Ð¸ Ð² RAG Ð±Ð°Ð·Ðµ
        try:
            # Ð’Ñ€ÐµÐ¼ÐµÐ½Ð½Ð¾ Ð¾Ñ‚ÐºÐ»ÑŽÑ‡Ð°ÐµÐ¼ Ð²Ñ‹Ð²Ð¾Ð´ Ð² ÐºÐ¾Ð½ÑÐ¾Ð»ÑŒ Ð´Ð»Ñ RAG Ð¿Ð¾Ð¸ÑÐºÐ°
            import io
            import contextlib
            
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                rag_results = rag_searcher.search(message, n_results=3)
            
            # Ð¤Ð¾Ñ€Ð¼Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¸Ðµ ÐºÐ¾Ð½Ñ‚ÐµÐºÑÑ‚Ð° Ð¸Ð· RAG
            context_parts = []
            if rag_results and rag_results.get('documents') and rag_results['documents'][0]:
                for i, (doc, metadata) in enumerate(zip(
                    rag_results['documents'][0],
                    rag_results['metadatas'][0]
                ), 1):
                    context_parts.append(f"[Ð˜ÑÑ‚Ð¾Ñ‡Ð½Ð¸Ðº {i} - {metadata['filename']}]:\n{doc[:500]}")
            
            rag_context = "\n\n".join(context_parts) if context_parts else "ÐšÐ¾Ð½Ñ‚ÐµÐºÑÑ‚ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½ Ð² Ð±Ð°Ð·Ðµ Ð·Ð½Ð°Ð½Ð¸Ð¹."
            
            # Ð—Ð°Ð¿Ñ€Ð¾Ñ Ðº Groq Ñ ÐºÐ¾Ð½Ñ‚ÐµÐºÑÑ‚Ð¾Ð¼
            system_prompt = """Ð¢Ñ‹ - Mari Lingo Bot, Ð¿Ð¾Ð¼Ð¾Ñ‰Ð½Ð¸Ðº Ð¿Ð¾ Ð¸Ð·ÑƒÑ‡ÐµÐ½Ð¸ÑŽ Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¾Ð³Ð¾ ÑÐ·Ñ‹ÐºÐ°.

Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐ¹ Ð¿Ñ€ÐµÐ´Ð¾ÑÑ‚Ð°Ð²Ð»ÐµÐ½Ð½Ñ‹Ð¹ ÐºÐ¾Ð½Ñ‚ÐµÐºÑÑ‚ Ð¸Ð· Ð±Ð°Ð·Ñ‹ Ð·Ð½Ð°Ð½Ð¸Ð¹ Ð´Ð»Ñ Ð¾Ñ‚Ð²ÐµÑ‚Ð° Ð½Ð° Ð²Ð¾Ð¿Ñ€Ð¾ÑÑ‹ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ.

Ð¢Ð²Ð¾Ð¸ Ð·Ð°Ð´Ð°Ñ‡Ð¸:
- ÐžÑ‚Ð²ÐµÑ‡Ð°Ñ‚ÑŒ Ñ‚Ð¾Ñ‡Ð½Ð¾ Ð¸ Ð¸Ð½Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚Ð¸Ð²Ð½Ð¾ Ð¾ Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¾Ð¼ ÑÐ·Ñ‹ÐºÐµ
- ÐžÐ±ÑŠÑÑÐ½ÑÑ‚ÑŒ Ð³Ñ€Ð°Ð¼Ð¼Ð°Ñ‚Ð¸ÐºÑƒ, ÑÐ»Ð¾Ð²Ð°, Ð¿Ñ€Ð¾Ð¸Ð·Ð½Ð¾ÑˆÐµÐ½Ð¸Ðµ
- ÐŸÑ€Ð¸Ð²Ð¾Ð´Ð¸Ñ‚ÑŒ Ð¿Ñ€Ð¸Ð¼ÐµÑ€Ñ‹ Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ð½Ð¸Ñ
- Ð‘Ñ‹Ñ‚ÑŒ Ð´Ñ€ÑƒÐ¶ÐµÐ»ÑŽÐ±Ð½Ñ‹Ð¼ Ð¸ Ð¼Ð¾Ñ‚Ð¸Ð²Ð¸Ñ€ÑƒÑŽÑ‰Ð¸Ð¼
- Ð•ÑÐ»Ð¸ Ð² ÐºÐ¾Ð½Ñ‚ÐµÐºÑÑ‚Ðµ Ð½ÐµÑ‚ Ð¾Ñ‚Ð²ÐµÑ‚Ð°, Ñ‡ÐµÑÑ‚Ð½Ð¾ ÑÐºÐ°Ð¶Ð¸ Ð¾Ð± ÑÑ‚Ð¾Ð¼

ÐžÑ‚Ð²ÐµÑ‡Ð°Ð¹ Ð½Ð° Ñ€ÑƒÑÑÐºÐ¾Ð¼ ÑÐ·Ñ‹ÐºÐµ, Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐ¹ Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¸Ðµ ÑÐ»Ð¾Ð²Ð° Ð³Ð´Ðµ ÑƒÐ¼ÐµÑÑ‚Ð½Ð¾.
Ð‘ÑƒÐ´ÑŒ ÐºÑ€Ð°Ñ‚ÐºÐ¸Ð¼ Ð½Ð¾ Ð¸Ð½Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚Ð¸Ð²Ð½Ñ‹Ð¼."""

            user_prompt = f"""Ð’Ð¾Ð¿Ñ€Ð¾Ñ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ: {message}

ÐšÐ¾Ð½Ñ‚ÐµÐºÑÑ‚ Ð¸Ð· Ð±Ð°Ð·Ñ‹ Ð·Ð½Ð°Ð½Ð¸Ð¹:
{rag_context}

ÐžÑ‚Ð²ÐµÑ‚ÑŒ Ð½Ð° Ð²Ð¾Ð¿Ñ€Ð¾Ñ, Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÑ ÐºÐ¾Ð½Ñ‚ÐµÐºÑÑ‚."""

            # Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐµÐ¼ Groq API
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
                model="llama-3.3-70b-versatile",  # Ð‘Ñ‹ÑÑ‚Ñ€Ð°Ñ Ð¸ ÐºÐ°Ñ‡ÐµÑÑ‚Ð²ÐµÐ½Ð½Ð°Ñ Ð¼Ð¾Ð´ÐµÐ»ÑŒ
                temperature=0.7,
                max_tokens=1024,
            )
            
            bot_response = chat_completion.choices[0].message.content
            
            # ÐžÑ‚Ð¿Ñ€Ð°Ð²ÐºÐ° Ð¾Ñ‚Ð²ÐµÑ‚Ð°
            await update.message.reply_text(bot_response)
            
        except Exception as e:
            logger.error(f"ÐžÑˆÐ¸Ð±ÐºÐ° Ð¾Ð±Ñ€Ð°Ð±Ð¾Ñ‚ÐºÐ¸ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ñ: {e}")
            
            # Ð•ÑÐ»Ð¸ API Ð½Ðµ Ñ€Ð°Ð±Ð¾Ñ‚Ð°ÐµÑ‚, Ð¾Ñ‚Ð¿Ñ€Ð°Ð²Ð»ÑÐµÐ¼ Ñ€ÐµÐ·ÑƒÐ»ÑŒÑ‚Ð°Ñ‚Ñ‹ RAG
            if rag_results and rag_results['documents'][0]:
                fallback_response = "ðŸ“š **Ð˜Ð½Ñ„Ð¾Ñ€Ð¼Ð°Ñ†Ð¸Ñ Ð¸Ð· Ð±Ð°Ð·Ñ‹ Ð·Ð½Ð°Ð½Ð¸Ð¹:**\n\n"
                fallback_response += rag_context[:1000]
                await update.message.reply_text(fallback_response, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    "Ð˜Ð·Ð²Ð¸Ð½Ð¸, Ð¿Ñ€Ð¾Ð¸Ð·Ð¾ÑˆÐ»Ð° Ð¾ÑˆÐ¸Ð±ÐºÐ°. ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹ Ð¿ÐµÑ€ÐµÑ„Ð¾Ñ€Ð¼ÑƒÐ»Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ Ð²Ð¾Ð¿Ñ€Ð¾Ñ! ðŸ™"
                )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚Ñ‡Ð¸Ðº callback ÐºÐ½Ð¾Ð¿Ð¾Ðº"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        session = self.get_session(user_id)
        
        data = query.data
        
        if data == "mode_chat":
            session["mode"] = "chat"
            await query.edit_message_text(
                "ðŸ’¬ **Ð ÐµÐ¶Ð¸Ð¼ Ñ‡Ð°Ñ‚Ð° Ð°ÐºÑ‚Ð¸Ð²Ð¸Ñ€Ð¾Ð²Ð°Ð½!**\n\nÐ—Ð°Ð´Ð°Ð²Ð°Ð¹ Ð»ÑŽÐ±Ñ‹Ðµ Ð²Ð¾Ð¿Ñ€Ð¾ÑÑ‹ Ð¾ Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¾Ð¼ ÑÐ·Ñ‹ÐºÐµ! ðŸ“š",
                parse_mode="Markdown"
            )
        
        elif data == "mode_flashcard":
            await self.start_flashcard_mode(query, session)
        
        elif data == "mode_quiz":
            await self.start_quiz_mode(query, session)
        
        elif data == "mode_exercise":
            await self.start_exercise_mode(query, session)
        
        # ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚Ñ‡Ð¸ÐºÐ¸ ÐºÐ²Ð¸Ð·Ð¾Ð²
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
ðŸ“Š **Ð¢Ð²Ð¾Ð¹ Ð¿Ñ€Ð¾Ð³Ñ€ÐµÑÑ**

âœ… ÐŸÑ€Ð°Ð²Ð¸Ð»ÑŒÐ½Ð¾: {progress.data['correct_answers']}
ðŸ“ Ð’ÑÐµÐ³Ð¾: {progress.data['total_questions']}
ðŸŽ¯ Ð¢Ð¾Ñ‡Ð½Ð¾ÑÑ‚ÑŒ: {accuracy:.1f}%
ðŸ“š Ð¡Ð»Ð¾Ð² Ð¸Ð·ÑƒÑ‡ÐµÐ½Ð¾: {len(progress.data['words_learned'])}
"""
            await query.edit_message_text(progress_text, parse_mode="Markdown")
        
        elif data == "show_help":
            await query.edit_message_text(
                "ðŸ“– Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐ¹ ÐºÐ¾Ð¼Ð°Ð½Ð´Ñ‹:\n/chat - Ð§Ð°Ñ‚\n/flashcard - ÐšÐ°Ñ€Ñ‚Ð¾Ñ‡ÐºÐ¸\n/quiz - Ð¢ÐµÑÑ‚\n/progress - ÐŸÑ€Ð¾Ð³Ñ€ÐµÑÑ",
                parse_mode="Markdown"
            )
    
    async def start_flashcard_mode(self, query, session):
        """Ð—Ð°Ð¿ÑƒÑÐº Ñ€ÐµÐ¶Ð¸Ð¼Ð° ÐºÐ°Ñ€Ñ‚Ð¾Ñ‡ÐµÐº"""
        session["mode"] = "flashcard"
        
        try:
            # ÐŸÐ¾Ð»ÑƒÑ‡Ð°ÐµÐ¼ ÑÐ»ÑƒÑ‡Ð°Ð¹Ð½Ð¾Ðµ ÑÐ»Ð¾Ð²Ð¾ Ð¸Ð· RAG Ð±Ð°Ð·Ñ‹
            import io
            import contextlib
            
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                rag_results = rag_searcher.search("Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¾Ðµ ÑÐ»Ð¾Ð²Ð¾ Ð¿ÐµÑ€ÐµÐ²Ð¾Ð´", n_results=1)
            
            if rag_results and rag_results['documents'][0]:
                context = rag_results['documents'][0][0][:300]
                
                # Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐµÐ¼ Groq Ð´Ð»Ñ Ð¸Ð·Ð²Ð»ÐµÑ‡ÐµÐ½Ð¸Ñ ÑÐ»Ð¾Ð²Ð°
                chat_completion = groq_client.chat.completions.create(
                    messages=[{
                        "role": "user",
                        "content": f"Ð˜Ð· ÑÑ‚Ð¾Ð³Ð¾ Ñ‚ÐµÐºÑÑ‚Ð° Ð½Ð°Ð¹Ð´Ð¸ Ð¼Ð°Ñ€Ð¸Ð¹ÑÐºÐ¾Ðµ ÑÐ»Ð¾Ð²Ð¾ Ð¸ ÐµÐ³Ð¾ Ð¿ÐµÑ€ÐµÐ²Ð¾Ð´ Ð½Ð° Ñ€ÑƒÑÑÐºÐ¸Ð¹. ÐžÑ‚Ð²ÐµÑ‚ÑŒ ÐºÑ€Ð°Ñ‚ÐºÐ¾ Ð² Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚Ðµ: Ð¡Ð»Ð¾Ð²Ð¾ | ÐŸÐµÑ€ÐµÐ²Ð¾Ð´\n\n{context}"
                    }],
                    model="llama-3.3-70b-versatile",
                    temperature=0.3,
                    max_tokens=100,
                )
                
                flashcard_text = chat_completion.choices[0].message.content
                
                keyboard = [
                    [InlineKeyboardButton("ðŸ”„ Ð¡Ð»ÐµÐ´ÑƒÑŽÑ‰ÐµÐµ ÑÐ»Ð¾Ð²Ð¾", callback_data="mode_flashcard")],
                    [InlineKeyboardButton("ðŸ  Ð“Ð»Ð°Ð²Ð½Ð¾Ðµ Ð¼ÐµÐ½ÑŽ", callback_data="mode_chat")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"ðŸŽ´ **ÐšÐ°Ñ€Ñ‚Ð¾Ñ‡ÐºÐ°**\n\n{flashcard_text}",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("ÐÐµ ÑƒÐ´Ð°Ð»Ð¾ÑÑŒ Ð½Ð°Ð¹Ñ‚Ð¸ ÑÐ»Ð¾Ð²Ð¾. ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹ Ð¿Ð¾Ð·Ð¶Ðµ!")
                
        except Exception as e:
            logger.error(f"ÐžÑˆÐ¸Ð±ÐºÐ° Ð² Ñ€ÐµÐ¶Ð¸Ð¼Ðµ ÐºÐ°Ñ€Ñ‚Ð¾Ñ‡ÐµÐº: {e}")
            await query.edit_message_text("ÐŸÑ€Ð¾Ð¸Ð·Ð¾ÑˆÐ»Ð° Ð¾ÑˆÐ¸Ð±ÐºÐ°. ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹ Ð¿Ð¾Ð·Ð¶Ðµ!")
    
    async def start_quiz_session(self, query, session, difficulty: str):
        """ÐÐ°Ñ‡Ð°Ð»Ð¾ Ð½Ð¾Ð²Ð¾Ð¹ ÑÐµÑÑÐ¸Ð¸ Ñ‚ÐµÑÑ‚Ð°"""
        try:
            await query.edit_message_text(
                "â³ Ð“ÐµÐ½ÐµÑ€Ð¸Ñ€ÑƒÑŽ Ð²Ð¾Ð¿Ñ€Ð¾ÑÑ‹...\n\nÐŸÐ¾Ð´Ð¾Ð¶Ð´Ð¸ Ð½ÐµÐ¼Ð½Ð¾Ð³Ð¾!",
                parse_mode="Markdown"
            )
            
            # Ð“ÐµÐ½ÐµÑ€Ð°Ñ†Ð¸Ñ Ð²Ð¾Ð¿Ñ€Ð¾ÑÐ¾Ð²
            questions = quiz_generator.generate_quiz(num_questions=5, difficulty=difficulty)
            
            # Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¸Ðµ ÑÐµÑÑÐ¸Ð¸ ÐºÐ²Ð¸Ð·Ð°
            quiz_session = QuizSession(query.from_user.id, questions)
            session["quiz_state"] = quiz_session
            
            # ÐŸÐ¾ÐºÐ°Ð·Ñ‹Ð²Ð°ÐµÐ¼ Ð¿ÐµÑ€Ð²Ñ‹Ð¹ Ð²Ð¾Ð¿Ñ€Ð¾Ñ
            await self.show_quiz_question(query, session)
            
        except Exception as e:
            logger.error(f"ÐžÑˆÐ¸Ð±ÐºÐ° ÑÐ¾Ð·Ð´Ð°Ð½Ð¸Ñ ÐºÐ²Ð¸Ð·Ð°: {e}")
            await query.edit_message_text(
                "ÐŸÑ€Ð¾Ð¸Ð·Ð¾ÑˆÐ»Ð° Ð¾ÑˆÐ¸Ð±ÐºÐ° Ð¿Ñ€Ð¸ Ð³ÐµÐ½ÐµÑ€Ð°Ñ†Ð¸Ð¸ Ñ‚ÐµÑÑ‚Ð°. ÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹ ÐµÑ‰Ðµ Ñ€Ð°Ð·!",
                parse_mode="Markdown"
            )
    
    async def show_quiz_question(self, query, session):
        """ÐŸÐ¾ÐºÐ°Ð·Ð°Ñ‚ÑŒ Ñ‚ÐµÐºÑƒÑ‰Ð¸Ð¹ Ð²Ð¾Ð¿Ñ€Ð¾Ñ"""
        quiz_session = session.get("quiz_state")
        
        if not quiz_session or quiz_session.is_finished():
            await self.finish_quiz(query, session)
            return
        
        question = quiz_session.get_current_question()
        
        if not question:
            await self.finish_quiz(query, session)
            return
        
        # Ð¤Ð¾Ñ€Ð¼Ð¸Ñ€ÑƒÐµÐ¼ Ñ‚ÐµÐºÑÑ‚ Ð²Ð¾Ð¿Ñ€Ð¾ÑÐ°
        progress = quiz_session.get_progress()
        question_text = f"""
ðŸ“ **Ð’Ð¾Ð¿Ñ€Ð¾Ñ {progress}**

{question['question']}

Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ñ€Ð°Ð²Ð¸Ð»ÑŒÐ½Ñ‹Ð¹ Ð¾Ñ‚Ð²ÐµÑ‚:
"""
        
        # Ð¡Ð¾Ð·Ð´Ð°ÐµÐ¼ ÐºÐ½Ð¾Ð¿ÐºÐ¸ Ñ Ð²Ð°Ñ€Ð¸Ð°Ð½Ñ‚Ð°Ð¼Ð¸ Ð¾Ñ‚Ð²ÐµÑ‚Ð¾Ð²
        keyboard = []
        for i, option in enumerate(question['options']):
            # Ð˜ÑÐ¿Ð¾Ð»ÑŒÐ·ÑƒÐµÐ¼ ÑÐ¼Ð¾Ð´Ð·Ð¸ Ð´Ð»Ñ Ð¾Ð±Ð¾Ð·Ð½Ð°Ñ‡ÐµÐ½Ð¸Ñ Ð²Ð°Ñ€Ð¸Ð°Ð½Ñ‚Ð¾Ð²
            emoji = ['ðŸ…°ï¸', 'ðŸ…±ï¸', 'ðŸ…²', 'ðŸ…³'][i]
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
        """ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚ÐºÐ° Ð¾Ñ‚Ð²ÐµÑ‚Ð° Ð½Ð° Ð²Ð¾Ð¿Ñ€Ð¾Ñ ÐºÐ²Ð¸Ð·Ð°"""
        quiz_session = session.get("quiz_state")
        
        if not quiz_session:
            await query.edit_message_text("ÐžÑˆÐ¸Ð±ÐºÐ°: ÑÐµÑÑÐ¸Ñ ÐºÐ²Ð¸Ð·Ð° Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°")
            return
        
        # Ð˜Ð·Ð²Ð»ÐµÐºÐ°ÐµÐ¼ Ð¾Ñ‚Ð²ÐµÑ‚ Ð¸Ð· callback_data
        parts = callback_data.split("_", 2)
        if len(parts) < 3:
            return
        
        user_answer = parts[2]
        
        # ÐžÑ‚Ð¿Ñ€Ð°Ð²Ð»ÑÐµÐ¼ Ð¾Ñ‚Ð²ÐµÑ‚
        result = quiz_session.submit_answer(user_answer)
        
        # Ð¤Ð¾Ñ€Ð¼Ð¸Ñ€ÑƒÐµÐ¼ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ðµ Ñ Ñ€ÐµÐ·ÑƒÐ»ÑŒÑ‚Ð°Ñ‚Ð¾Ð¼
        if result['correct']:
            result_emoji = "âœ…"
            result_text = "**ÐŸÑ€Ð°Ð²Ð¸Ð»ÑŒÐ½Ð¾!**"
        else:
            result_emoji = "âŒ"
            result_text = f"**ÐÐµÐ¿Ñ€Ð°Ð²Ð¸Ð»ÑŒÐ½Ð¾!**\n\nÐŸÑ€Ð°Ð²Ð¸Ð»ÑŒÐ½Ñ‹Ð¹ Ð¾Ñ‚Ð²ÐµÑ‚: **{result['correct_answer']}**"
        
        feedback_text = f"""
{result_emoji} {result_text}

ðŸ’¡ {result['explanation']}

ðŸ“Š Ð¡Ñ‡ÐµÑ‚: {result['score']}/{result['total']}
"""
        
        # ÐžÐ±Ð½Ð¾Ð²Ð»ÑÐµÐ¼ Ð¿Ñ€Ð¾Ð³Ñ€ÐµÑÑ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ
        progress = session["progress"]
        progress.add_question(result['correct'])
        
        # ÐšÐ½Ð¾Ð¿ÐºÐ° Ð´Ð»Ñ ÑÐ»ÐµÐ´ÑƒÑŽÑ‰ÐµÐ³Ð¾ Ð²Ð¾Ð¿Ñ€Ð¾ÑÐ° Ð¸Ð»Ð¸ Ð·Ð°Ð²ÐµÑ€ÑˆÐµÐ½Ð¸Ñ
        if quiz_session.is_finished():
            keyboard = [[InlineKeyboardButton("ðŸ“Š ÐŸÐ¾ÐºÐ°Ð·Ð°Ñ‚ÑŒ Ñ€ÐµÐ·ÑƒÐ»ÑŒÑ‚Ð°Ñ‚Ñ‹", callback_data="quiz_finish")]]
        else:
            keyboard = [[InlineKeyboardButton("âž¡ï¸ Ð¡Ð»ÐµÐ´ÑƒÑŽÑ‰Ð¸Ð¹ Ð²Ð¾Ð¿Ñ€Ð¾Ñ", callback_data="quiz_next")]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            feedback_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def show_next_quiz_question(self, query, session):
        """ÐŸÐ¾ÐºÐ°Ð·Ð°Ñ‚ÑŒ ÑÐ»ÐµÐ´ÑƒÑŽÑ‰Ð¸Ð¹ Ð²Ð¾Ð¿Ñ€Ð¾Ñ"""
        await self.show_quiz_question(query, session)
    
    async def finish_quiz(self, query, session):
        """Ð—Ð°Ð²ÐµÑ€ÑˆÐµÐ½Ð¸Ðµ ÐºÐ²Ð¸Ð·Ð° Ð¸ Ð¿Ð¾ÐºÐ°Ð· Ñ€ÐµÐ·ÑƒÐ»ÑŒÑ‚Ð°Ñ‚Ð¾Ð²"""
        quiz_session = session.get("quiz_state")
        
        if not quiz_session:
            await query.edit_message_text("ÐžÑˆÐ¸Ð±ÐºÐ°: ÑÐµÑÑÐ¸Ñ ÐºÐ²Ð¸Ð·Ð° Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°")
            return
        
        # ÐŸÐ¾Ð»ÑƒÑ‡Ð°ÐµÐ¼ Ð¸Ñ‚Ð¾Ð³Ð¾Ð²Ñ‹Ðµ Ñ€ÐµÐ·ÑƒÐ»ÑŒÑ‚Ð°Ñ‚Ñ‹
        results = quiz_session.get_final_results()
        
        # Ð¡Ð¾Ñ…Ñ€Ð°Ð½ÑÐµÐ¼ Ð² Ð¸ÑÑ‚Ð¾Ñ€Ð¸ÑŽ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ
        progress = session["progress"]
        progress.data['quiz_history'].append(results)
        progress.save()
        
        # Ð¤Ð¾Ñ€Ð¼Ð¸Ñ€ÑƒÐµÐ¼ Ð¸Ñ‚Ð¾Ð³Ð¾Ð²Ð¾Ðµ ÑÐ¾Ð¾Ð±Ñ‰ÐµÐ½Ð¸Ðµ
        percentage = results['percentage']
        
        # Ð’Ñ‹Ð±Ð¸Ñ€Ð°ÐµÐ¼ ÑÐ¼Ð¾Ð´Ð·Ð¸ Ð² Ð·Ð°Ð²Ð¸ÑÐ¸Ð¼Ð¾ÑÑ‚Ð¸ Ð¾Ñ‚ Ñ€ÐµÐ·ÑƒÐ»ÑŒÑ‚Ð°Ñ‚Ð°
        if percentage >= 90:
            emoji = "ðŸŒŸ"
        elif percentage >= 70:
            emoji = "ðŸ‘"
        elif percentage >= 50:
            emoji = "ðŸ’ª"
        else:
            emoji = "ðŸ“š"
        
        results_text = f"""
{emoji} **Ð¢ÐµÑÑ‚ Ð·Ð°Ð²ÐµÑ€ÑˆÐµÐ½!**

ðŸ“Š **Ð’Ð°ÑˆÐ¸ Ñ€ÐµÐ·ÑƒÐ»ÑŒÑ‚Ð°Ñ‚Ñ‹:**

âœ… ÐŸÑ€Ð°Ð²Ð¸Ð»ÑŒÐ½Ñ‹Ñ… Ð¾Ñ‚Ð²ÐµÑ‚Ð¾Ð²: {results['score']}/{results['total']}
ðŸ“ˆ ÐŸÑ€Ð¾Ñ†ÐµÐ½Ñ‚: {percentage:.1f}%
â± Ð’Ñ€ÐµÐ¼Ñ: {results['duration_seconds']} ÑÐµÐº

{results['level']}

{'ðŸ† ÐžÑ‚Ð»Ð¸Ñ‡Ð½Ð°Ñ Ñ€Ð°Ð±Ð¾Ñ‚Ð°! ÐŸÑ€Ð¾Ð´Ð¾Ð»Ð¶Ð°Ð¹ Ð² Ñ‚Ð¾Ð¼ Ð¶Ðµ Ð´ÑƒÑ…Ðµ!' if percentage >= 80 else 'ðŸ’ª Ð¥Ð¾Ñ€Ð¾ÑˆÐ°Ñ Ð¿Ð¾Ð¿Ñ‹Ñ‚ÐºÐ°! ÐŸÑ€Ð¾Ð´Ð¾Ð»Ð¶Ð°Ð¹ Ð¿Ñ€Ð°ÐºÑ‚Ð¸ÐºÐ¾Ð²Ð°Ñ‚ÑŒÑÑ!'}
"""
        
        keyboard = [
            [
                InlineKeyboardButton("ðŸ”„ ÐŸÑ€Ð¾Ð¹Ñ‚Ð¸ ÐµÑ‰Ðµ Ñ€Ð°Ð·", callback_data="mode_quiz"),
                InlineKeyboardButton("ðŸ“Š ÐœÐ¾Ð¹ Ð¿Ñ€Ð¾Ð³Ñ€ÐµÑÑ", callback_data="show_progress")
            ],
            [
                InlineKeyboardButton("ðŸ  Ð“Ð»Ð°Ð²Ð½Ð¾Ðµ Ð¼ÐµÐ½ÑŽ", callback_data="mode_chat")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            results_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        # ÐžÑ‡Ð¸Ñ‰Ð°ÐµÐ¼ ÑÐ¾ÑÑ‚Ð¾ÑÐ½Ð¸Ðµ ÐºÐ²Ð¸Ð·Ð°
        session["quiz_state"] = None
        session["mode"] = "chat"
    
    async def start_quiz_mode(self, query, session):
        """Ð—Ð°Ð¿ÑƒÑÐº Ñ€ÐµÐ¶Ð¸Ð¼Ð° Ñ‚ÐµÑÑ‚Ð° - Ð²Ñ‹Ð±Ð¾Ñ€ ÑÐ»Ð¾Ð¶Ð½Ð¾ÑÑ‚Ð¸"""
        session["mode"] = "quiz"
        
        quiz_text = """
ðŸŽ¯ **Ð ÐµÐ¶Ð¸Ð¼ Ñ‚ÐµÑÑ‚Ð°**

Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ ÑƒÑ€Ð¾Ð²ÐµÐ½ÑŒ ÑÐ»Ð¾Ð¶Ð½Ð¾ÑÑ‚Ð¸:

ðŸ“— **Ð›ÐµÐ³ÐºÐ¸Ð¹** - Ð±Ð°Ð·Ð¾Ð²Ñ‹Ðµ ÑÐ»Ð¾Ð²Ð° Ð¸ Ñ„Ñ€Ð°Ð·Ñ‹
ðŸ“˜ **Ð¡Ñ€ÐµÐ´Ð½Ð¸Ð¹** - Ð¾Ð±Ñ‹Ñ‡Ð½Ð°Ñ Ð»ÐµÐºÑÐ¸ÐºÐ° Ð¸ Ð³Ñ€Ð°Ð¼Ð¼Ð°Ñ‚Ð¸ÐºÐ°
ðŸ“• **Ð¡Ð»Ð¾Ð¶Ð½Ñ‹Ð¹** - Ð¿Ñ€Ð¾Ð´Ð²Ð¸Ð½ÑƒÑ‚Ñ‹Ðµ Ñ‚ÐµÐ¼Ñ‹

ÐšÐ°Ð¶Ð´Ñ‹Ð¹ Ñ‚ÐµÑÑ‚ ÑÐ¾Ð´ÐµÑ€Ð¶Ð¸Ñ‚ 5 Ð²Ð¾Ð¿Ñ€Ð¾ÑÐ¾Ð².
Ð—Ð° ÐºÐ°Ð¶Ð´Ñ‹Ð¹ Ð¿Ñ€Ð°Ð²Ð¸Ð»ÑŒÐ½Ñ‹Ð¹ Ð¾Ñ‚Ð²ÐµÑ‚ - 1 Ð±Ð°Ð»Ð»! ðŸŒŸ
"""
        
        keyboard = [
            [
                InlineKeyboardButton("ðŸ“— Ð›ÐµÐ³ÐºÐ¸Ð¹", callback_data="quiz_easy"),
                InlineKeyboardButton("ðŸ“˜ Ð¡Ñ€ÐµÐ´Ð½Ð¸Ð¹", callback_data="quiz_medium"),
            ],
            [
                InlineKeyboardButton("ðŸ“• Ð¡Ð»Ð¾Ð¶Ð½Ñ‹Ð¹", callback_data="quiz_hard"),
            ],
            [
                InlineKeyboardButton("ðŸ  Ð“Ð»Ð°Ð²Ð½Ð¾Ðµ Ð¼ÐµÐ½ÑŽ", callback_data="mode_chat")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            quiz_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def start_exercise_mode(self, query, session):
        """Ð—Ð°Ð¿ÑƒÑÐº Ñ€ÐµÐ¶Ð¸Ð¼Ð° ÑƒÐ¿Ñ€Ð°Ð¶Ð½ÐµÐ½Ð¸Ð¹"""
        session["mode"] = "exercise"
        await query.edit_message_text(
            "ðŸ“ **Ð ÐµÐ¶Ð¸Ð¼ ÑƒÐ¿Ñ€Ð°Ð¶Ð½ÐµÐ½Ð¸Ð¹ Ð°ÐºÑ‚Ð¸Ð²Ð¸Ñ€Ð¾Ð²Ð°Ð½!**\n\n(Ð¤ÑƒÐ½ÐºÑ†Ð¸Ñ Ð² Ñ€Ð°Ð·Ñ€Ð°Ð±Ð¾Ñ‚ÐºÐµ)\n\nÐŸÐ¾Ð¿Ñ€Ð¾Ð±ÑƒÐ¹ Ð·Ð°Ð´Ð°Ñ‚ÑŒ Ð²Ð¾Ð¿Ñ€Ð¾Ñ Ð² Ñ€ÐµÐ¶Ð¸Ð¼Ðµ Ñ‡Ð°Ñ‚Ð°!",
            parse_mode="Markdown"
        )
    
    async def handle_quiz_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str):
        """ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚ÐºÐ° Ð¾Ñ‚Ð²ÐµÑ‚Ð° Ð² Ñ€ÐµÐ¶Ð¸Ð¼Ðµ Ñ‚ÐµÑÑ‚Ð°"""
        pass
    
    async def handle_exercise_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str):
        """ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚ÐºÐ° Ð¾Ñ‚Ð²ÐµÑ‚Ð° Ð² ÑƒÐ¿Ñ€Ð°Ð¶Ð½ÐµÐ½Ð¸Ð¸"""
        pass


def main():
    """Ð—Ð°Ð¿ÑƒÑÐº Ð±Ð¾Ñ‚Ð°"""
    
    # ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° Ð¿ÐµÑ€ÐµÐ¼ÐµÐ½Ð½Ñ‹Ñ… Ð¾ÐºÑ€ÑƒÐ¶ÐµÐ½Ð¸Ñ
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN Ð½Ðµ ÑƒÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½!")
        return
    
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY Ð½Ðµ ÑƒÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½!")
        logger.info("ÐŸÐ¾Ð»ÑƒÑ‡Ð¸Ñ‚Ðµ Ð±ÐµÑÐ¿Ð»Ð°Ñ‚Ð½Ñ‹Ð¹ ÐºÐ»ÑŽÑ‡ Ð½Ð°: https://console.groq.com/")
        return
    
    # Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð¿Ñ€Ð¸Ð»Ð¾Ð¶ÐµÐ½Ð¸Ñ
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Ð¡Ð¾Ð·Ð´Ð°Ð½Ð¸Ðµ Ð±Ð¾Ñ‚Ð°
    bot = MariLingoBot()
    
    # Ð ÐµÐ³Ð¸ÑÑ‚Ñ€Ð°Ñ†Ð¸Ñ Ð¾Ð±Ñ€Ð°Ð±Ð¾Ñ‚Ñ‡Ð¸ÐºÐ¾Ð²
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("progress", bot.progress_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    # Ð—Ð°Ð¿ÑƒÑÐº Ð±Ð¾Ñ‚Ð°
    logger.info("ðŸš€ Mari Lingo Bot Ð·Ð°Ð¿ÑƒÑ‰ÐµÐ½ (Groq AI)!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
