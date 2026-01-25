"""
Методы Spaced Repetition для интеграции в Mari Lingo Bot
Добавьте эти методы в класс MariLingoBot
"""

async def sr_review_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /review - начать повторение карточек"""
    user_id = update.effective_user.id
    session = self.get_session(user_id)
    sr_system = session["sr_system"]
    
    # Получаем карточки для повторения
    due_cards = sr_system.get_due_cards(limit=10)
    new_cards = sr_system.get_new_cards(limit=5)
    
    stats = sr_system.get_statistics()
    
    review_text = f"""
📚 **Повторение карточек**

📊 Статистика:
• Всего карточек: {stats['total_cards']}
• Новых: {stats['new_cards']} 📗
• Изучаются: {stats['learning_cards']} 📘
• Знакомых: {stats['familiar_cards']} 📙
• Освоено: {stats['mastered_cards']} 📕

⏰ **К повторению сегодня: {stats['due_today']}**

Точность: {stats['average_accuracy']:.1f}%
"""
    
    keyboard = []
    
    if due_cards or new_cards:
        keyboard.append([InlineKeyboardButton(
            f"🎯 Начать повторение ({len(due_cards)} карточек)",
            callback_data="sr_start_review"
        )])
    
    if new_cards:
        keyboard.append([InlineKeyboardButton(
            f"📗 Изучить новые ({len(new_cards)} карточек)",
            callback_data="sr_learn_new"
        )])
    
    keyboard.extend([
        [
            InlineKeyboardButton("📊 Статистика", callback_data="sr_stats"),
            InlineKeyboardButton("🔍 Сложные", callback_data="sr_difficult")
        ],
        [
            InlineKeyboardButton("➕ Добавить карточку", callback_data="sr_add_card"),
            InlineKeyboardButton("📋 Все карточки", callback_data="sr_list_all")
        ],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="mode_chat")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        review_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def start_sr_review(self, query, session):
    """Начало SR повторения"""
    sr_system = session["sr_system"]
    
    # Получаем карточки для повторения
    due_cards = sr_system.get_due_cards(limit=10)
    
    if not due_cards:
        await query.edit_message_text(
            "🎉 Отлично! Сегодня нечего повторять.\n\nВсе карточки выучены!",
            parse_mode="Markdown"
        )
        return
    
    # Начинаем повторение
    session["mode"] = "sr_review"
    session["sr_state"] = {
        "cards": due_cards,
        "current_index": 0,
        "results": []
    }
    
    await self.show_sr_card(query, session)


async def show_sr_card(self, query, session):
    """Показать текущую карточку SR"""
    sr_state = session.get("sr_state")
    
    if not sr_state or sr_state["current_index"] >= len(sr_state["cards"]):
        await self.finish_sr_review(query, session)
        return
    
    card = sr_state["cards"][sr_state["current_index"]]
    progress = f"{sr_state['current_index'] + 1}/{len(sr_state['cards'])}"
    
    # Показываем лицевую сторону (марийское слово)
    card_text = f"""
🎴 **Карточка {progress}**

📖 Уровень: {card.get_mastery_level()}
🔄 Повторений: {card.repetitions}
📅 Интервал: {card.interval} дней

━━━━━━━━━━━━━━━━━

**{card.front}**

Как переводится это слово?
"""
    
    keyboard = [
        [InlineKeyboardButton("👁️ Показать ответ", callback_data="sr_show_answer")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        card_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_sr_answer(self, query, session):
    """Показать ответ и кнопки оценки"""
    sr_state = session.get("sr_state")
    card = sr_state["cards"][sr_state["current_index"]]
    progress = f"{sr_state['current_index'] + 1}/{len(sr_state['cards'])}"
    
    answer_text = f"""
🎴 **Карточка {progress}**

**Вопрос:** {card.front}
**Ответ:** {card.back}

━━━━━━━━━━━━━━━━━

Насколько легко вы вспомнили?
"""
    
    # Кнопки оценки сложности (по алгоритму SM-2)
    keyboard = [
        [InlineKeyboardButton("😰 Не знал совсем (0)", callback_data="sr_rate_0")],
        [InlineKeyboardButton("😟 Не знал (1)", callback_data="sr_rate_1")],
        [InlineKeyboardButton("😕 С трудом (2)", callback_data="sr_rate_2")],
        [InlineKeyboardButton("😐 Правильно, с усилием (3)", callback_data="sr_rate_3")],
        [InlineKeyboardButton("🙂 Правильно, легко (4)", callback_data="sr_rate_4")],
        [InlineKeyboardButton("😃 Очень легко! (5)", callback_data="sr_rate_5")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        answer_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def rate_sr_card(self, query, session, quality: int):
    """Оценить карточку и перейти к следующей"""
    sr_state = session["sr_state"]
    sr_system = session["sr_system"]
    
    card = sr_state["cards"][sr_state["current_index"]]
    
    # Обновляем карточку через SR систему
    updated_card = sr_system.review_card(card.card_id, quality)
    
    # Сохраняем результат
    sr_state["results"].append({
        "card": card,
        "quality": quality,
        "next_interval": updated_card.interval
    })
    
    # Показываем результат оценки
    quality_names = {
        0: "Не знал совсем",
        1: "Не знал",
        2: "С трудом",
        3: "Правильно, с усилием",
        4: "Правильно, легко",
        5: "Очень легко"
    }
    
    result_text = f"""
{'✅' if quality >= 3 else '❌'} **{quality_names[quality]}**

📅 Следующее повторение через: **{updated_card.interval} дней**
📈 Коэффициент легкости: {updated_card.easiness_factor:.2f}
"""
    
    keyboard = [[InlineKeyboardButton("➡️ Следующая карточка", callback_data="sr_next_card")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        result_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def next_sr_card(self, query, session):
    """Перейти к следующей карточке"""
    sr_state = session["sr_state"]
    sr_state["current_index"] += 1
    
    await self.show_sr_card(query, session)


async def finish_sr_review(self, query, session):
    """Завершение SR повторения"""
    sr_state = session.get("sr_state")
    
    if not sr_state or not sr_state["results"]:
        await query.edit_message_text("Повторение завершено!")
        return
    
    results = sr_state["results"]
    total = len(results)
    correct = sum(1 for r in results if r["quality"] >= 3)
    
    # Статистика по интервалам
    intervals = [r["next_interval"] for r in results]
    avg_interval = sum(intervals) / len(intervals) if intervals else 0
    
    summary_text = f"""
🎉 **Повторение завершено!**

📊 **Результаты:**
• Повторено карточек: {total}
• Правильно: {correct} ({correct/total*100:.0f}%)
• Неправильно: {total - correct}

📅 **Интервалы:**
• Средний интервал: {avg_interval:.1f} дней
• От {min(intervals)} до {max(intervals)} дней

{'🌟 Отличная работа!' if correct/total >= 0.8 else '💪 Продолжай практиковаться!'}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 Повторить еще", callback_data="sr_start_review"),
            InlineKeyboardButton("📊 Статистика", callback_data="sr_stats")
        ],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="mode_chat")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        summary_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    # Очищаем состояние
    session["sr_state"] = None
    session["mode"] = "chat"


async def show_sr_stats(self, query, session):
    """Показать детальную статистику SR"""
    sr_system = session["sr_system"]
    stats = sr_system.get_statistics()
    
    stats_text = f"""
📊 **Детальная статистика**

📚 **Карточки:**
• Всего: {stats['total_cards']}
• Новые: {stats['new_cards']} 📗
• Изучаются: {stats['learning_cards']} 📘
• Знакомые: {stats['familiar_cards']} 📙
• Освоены: {stats['mastered_cards']} 📕

⏰ **Сегодня:**
• К повторению: {stats['due_today']}

📈 **Общая статистика:**
• Всего повторений: {stats['total_reviews']}
• Точность: {stats['average_accuracy']:.1f}%

{'🎯 Продолжай в том же духе!' if stats['average_accuracy'] >= 80 else '💪 Больше практики!'}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="mode_sr_review")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="mode_chat")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_difficult_cards(self, query, session):
    """Показать самые сложные карточки"""
    sr_system = session["sr_system"]
    difficult = sr_system.get_difficult_cards(limit=5)
    
    if not difficult:
        await query.edit_message_text(
            "Пока нет статистики по сложным карточкам.\n\nСначала повторите несколько карточек!",
            parse_mode="Markdown"
        )
        return
    
    cards_list = []
    for i, card in enumerate(difficult, 1):
        accuracy = card.get_accuracy()
        cards_list.append(
            f"{i}. **{card.front}** → {card.back}\n"
            f"   Точность: {accuracy:.0f}% ({card.correct_reviews}/{card.total_reviews})"
        )
    
    difficult_text = f"""
🔍 **Самые сложные карточки**

Карточки с наименьшей точностью:

{chr(10).join(cards_list)}

💡 Совет: Повторяйте эти карточки чаще!
"""
    
    keyboard = [
        [InlineKeyboardButton("🎯 Повторить эти карточки", callback_data="sr_review_difficult")],
        [InlineKeyboardButton("🔙 Назад", callback_data="mode_sr_review")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="mode_chat")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        difficult_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
