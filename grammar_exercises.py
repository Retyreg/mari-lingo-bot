"""
Grammar Exercises - Грамматические упражнения для Mari Lingo Bot

В отличие от quiz_system.py (который генерирует вопросы через Groq на
лету), здесь используется ЗАРАНЕЕ ПРОВЕРЕННЫЙ статический банк. Причина:
эти упражнения требуют не перевода слова, а правильного выбора падежной/
глагольной формы — а это заведомо сложнее для LLM, чем перевод (модель
уже ошибалась даже в простых переводах, см. историю тестов). Поэтому
корректный ответ на каждое упражнение взят дословно из официального
"Exercise key" учебника, а не сгенерирован моделью.

Источник: Riese, T., Bradley, J., Yefremova, T. — "Mari: An Essential
Grammar for International Learners" (2022), Department of Finno-Ugric
Studies, University of Vienna. Публикуется под лицензией
CC BY-SA 3.0 Unported.
"""

import random
from typing import Dict, List, Optional
from datetime import datetime


# Каждый пункт: номер упражнения из учебника (для атрибуции), тема,
# предложение с пропуском "…", варианты (2-3, как даны в скобках в
# оригинале) и правильный ответ — сверен вручную с разделом Exercise key.
GRAMMAR_EXERCISES: List[Dict] = [
    # 7.154 — выбор глагола: непереходный/возвратный vs. побудительный (каузатив)
    {
        "source": "eg2022, упр. 7.154", "topic": "глаголы (переходность)",
        "sentence": "Ме тошкалтыш дене куржын (воленна/волтенна).",
        "options": ["воленна", "волтенна"], "correct_answer": "воленна",
    },
    {
        "source": "eg2022, упр. 7.154", "topic": "глаголы (переходность)",
        "sentence": "Рвезе имньыжым эҥер деке вӱден (мийыш/намийыш).",
        "options": ["мийыш", "намийыш"], "correct_answer": "намийыш",
    },
    {
        "source": "eg2022, упр. 7.154", "topic": "глаголы (переходность)",
        "sentence": "Самолёт кавашке чоҥештен (кӱзен/кӱзыктен).",
        "options": ["кӱзен", "кӱзыктен"], "correct_answer": "кӱзен",
    },
    {
        "source": "eg2022, упр. 7.154", "topic": "глаголы (переходность)",
        "sentence": "Тудым адак паша гыч поктен (лектыныт/луктыныт).",
        "options": ["лектыныт", "луктыныт"], "correct_answer": "луктыныт",
    },
    {
        "source": "eg2022, упр. 7.154", "topic": "глаголы (переходность)",
        "sentence": "Кишке кудывечышкына нушкын (пурен/пуртен).",
        "options": ["пурен", "пуртен"], "correct_answer": "пурен",
    },

    # 3.4 — краткая vs. полная форма прилагательного (пункты с суффиксами
    # исключены — оставлены только те, где ответ совпадает буквально с
    # одним из двух вариантов в скобках)
    {
        "source": "eg2022, упр. 3.4", "topic": "прилагательные (краткая/полная форма)",
        "sentence": "Марий калык поснак … тӱсым йӧрата. (ош/ошо)",
        "options": ["ош", "ошо"], "correct_answer": "ош",
    },
    {
        "source": "eg2022, упр. 3.4", "topic": "прилагательные (краткая/полная форма)",
        "sentence": "Кеҥежым шудо …, а шыжым нарынче. (ужар/ужарге)",
        "options": ["ужар", "ужарге"], "correct_answer": "ужарге",
    },
    {
        "source": "eg2022, упр. 3.4", "topic": "прилагательные (краткая/полная форма)",
        "sentence": "… неран туфльым кызыт огыт чий. (кошар/кошарге)",
        "options": ["кошар", "кошарге"], "correct_answer": "кошар",
    },
    {
        "source": "eg2022, упр. 3.4", "topic": "прилагательные (краткая/полная форма)",
        "sentence": "Телым уремыште чыла … . (ош/ошо)",
        "options": ["ош", "ошо"], "correct_answer": "ошо",
    },
    {
        "source": "eg2022, упр. 3.4", "topic": "прилагательные (краткая/полная форма)",
        "sentence": "Китай календарь почеш 2017-ше ий – тиде … агытанын ийже. (йошкар/йошкарге)",
        "options": ["йошкар", "йошкарге"], "correct_answer": "йошкар",
    },
    {
        "source": "eg2022, упр. 3.4", "topic": "прилагательные (краткая/полная форма)",
        "sentence": "Тиде курчак мотор огыл: нерже пеш … . (кошар/кошарге)",
        "options": ["кошар", "кошарге"], "correct_answer": "кошарге",
    },
    {
        "source": "eg2022, упр. 3.4", "topic": "прилагательные (краткая/полная форма)",
        "sentence": "Тыйын … костюмет уло мо? (шем/шеме)",
        "options": ["шем", "шеме"], "correct_answer": "шем",
    },
    {
        "source": "eg2022, упр. 3.4", "topic": "прилагательные (краткая/полная форма)",
        "sentence": "Тый … чайым йӱат але шемым? (ужар/ужарге)",
        "options": ["ужар", "ужарге"], "correct_answer": "ужар",
    },

    # 4.13 — именная vs. наречная форма названия дня недели
    {
        "source": "eg2022, упр. 4.13", "topic": "дни недели (форма)",
        "sentence": "… кастене мом ыштет? Айда марий спектакльыш каена! (шуматкече/шуматкечын)",
        "options": ["шуматкече", "шуматкечын"], "correct_answer": "шуматкечын",
    },
    {
        "source": "eg2022, упр. 4.13", "topic": "дни недели (форма)",
        "sentence": "Арнян кокымшо кечыже марла … маналтеш. (кушкыжмо/кушкыжмын)",
        "options": ["кушкыжмо", "кушкыжмын"], "correct_answer": "кушкыжмо",
    },
    {
        "source": "eg2022, упр. 4.13", "topic": "дни недели (форма)",
        "sentence": "… гыч эр еда куржталаш тӱҥалына. (шочмо/шочмын)",
        "options": ["шочмо", "шочмын"], "correct_answer": "шочмо",
    },
    {
        "source": "eg2022, упр. 4.13", "topic": "дни недели (форма)",
        "sentence": "… мый индеше марте мален кертам. (рушарня/рушарнян)",
        "options": ["рушарня", "рушарнян"], "correct_answer": "рушарнян",
    },
    {
        "source": "eg2022, упр. 4.13", "topic": "дни недели (форма)",
        "sentence": "Эн йӧратыме кечем – … . (кугарня/кугарнян)",
        "options": ["кугарня", "кугарнян"], "correct_answer": "кугарня",
    },

    # 10.22 — отымённое прилагательное (выбор подходящего суффикса-варианта)
    {
        "source": "eg2022, упр. 10.22", "topic": "отымённые прилагательные",
        "sentence": "Пакчаштына тӱрлӧ … шудо кушкеш. (чаян/чайысе/чайлык)",
        "options": ["чаян", "чайысе", "чайлык"], "correct_answer": "чайлык",
    },
    {
        "source": "eg2022, упр. 10.22", "topic": "отымённые прилагательные",
        "sentence": "Ме … тортым нигунам она нал: авай эре шке ышта. (кевытан/кевытысе/кевытлык)",
        "options": ["кевытан", "кевытысе", "кевытлык"], "correct_answer": "кевытысе",
    },
    {
        "source": "eg2022, упр. 10.22", "topic": "отымённые прилагательные",
        "sentence": "Йолташем Индий гыч сылне … материалым конден. (тувыран/тувырысо/тувырлык)",
        "options": ["тувыран", "тувырысо", "тувырлык"], "correct_answer": "тувырлык",
    },
    {
        "source": "eg2022, упр. 10.22", "topic": "отымённые прилагательные",
        "sentence": "Самырык серызе оҥай … романым возен. (сюжетан/сюжетысе/сюжетлык)",
        "options": ["сюжетан", "сюжетысе", "сюжетлык"], "correct_answer": "сюжетан",
    },
    {
        "source": "eg2022, упр. 10.22", "topic": "отымённые прилагательные",
        "sentence": "Чодыраште кок … поҥгым погенам. (шӱран/шӱрысӧ/шӱрлык)",
        "options": ["шӱран", "шӱрысӧ", "шӱрлык"], "correct_answer": "шӱрлык",
    },
]


def get_topics() -> List[str]:
    return sorted({ex["topic"] for ex in GRAMMAR_EXERCISES})


def generate_exercise_set(num_exercises: int = 5, topic: Optional[str] = None) -> List[Dict]:
    """Выбрать набор упражнений (без повторов, пока хватает уникальных)"""
    pool = [ex for ex in GRAMMAR_EXERCISES if topic is None or ex["topic"] == topic]
    if not pool:
        pool = GRAMMAR_EXERCISES

    if num_exercises >= len(pool):
        chosen = pool.copy()
        random.shuffle(chosen)
        return chosen

    return random.sample(pool, num_exercises)


class ExerciseSession:
    """Сессия прохождения набора грамматических упражнений (аналог QuizSession)"""

    def __init__(self, user_id: int, exercises: List[Dict]):
        self.user_id = user_id
        self.exercises = exercises
        self.current_index = 0
        self.answers: List[Dict] = []
        self.score = 0
        self.start_time = datetime.now()

    def get_current_exercise(self) -> Optional[Dict]:
        if self.current_index < len(self.exercises):
            return self.exercises[self.current_index]
        return None

    def submit_answer(self, answer: str) -> Dict:
        current = self.get_current_exercise()
        if not current:
            return {"error": "Нет активного упражнения"}

        is_correct = answer == current["correct_answer"]
        if is_correct:
            self.score += 1

        result = {
            "correct": is_correct,
            "user_answer": answer,
            "correct_answer": current["correct_answer"],
            "sentence": current["sentence"],
            "source": current["source"],
            "score": self.score,
            "total": len(self.exercises),
        }

        self.answers.append(result)
        self.current_index += 1
        return result

    def is_finished(self) -> bool:
        return self.current_index >= len(self.exercises)

    def get_progress(self) -> str:
        return f"{self.current_index + 1}/{len(self.exercises)}"

    def get_final_results(self) -> Dict:
        duration = (datetime.now() - self.start_time).total_seconds()
        percentage = (self.score / len(self.exercises)) * 100 if self.exercises else 0

        if percentage >= 90:
            level = "Отлично! 🌟"
        elif percentage >= 70:
            level = "Хорошо! 👍"
        elif percentage >= 50:
            level = "Неплохо! 💪"
        else:
            level = "Нужно повторить правило! 📚"

        return {
            "score": self.score,
            "total": len(self.exercises),
            "percentage": percentage,
            "level": level,
            "duration_seconds": int(duration),
        }
