# Интеграция геймификации (справочник)

> Этот файл — не модуль, а набор сниппетов «куда что вставить». Изменения уже
> применены к `mari_lingo_bot_groq.py`. Раньше он лежал в корне как
> `gamification_integration.py` и не был валидным Python (`elif` на уровне
> модуля, SyntaxError на строке 79): ботом он не импортируется, но ломал
> линтеры, `py_compile` и любые попытки прогнать проверки по всему репозиторию.

```python
"""
Интеграция системы геймификации с Mari Lingo Bot
Этот файл показывает как добавить геймификацию в основной бот
"""

# ============================================
# 1. ИМПОРТЫ (добавить в mari_lingo_bot_groq.py)
# ============================================

from gamification import GamificationSystem, LEVELS, format_leaderboard, get_leaderboard


# ============================================
# 2. ИЗМЕНИТЬ get_session() в классе MariLingoBot
# ============================================

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
            "gamification": GamificationSystem(user_id, USER_DATA_PATH),  # <-- ДОБАВИТЬ
        }
    return self.user_sessions[user_id]


# ============================================
# 3. ДОБАВИТЬ КНОПКИ В ГЛАВНОЕ МЕНЮ
# ============================================

# В start_command и menu_command добавить кнопки:
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
        InlineKeyboardButton("🏆 Достижения", callback_data="show_achievements")  # <-- НОВОЕ
    ],
    [
        InlineKeyboardButton("📋 Ежедневные цели", callback_data="show_daily_goals"),  # <-- НОВОЕ
        InlineKeyboardButton("🏅 Лидеры", callback_data="show_leaderboard")  # <-- НОВОЕ
    ],
    [
        InlineKeyboardButton("ℹ️ Помощь", callback_data="show_help")
    ]
]


# ============================================
# 4. ДОБАВИТЬ ОБРАБОТЧИКИ В handle_callback()
# ============================================

async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    session = self.get_session(user_id)
    gamification = session["gamification"]  # <-- ПОЛУЧАЕМ СИСТЕМУ
    
    data = query.data
    
    # ... существующие обработчики ...
    
    # НОВЫЕ ОБРАБОТЧИКИ:
    
    elif data == "show_achievements":
        # Показать достижения
        achievements_text = gamification.get_achievements_summary()
        
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            achievements_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    elif data == "show_daily_goals":
        # Показать ежедневные цели
        goals_text = gamification.get_daily_goals_summary()
        
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            goals_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    elif data == "show_leaderboard":
        # Показать таблицу лидеров
        leaderboard = get_leaderboard(USER_DATA_PATH)
        leaderboard_text = format_leaderboard(leaderboard)
        
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            leaderboard_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    elif data == "show_progress":
        # ОБНОВЛЁННЫЙ обработчик прогресса с геймификацией
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
    
    elif data == "main_menu":
        # Вернуться в главное меню
        await self.show_main_menu(query)


# ============================================
# 5. ДОБАВИТЬ МЕТОД show_main_menu()
# ============================================

async def show_main_menu(self, query):
    """Показать главное меню"""
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
            InlineKeyboardButton("🏆 Достижения", callback_data="show_achievements")
        ],
        [
            InlineKeyboardButton("📋 Цели дня", callback_data="show_daily_goals"),
            InlineKeyboardButton("🏅 Лидеры", callback_data="show_leaderboard")
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        menu_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# ============================================
# 6. ИНТЕГРИРОВАТЬ В finish_quiz()
# ============================================

async def finish_quiz(self, query, session):
    """Завершение квиза и показ результатов"""
    quiz_session = session.get("quiz_state")
    gamification = session["gamification"]  # <-- ПОЛУЧАЕМ
    
    if not quiz_session:
        await query.edit_message_text("Ошибка: сессия квиза не найдена")
        return
    
    results = quiz_session.get_final_results()
    
    # ЗАПИСЫВАЕМ В ГЕЙМИФИКАЦИЮ
    game_result = gamification.record_quiz_completed(
        correct=results['score'],
        total=results['total']
    )
    
    percentage = results['percentage']
    
    # Формируем сообщение с XP
    if percentage >= 90:
        emoji = "🌟"
    elif percentage >= 70:
        emoji = "👍"
    elif percentage >= 50:
        emoji = "💪"
    else:
        emoji = "📚"
    
    results_text = f"""
{emoji} **Тест завершён!**

📊 **Результаты:**
✅ Правильно: {results['score']}/{results['total']}
📈 Процент: {percentage:.1f}%

⭐ **+{game_result['xp_earned']} XP**
"""
    
    # Добавляем информацию о повышении уровня
    if game_result['level_up']:
        level_info = LEVELS[game_result['new_level']]
        results_text += f"""
🎉 **НОВЫЙ УРОВЕНЬ!**
{level_info['emoji']} Уровень {game_result['new_level']}: {level_info['name']}
"""
    
    # Добавляем новые достижения
    if game_result['new_achievements']:
        results_text += "\n🏆 **Новые достижения:**\n"
        for ach in game_result['new_achievements']:
            results_text += f"{ach['emoji']} {ach['name']}\n"
    
    # Добавляем прогресс ежедневных целей
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
        [InlineKeyboardButton("🏠 Меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        results_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    session["quiz_state"] = None
    session["mode"] = "chat"


# ============================================
# 7. ИНТЕГРИРОВАТЬ В start_flashcard_mode()
# ============================================

async def start_flashcard_mode(self, query, session):
    """Запуск режима карточек"""
    session["mode"] = "flashcard"
    gamification = session["gamification"]  # <-- ПОЛУЧАЕМ
    
    try:
        # ... существующий код получения карточки ...
        
        flashcard_text = chat_completion.choices[0].message.content
        
        # ЗАПИСЫВАЕМ В ГЕЙМИФИКАЦИЮ
        game_result = gamification.record_flashcard_learned(flashcard_text)
        
        # Добавляем XP в сообщение
        card_message = f"🎴 **Карточка**\n\n{flashcard_text}\n\n⭐ +{game_result['xp_earned']} XP"
        
        # Если повысился уровень
        if game_result['level_up']:
            card_message += "\n\n🎉 **Новый уровень!**"
        
        # Если получено достижение
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
        
    except Exception as e:
        logger.error(f"Ошибка в режиме карточек: {e}")
        await query.edit_message_text("Произошла ошибка. Попробуй позже!")


# ============================================
# 8. ИНТЕГРИРОВАТЬ В handle_chat_message()
# ============================================

async def handle_chat_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
    """Обработка сообщения в режиме чата с RAG"""
    user_id = update.effective_user.id
    session = self.get_session(user_id)
    gamification = session["gamification"]  # <-- ПОЛУЧАЕМ
    
    # ... существующий код обработки ...
    
    # После отправки ответа записываем активность
    gamification.record_chat_question()
    
    # Отправка ответа
    await update.message.reply_text(bot_response)


# ============================================
# 9. ДОБАВИТЬ ПРИВЕТСТВЕННЫЙ БОНУС В start_command()
# ============================================

async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    session = self.get_session(user_id)
    gamification = session["gamification"]
    
    # Начисляем бонус за вход
    login_result = gamification.claim_daily_login_bonus()
    
    level_info = gamification.get_level_info()
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я **Mari Lingo Bot** - твой помощник в изучении марийского языка! 🎓

{level_info['emoji']} **Твой уровень:** {level_info['level']} ({level_info['name']})
⭐ **XP:** {level_info['xp']}
🔥 **Серия:** {gamification.data['stats']['current_streak']} дней
"""
    
    if login_result['claimed']:
        welcome_text += f"\n✨ **+{login_result['xp']} XP** за ежедневный вход!"
        
        if login_result['streak'] and login_result['streak']['streak_bonus']:
            bonus = login_result['streak']['streak_bonus']
            welcome_text += f"\n🎁 **+{bonus['xp']} XP** за серию {bonus['days']} дней!"
    
    welcome_text += "\n\n**Выбери действие:**"
    
    # ... остальной код меню ...
```
