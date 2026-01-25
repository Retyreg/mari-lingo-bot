#!/usr/bin/env python3
"""
Патч для добавления системы карточек в mari_lingo_bot_groq.py
Запуск: python3 apply_flashcard_patch.py
"""

import re

# Читаем файл
with open('mari_lingo_bot_groq.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Добавляем импорт flashcard_system после gamification
old_import = "from gamification import GamificationSystem, LEVELS, get_leaderboard, format_leaderboard"
new_import = """from gamification import GamificationSystem, LEVELS, get_leaderboard, format_leaderboard
from flashcard_system import FlashcardDeck, FlashcardManager, FlashCard as FC, format_flashcard_message, format_session_stats"""

if "flashcard_system" not in content:
    content = content.replace(old_import, new_import)
    print("✅ Добавлен импорт flashcard_system")
else:
    print("ℹ️ Импорт уже есть")

# 2. Добавляем поля в get_session
old_session = '"gamification": GamificationSystem(user_id, USER_DATA_PATH)'
new_session = '''"gamification": GamificationSystem(user_id, USER_DATA_PATH),
                "flashcard_deck": None,
                "flashcard_session": {"knew": 0, "total": 0}'''

if '"flashcard_deck"' not in content:
    content = content.replace(old_session, new_session)
    print("✅ Добавлены поля flashcard в сессию")
else:
    print("ℹ️ Поля flashcard уже есть")

# 3. Находим и заменяем start_flashcard_mode
new_flashcard_mode = '''    async def start_flashcard_mode(self, query, session):
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
            init_msg = f"\\n\\n✨ Добавлено {added} слов!"
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
            text = "📭 Нет карточек!\\n\\n"
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
        text = f"{progress}\\n{text}"
        
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
            text += f"{emoji} {cat}: {c['mastered']}/{c['total']}\\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="mode_flashcard")]]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

'''

# Находим старый start_flashcard_mode и заменяем
pattern = r'    async def start_flashcard_mode\(self, query, session\):.*?(?=\n    async def start_quiz_session)'
if re.search(pattern, content, re.DOTALL):
    content = re.sub(pattern, new_flashcard_mode, content, flags=re.DOTALL)
    print("✅ Заменён start_flashcard_mode и добавлены новые методы")
else:
    print("❌ Не удалось найти start_flashcard_mode")

# 4. Добавляем обработчики callback
# Находим место после elif data == "mode_flashcard":
callback_handlers = '''
        # Карточки - новые обработчики
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
        
'''

# Вставляем после mode_flashcard
if "fc_review" not in content:
    old_flashcard_handler = '''elif data == "mode_flashcard":
            await self.start_flashcard_mode(query, session)'''
    new_flashcard_handler = old_flashcard_handler + callback_handlers
    content = content.replace(old_flashcard_handler, new_flashcard_handler)
    print("✅ Добавлены callback обработчики")
else:
    print("ℹ️ Callback обработчики уже есть")

# Сохраняем
with open('mari_lingo_bot_groq.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ Патч применён! Перезапустите бота:")
print("   pkill -f mari_lingo && python3 mari_lingo_bot_groq.py")
