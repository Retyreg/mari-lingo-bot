"""
Gamification System - Система геймификации для Mari Lingo Bot
Уровни, достижения, XP, ежедневные цели
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ============================================
# КОНФИГУРАЦИЯ СИСТЕМЫ
# ============================================

# Уровни и требуемый XP
LEVELS = {
    1: {"name": "Новичок", "name_mari": "Тӱҥалше", "xp_required": 0, "emoji": "🌱"},
    2: {"name": "Ученик", "name_mari": "Тунемше", "xp_required": 100, "emoji": "📖"},
    3: {"name": "Знаток", "name_mari": "Палыше", "xp_required": 350, "emoji": "📚"},
    4: {"name": "Мастер", "name_mari": "Мастар", "xp_required": 850, "emoji": "⭐"},
    5: {"name": "Эксперт", "name_mari": "Эксперт", "xp_required": 1850, "emoji": "🌟"},
    6: {"name": "Гуру", "name_mari": "Гуру", "xp_required": 3850, "emoji": "👑"},
    7: {"name": "Легенда", "name_mari": "Легенда", "xp_required": 8850, "emoji": "💎"},
}

# Начисление XP за действия
XP_REWARDS = {
    "quiz_correct_answer": 10,      # Правильный ответ в тесте
    "quiz_completed": 25,           # Бонус за завершение теста
    "quiz_perfect": 50,             # Бонус за 100% в тесте
    "flashcard_learned": 5,         # Изучена карточка
    "daily_login": 15,              # Ежедневный вход
    "streak_7_days": 100,           # Бонус за 7 дней подряд
    "streak_30_days": 500,          # Бонус за 30 дней подряд
    "chat_question": 3,             # Задан вопрос в чате
    "daily_goal_completed": 30,     # Все ежедневные цели выполнены
}

# Достижения
ACHIEVEMENTS = {
    "first_steps": {
        "id": "first_steps",
        "name": "Первые шаги",
        "name_mari": "Икымше ошкыл",
        "description": "Пройти первый тест",
        "emoji": "🌱",
        "xp_bonus": 20,
        "condition": lambda stats: stats.get("quizzes_completed", 0) >= 1
    },
    "bookworm": {
        "id": "bookworm",
        "name": "Книжный червь",
        "name_mari": "Книга-тӱня",
        "description": "Изучить 50 слов",
        "emoji": "📚",
        "xp_bonus": 50,
        "condition": lambda stats: stats.get("words_learned", 0) >= 50
    },
    "bookworm_master": {
        "id": "bookworm_master",
        "name": "Библиотекарь",
        "name_mari": "Книгагудо",
        "description": "Изучить 200 слов",
        "emoji": "📖",
        "xp_bonus": 150,
        "condition": lambda stats: stats.get("words_learned", 0) >= 200
    },
    "sniper": {
        "id": "sniper",
        "name": "Снайпер",
        "name_mari": "Снайпер",
        "description": "10 тестов со 100% результатом",
        "emoji": "🎯",
        "xp_bonus": 100,
        "condition": lambda stats: stats.get("perfect_quizzes", 0) >= 10
    },
    "on_fire": {
        "id": "on_fire",
        "name": "В огне",
        "name_mari": "Тул дене",
        "description": "Серия 7 дней подряд",
        "emoji": "🔥",
        "xp_bonus": 75,
        "condition": lambda stats: stats.get("max_streak", 0) >= 7
    },
    "lightning": {
        "id": "lightning",
        "name": "Молния",
        "name_mari": "Волгенче",
        "description": "Серия 30 дней подряд",
        "emoji": "⚡",
        "xp_bonus": 300,
        "condition": lambda stats: stats.get("max_streak", 0) >= 30
    },
    "champion": {
        "id": "champion",
        "name": "Чемпион",
        "name_mari": "Чемпион",
        "description": "Достичь 5 уровня",
        "emoji": "🏆",
        "xp_bonus": 200,
        "condition": lambda stats: stats.get("level", 1) >= 5
    },
    "legend": {
        "id": "legend",
        "name": "Легенда",
        "name_mari": "Легенда",
        "description": "Достичь 7 уровня",
        "emoji": "💎",
        "xp_bonus": 500,
        "condition": lambda stats: stats.get("level", 1) >= 7
    },
    "wise_owl": {
        "id": "wise_owl",
        "name": "Мудрец",
        "name_mari": "Ушанче",
        "description": "500 правильных ответов",
        "emoji": "🦉",
        "xp_bonus": 250,
        "condition": lambda stats: stats.get("correct_answers", 0) >= 500
    },
    "quiz_master": {
        "id": "quiz_master",
        "name": "Мастер тестов",
        "name_mari": "Тест мастар",
        "description": "Пройти 50 тестов",
        "emoji": "🎓",
        "xp_bonus": 150,
        "condition": lambda stats: stats.get("quizzes_completed", 0) >= 50
    },
    "early_bird": {
        "id": "early_bird",
        "name": "Ранняя пташка",
        "name_mari": "Эр кайык",
        "description": "Заниматься 3 дня до 8 утра",
        "emoji": "🐦",
        "xp_bonus": 50,
        "condition": lambda stats: stats.get("early_sessions", 0) >= 3
    },
    "night_owl": {
        "id": "night_owl",
        "name": "Ночная сова",
        "name_mari": "Йӱд тумна",
        "description": "Заниматься 3 дня после 23:00",
        "emoji": "🦉",
        "xp_bonus": 50,
        "condition": lambda stats: stats.get("night_sessions", 0) >= 3
    },
}

# Ежедневные цели
DAILY_GOALS = {
    "complete_quiz": {
        "id": "complete_quiz",
        "name": "Пройти тест",
        "description": "Пройти 1 тест",
        "emoji": "🎯",
        "target": 1,
        "stat_key": "daily_quizzes"
    },
    "learn_cards": {
        "id": "learn_cards",
        "name": "Изучить карточки",
        "description": "Изучить 5 карточек",
        "emoji": "🎴",
        "target": 5,
        "stat_key": "daily_cards"
    },
    "ask_question": {
        "id": "ask_question",
        "name": "Задать вопрос",
        "description": "Задать 1 вопрос боту",
        "emoji": "💬",
        "target": 1,
        "stat_key": "daily_questions"
    },
}


class GamificationSystem:
    """Основной класс системы геймификации"""
    
    def __init__(self, user_id: int, data_path: str = "./user_data"):
        self.user_id = user_id
        self.data_path = Path(data_path)
        self.data_path.mkdir(exist_ok=True)
        self.file_path = self.data_path / f"gamification_{user_id}.json"
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Загрузка данных геймификации пользователя"""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки данных геймификации: {e}")
        
        return self._create_default_data()
    
    def _create_default_data(self) -> Dict:
        """Создание данных по умолчанию"""
        today = datetime.now().date().isoformat()
        return {
            "user_id": self.user_id,
            "created_at": datetime.now().isoformat(),
            
            # XP и уровень
            "xp": 0,
            "level": 1,
            
            # Статистика
            "stats": {
                "correct_answers": 0,
                "total_answers": 0,
                "quizzes_completed": 0,
                "perfect_quizzes": 0,
                "words_learned": 0,
                "cards_viewed": 0,
                "questions_asked": 0,
                "max_streak": 0,
                "current_streak": 0,
                "early_sessions": 0,
                "night_sessions": 0,
            },
            
            # Достижения
            "achievements": [],  # Список ID полученных достижений
            "achievements_notified": [],  # Уже показанные уведомления
            
            # Ежедневная активность
            "daily": {
                "date": today,
                "quizzes": 0,
                "cards": 0,
                "questions": 0,
                "goals_completed": False,
                "login_bonus_claimed": False,
            },
            
            # История серий
            "last_activity_date": today,
            
            # XP история (для графиков)
            "xp_history": [
                {"date": today, "xp": 0}
            ],
        }
    
    def save(self):
        """Сохранение данных"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных геймификации: {e}")
    
    # ============================================
    # XP И УРОВНИ
    # ============================================
    
    def add_xp(self, amount: int, reason: str = "") -> Dict:
        """
        Добавить XP пользователю
        
        Returns:
            Dict с информацией о начислении и возможном повышении уровня
        """
        old_level = self.data["level"]
        old_xp = self.data["xp"]
        
        self.data["xp"] += amount
        
        # Проверяем повышение уровня
        new_level = self._calculate_level(self.data["xp"])
        level_up = new_level > old_level
        
        if level_up:
            self.data["level"] = new_level
        
        # Добавляем в историю XP
        today = datetime.now().date().isoformat()
        if self.data["xp_history"][-1]["date"] == today:
            self.data["xp_history"][-1]["xp"] = self.data["xp"]
        else:
            self.data["xp_history"].append({"date": today, "xp": self.data["xp"]})
        
        # Ограничиваем историю последними 30 днями
        self.data["xp_history"] = self.data["xp_history"][-30:]
        
        self.save()
        
        return {
            "xp_added": amount,
            "reason": reason,
            "old_xp": old_xp,
            "new_xp": self.data["xp"],
            "level_up": level_up,
            "old_level": old_level,
            "new_level": new_level,
            "level_info": LEVELS[new_level],
        }
    
    def _calculate_level(self, xp: int) -> int:
        """Вычислить уровень по XP"""
        level = 1
        for lvl, info in LEVELS.items():
            if xp >= info["xp_required"]:
                level = lvl
        return level
    
    def get_level_info(self) -> Dict:
        """Получить информацию о текущем уровне"""
        current_level = self.data["level"]
        current_xp = self.data["xp"]
        level_info = LEVELS[current_level]
        
        # XP до следующего уровня
        next_level = current_level + 1
        if next_level in LEVELS:
            next_level_info = LEVELS[next_level]
            xp_for_next = next_level_info["xp_required"] - current_xp
            progress_percent = ((current_xp - level_info["xp_required"]) / 
                               (next_level_info["xp_required"] - level_info["xp_required"])) * 100
        else:
            xp_for_next = 0
            progress_percent = 100
        
        return {
            "level": current_level,
            "name": level_info["name"],
            "name_mari": level_info["name_mari"],
            "emoji": level_info["emoji"],
            "xp": current_xp,
            "xp_for_next_level": max(0, xp_for_next),
            "progress_percent": min(100, max(0, progress_percent)),
            "is_max_level": next_level not in LEVELS,
        }
    
    def get_xp_progress_bar(self, width: int = 10) -> str:
        """Генерация визуального прогресс-бара XP"""
        info = self.get_level_info()
        filled = int(info["progress_percent"] / 100 * width)
        empty = width - filled
        return "█" * filled + "░" * empty
    
    # ============================================
    # ДОСТИЖЕНИЯ
    # ============================================
    
    def check_achievements(self) -> List[Dict]:
        """
        Проверить и выдать новые достижения
        
        Returns:
            Список новых достижений
        """
        new_achievements = []
        stats = self._get_stats_for_achievements()
        
        for achievement_id, achievement in ACHIEVEMENTS.items():
            # Пропускаем уже полученные
            if achievement_id in self.data["achievements"]:
                continue
            
            # Проверяем условие
            if achievement["condition"](stats):
                # Выдаём достижение
                self.data["achievements"].append(achievement_id)
                
                # Начисляем бонусный XP
                self.add_xp(achievement["xp_bonus"], f"Достижение: {achievement['name']}")
                
                new_achievements.append({
                    "id": achievement_id,
                    "name": achievement["name"],
                    "name_mari": achievement["name_mari"],
                    "description": achievement["description"],
                    "emoji": achievement["emoji"],
                    "xp_bonus": achievement["xp_bonus"],
                })
        
        if new_achievements:
            self.save()
        
        return new_achievements
    
    def _get_stats_for_achievements(self) -> Dict:
        """Получить статистику для проверки достижений"""
        stats = self.data["stats"].copy()
        stats["level"] = self.data["level"]
        return stats
    
    def get_achievements(self) -> Dict:
        """Получить список всех достижений с их статусом"""
        earned = []
        locked = []
        
        for achievement_id, achievement in ACHIEVEMENTS.items():
            achievement_data = {
                "id": achievement_id,
                "name": achievement["name"],
                "name_mari": achievement["name_mari"],
                "description": achievement["description"],
                "emoji": achievement["emoji"],
                "xp_bonus": achievement["xp_bonus"],
            }
            
            if achievement_id in self.data["achievements"]:
                earned.append(achievement_data)
            else:
                locked.append(achievement_data)
        
        return {
            "earned": earned,
            "locked": locked,
            "total": len(ACHIEVEMENTS),
            "earned_count": len(earned),
        }
    
    # ============================================
    # ЕЖЕДНЕВНЫЕ ЦЕЛИ
    # ============================================
    
    def _check_daily_reset(self):
        """Проверить и сбросить ежедневные данные если нужно"""
        today = datetime.now().date().isoformat()
        
        if self.data["daily"]["date"] != today:
            # Новый день - сбрасываем счётчики
            self.data["daily"] = {
                "date": today,
                "quizzes": 0,
                "cards": 0,
                "questions": 0,
                "goals_completed": False,
                "login_bonus_claimed": False,
            }
            self.save()
    
    def record_daily_activity(self, activity_type: str, count: int = 1) -> Dict:
        """
        Записать ежедневную активность
        
        Args:
            activity_type: "quiz", "card", "question"
            count: количество
        
        Returns:
            Dict с информацией о целях
        """
        self._check_daily_reset()
        
        mapping = {
            "quiz": "quizzes",
            "card": "cards",
            "question": "questions",
        }
        
        if activity_type in mapping:
            self.data["daily"][mapping[activity_type]] += count
        
        # Проверяем выполнение всех целей
        result = self.check_daily_goals()
        self.save()
        
        return result
    
    def check_daily_goals(self) -> Dict:
        """Проверить статус ежедневных целей"""
        self._check_daily_reset()
        
        goals_status = []
        all_completed = True
        
        goal_mapping = {
            "complete_quiz": self.data["daily"]["quizzes"],
            "learn_cards": self.data["daily"]["cards"],
            "ask_question": self.data["daily"]["questions"],
        }
        
        for goal_id, goal in DAILY_GOALS.items():
            current = goal_mapping.get(goal_id, 0)
            target = goal["target"]
            completed = current >= target
            
            if not completed:
                all_completed = False
            
            goals_status.append({
                "id": goal_id,
                "name": goal["name"],
                "emoji": goal["emoji"],
                "current": current,
                "target": target,
                "completed": completed,
                "progress_percent": min(100, (current / target) * 100),
            })
        
        # Бонус за выполнение всех целей
        bonus_awarded = False
        if all_completed and not self.data["daily"]["goals_completed"]:
            self.data["daily"]["goals_completed"] = True
            self.add_xp(XP_REWARDS["daily_goal_completed"], "Все ежедневные цели выполнены")
            bonus_awarded = True
            self.save()
        
        return {
            "goals": goals_status,
            "all_completed": all_completed,
            "bonus_awarded": bonus_awarded,
            "bonus_xp": XP_REWARDS["daily_goal_completed"] if bonus_awarded else 0,
        }
    
    # ============================================
    # СЕРИИ (STREAKS)
    # ============================================
    
    def update_streak(self) -> Dict:
        """Обновить серию дней"""
        today = datetime.now().date()
        last_activity = datetime.fromisoformat(self.data["last_activity_date"]).date()
        
        delta = (today - last_activity).days
        
        streak_broken = False
        streak_bonus = None
        
        if delta == 0:
            # Уже заходил сегодня
            pass
        elif delta == 1:
            # Продолжение серии
            self.data["stats"]["current_streak"] += 1
            
            # Обновляем максимальную серию
            if self.data["stats"]["current_streak"] > self.data["stats"]["max_streak"]:
                self.data["stats"]["max_streak"] = self.data["stats"]["current_streak"]
            
            # Проверяем бонусы за серию
            streak = self.data["stats"]["current_streak"]
            if streak == 7:
                self.add_xp(XP_REWARDS["streak_7_days"], "Серия 7 дней")
                streak_bonus = {"days": 7, "xp": XP_REWARDS["streak_7_days"]}
            elif streak == 30:
                self.add_xp(XP_REWARDS["streak_30_days"], "Серия 30 дней")
                streak_bonus = {"days": 30, "xp": XP_REWARDS["streak_30_days"]}
        else:
            # Серия прервана
            streak_broken = True
            self.data["stats"]["current_streak"] = 1
        
        self.data["last_activity_date"] = today.isoformat()
        self.save()
        
        return {
            "current_streak": self.data["stats"]["current_streak"],
            "max_streak": self.data["stats"]["max_streak"],
            "streak_broken": streak_broken,
            "streak_bonus": streak_bonus,
        }
    
    def claim_daily_login_bonus(self) -> Dict:
        """Получить бонус за ежедневный вход"""
        self._check_daily_reset()
        
        if self.data["daily"]["login_bonus_claimed"]:
            return {
                "claimed": False,
                "reason": "already_claimed",
                "xp": 0,
            }
        
        self.data["daily"]["login_bonus_claimed"] = True
        xp_result = self.add_xp(XP_REWARDS["daily_login"], "Ежедневный вход")
        
        # Обновляем серию
        streak_result = self.update_streak()
        
        # Проверяем время для достижений
        hour = datetime.now().hour
        if hour < 8:
            self.data["stats"]["early_sessions"] += 1
        elif hour >= 23:
            self.data["stats"]["night_sessions"] += 1
        
        self.save()
        
        return {
            "claimed": True,
            "xp": XP_REWARDS["daily_login"],
            "streak": streak_result,
            "level_up": xp_result["level_up"],
        }
    
    # ============================================
    # ЗАПИСЬ СОБЫТИЙ
    # ============================================
    
    def record_quiz_completed(self, correct: int, total: int) -> Dict:
        """Записать прохождение теста"""
        self.data["stats"]["quizzes_completed"] += 1
        self.data["stats"]["correct_answers"] += correct
        self.data["stats"]["total_answers"] += total
        
        # XP за правильные ответы
        xp_earned = correct * XP_REWARDS["quiz_correct_answer"]
        
        # Бонус за завершение
        xp_earned += XP_REWARDS["quiz_completed"]
        
        # Бонус за идеальный результат
        is_perfect = correct == total
        if is_perfect:
            self.data["stats"]["perfect_quizzes"] += 1
            xp_earned += XP_REWARDS["quiz_perfect"]
        
        xp_result = self.add_xp(xp_earned, "Тест завершён")
        
        # Записываем в ежедневную активность
        self.record_daily_activity("quiz")
        
        # Проверяем достижения
        new_achievements = self.check_achievements()
        
        self.save()
        
        return {
            "xp_earned": xp_earned,
            "is_perfect": is_perfect,
            "level_up": xp_result["level_up"],
            "new_level": xp_result["new_level"] if xp_result["level_up"] else None,
            "new_achievements": new_achievements,
            "daily_goals": self.check_daily_goals(),
        }
    
    def record_flashcard_learned(self, word: str) -> Dict:
        """Записать изучение карточки"""
        self.data["stats"]["cards_viewed"] += 1
        self.data["stats"]["words_learned"] += 1
        
        xp_result = self.add_xp(XP_REWARDS["flashcard_learned"], "Карточка изучена")
        
        # Записываем в ежедневную активность
        self.record_daily_activity("card")
        
        # Проверяем достижения
        new_achievements = self.check_achievements()
        
        self.save()
        
        return {
            "xp_earned": XP_REWARDS["flashcard_learned"],
            "level_up": xp_result["level_up"],
            "new_achievements": new_achievements,
        }
    
    def record_chat_question(self) -> Dict:
        """Записать вопрос в чате"""
        self.data["stats"]["questions_asked"] += 1
        
        xp_result = self.add_xp(XP_REWARDS["chat_question"], "Вопрос в чате")
        
        # Записываем в ежедневную активность
        self.record_daily_activity("question")
        
        self.save()
        
        return {
            "xp_earned": XP_REWARDS["chat_question"],
            "level_up": xp_result["level_up"],
        }
    
    # ============================================
    # ФОРМАТИРОВАНИЕ ДЛЯ ОТОБРАЖЕНИЯ
    # ============================================
    
    def get_profile_summary(self) -> str:
        """Получить сводку профиля для отображения"""
        level_info = self.get_level_info()
        stats = self.data["stats"]
        achievements = self.get_achievements()
        
        progress_bar = self.get_xp_progress_bar(10)
        
        summary = f"""
{level_info['emoji']} **Уровень {level_info['level']}: {level_info['name']}**
*({level_info['name_mari']})*

**XP:** {level_info['xp']} {'/ ' + str(level_info['xp'] + level_info['xp_for_next_level']) if not level_info['is_max_level'] else '(MAX)'}
[{progress_bar}] {level_info['progress_percent']:.0f}%

🔥 **Серия:** {stats['current_streak']} дн. (макс: {stats['max_streak']})

📊 **Статистика:**
• Тестов пройдено: {stats['quizzes_completed']}
• Правильных ответов: {stats['correct_answers']}
• Слов изучено: {stats['words_learned']}
• Идеальных тестов: {stats['perfect_quizzes']}

🏆 **Достижения:** {achievements['earned_count']}/{achievements['total']}
"""
        return summary
    
    def get_daily_goals_summary(self) -> str:
        """Получить сводку ежедневных целей"""
        goals = self.check_daily_goals()
        
        lines = ["📋 **Ежедневные цели:**\n"]
        
        for goal in goals["goals"]:
            status = "✅" if goal["completed"] else "⬜"
            lines.append(f"{status} {goal['emoji']} {goal['name']}: {goal['current']}/{goal['target']}")
        
        if goals["all_completed"]:
            lines.append(f"\n🎉 **Все цели выполнены!** +{XP_REWARDS['daily_goal_completed']} XP")
        
        return "\n".join(lines)
    
    def get_achievements_summary(self) -> str:
        """Получить сводку достижений"""
        achievements = self.get_achievements()
        
        lines = [f"🏆 **Достижения** ({achievements['earned_count']}/{achievements['total']})\n"]
        
        if achievements["earned"]:
            lines.append("**Получено:**")
            for a in achievements["earned"]:
                lines.append(f"{a['emoji']} {a['name']} — *{a['description']}*")
        
        lines.append("")
        
        if achievements["locked"]:
            lines.append("**Заблокировано:**")
            for a in achievements["locked"][:5]:  # Показываем только 5
                lines.append(f"🔒 {a['name']} — *{a['description']}*")
            
            if len(achievements["locked"]) > 5:
                lines.append(f"... и ещё {len(achievements['locked']) - 5}")
        
        return "\n".join(lines)
    
    def format_level_up_message(self, old_level: int, new_level: int) -> str:
        """Форматировать сообщение о повышении уровня"""
        new_info = LEVELS[new_level]
        
        return f"""
🎉🎉🎉

**НОВЫЙ УРОВЕНЬ!**

{new_info['emoji']} **Уровень {new_level}: {new_info['name']}**
*({new_info['name_mari']})*

Поздравляем с достижением!
Продолжай в том же духе! 💪

🎉🎉🎉
"""
    
    def format_achievement_message(self, achievement: Dict) -> str:
        """Форматировать сообщение о достижении"""
        return f"""
🏆 **ДОСТИЖЕНИЕ ПОЛУЧЕНО!**

{achievement['emoji']} **{achievement['name']}**
*({achievement['name_mari']})*

{achievement['description']}

+{achievement['xp_bonus']} XP бонус! ⭐
"""


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def get_leaderboard(data_path: str = "./user_data", limit: int = 10) -> List[Dict]:
    """
    Получить таблицу лидеров
    
    Args:
        data_path: путь к данным пользователей
        limit: количество записей
    
    Returns:
        Список лидеров
    """
    data_path = Path(data_path)
    leaderboard = []
    
    for file_path in data_path.glob("gamification_*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                leaderboard.append({
                    "user_id": data["user_id"],
                    "xp": data["xp"],
                    "level": data["level"],
                    "level_name": LEVELS[data["level"]]["name"],
                    "level_emoji": LEVELS[data["level"]]["emoji"],
                    "achievements": len(data["achievements"]),
                })
        except Exception:
            continue
    
    # Сортируем по XP
    leaderboard.sort(key=lambda x: x["xp"], reverse=True)
    
    return leaderboard[:limit]


def format_leaderboard(leaderboard: List[Dict]) -> str:
    """Форматировать таблицу лидеров"""
    if not leaderboard:
        return "🏆 **Таблица лидеров пуста**"
    
    lines = ["🏆 **Таблица лидеров**\n"]
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, entry in enumerate(leaderboard):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(
            f"{medal} {entry['level_emoji']} Ур.{entry['level']} — "
            f"{entry['xp']} XP — 🏆{entry['achievements']}"
        )
    
    return "\n".join(lines)
