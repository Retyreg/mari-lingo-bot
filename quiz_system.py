"""
Quiz System - Система тестов и викторин для Mari Lingo Bot
Улучшенная версия с валидацией
"""

import json
import random
from typing import Dict, List, Optional
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class QuizGenerator:
    """Генератор тестов на основе RAG базы и Groq AI"""
    
    def __init__(self, rag_searcher, groq_client):
        self.rag_searcher = rag_searcher
        self.groq_client = groq_client
        self.question_types = [
            "translation_to_russian",
            "translation_to_mari",
        ]
        self.used_words = set()  # Для избежания повторов
    
    def generate_question(self, difficulty: str = "medium", question_type: str = None) -> Dict:
        """Генерация одного вопроса"""
        if question_type is None:
            question_type = random.choice(self.question_types)
        
        try:
            if question_type == "translation_to_russian":
                return self._generate_translation_question(to_russian=True, difficulty=difficulty)
            elif question_type == "translation_to_mari":
                return self._generate_translation_question(to_russian=False, difficulty=difficulty)
            else:
                return self._generate_translation_question(to_russian=True, difficulty=difficulty)
        except Exception as e:
            logger.error(f"Ошибка генерации вопроса: {e}")
            return self._generate_fallback_question()
    
    def _get_rag_context(self, query: str, n_results: int = 3) -> str:
        """Получение контекста из RAG базы"""
        import io
        import contextlib
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            results = self.rag_searcher.search(query, n_results=n_results)
        
        if results and results.get('documents') and results['documents'][0]:
            # Объединяем несколько результатов для разнообразия
            texts = []
            for doc in results['documents'][0]:
                texts.append(doc[:800])
            return "\n---\n".join(texts)
        return ""
    
    def _generate_translation_question(self, to_russian: bool, difficulty: str) -> Dict:
        """Генерация вопроса на перевод слов"""
        
        # Разные запросы для разнообразия
        queries = [
            "марийский словарь слова перевод",
            "марийские существительные",
            "марийские глаголы",
            "марийские прилагательные",
            "базовые марийские слова"
        ]
        context = self._get_rag_context(random.choice(queries))
        
        if not context:
            return self._generate_fallback_question()
        
        if to_russian:
            prompt = f"""Из этого словаря выбери ОДНО марийское слово и создай вопрос на перевод.

Словарь:
{context}

ЗАДАЧА: Создай вопрос "Как переводится марийское слово X?" где X - марийское слово.
Все 4 варианта ответа должны быть на РУССКОМ языке.

Верни ТОЛЬКО JSON:
{{"question": "Как переводится марийское слово [марийское]?", "correct_answer": "[русский перевод]", "options": ["[русский1]", "[русский2]", "[русский3]", "[русский4]"], "explanation": "[марийское] = [русское]"}}

Пример правильного ответа:
{{"question": "Как переводится марийское слово шӱкаш?", "correct_answer": "толкать", "options": ["толкать", "бежать", "идти", "стоять"], "explanation": "шӱкаш = толкать"}}"""

        else:
            prompt = f"""Из этого словаря выбери ОДНО русское слово и создай вопрос на перевод.

Словарь:
{context}

ЗАДАЧА: Создай вопрос "Как сказать X на марийском?" где X - русское слово.
Все 4 варианта ответа должны быть на МАРИЙСКОМ языке (с буквами ӱ, ӧ, ӓ, ӹ если нужно).

Верни ТОЛЬКО JSON:
{{"question": "Как сказать [русское] на марийском?", "correct_answer": "[марийский перевод]", "options": ["[марийский1]", "[марийский2]", "[марийский3]", "[марийский4]"], "explanation": "[русское] = [марийское]"}}

Пример правильного ответа:
{{"question": "Как сказать толкать на марийском?", "correct_answer": "шӱкаш", "options": ["шӱкаш", "кошташ", "ошкылаш", "шогаш"], "explanation": "толкать = шӱкаш"}}"""

        try:
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.8,
                max_tokens=400,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Очищаем от markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Находим JSON в ответе
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group()
            
            question_data = json.loads(content)
            
            # Валидация
            if not self._validate_question(question_data, to_russian):
                logger.warning("Вопрос не прошёл валидацию, используем fallback")
                return self._generate_fallback_question()
            
            # Добавляем слово в использованные
            word = question_data["correct_answer"]
            self.used_words.add(word.lower())
            
            # Перемешиваем варианты
            random.shuffle(question_data["options"])
            
            question_data["type"] = "translation"
            question_data["difficulty"] = difficulty
            
            return question_data
            
        except Exception as e:
            logger.error(f"Ошибка парсинга вопроса: {e}")
            return self._generate_fallback_question()
    
    def _validate_question(self, question_data: Dict, to_russian: bool) -> bool:
        """Валидация сгенерированного вопроса"""
        try:
            # Проверяем наличие всех полей
            required = ["question", "correct_answer", "options", "explanation"]
            for field in required:
                if field not in question_data:
                    return False
            
            # Проверяем что есть 4 варианта
            if len(question_data["options"]) != 4:
                return False
            
            # Проверяем что правильный ответ в вариантах
            if question_data["correct_answer"] not in question_data["options"]:
                return False
            
            # Для вопросов "на русский" - ответы должны быть русскими словами
            if to_russian:
                for opt in question_data["options"]:
                    # Если есть марийские буквы - это неправильно
                    if any(c in opt for c in "ӱӧӓӹ"):
                        return False
            
            return True
            
        except Exception:
            return False
    
    def _generate_fallback_question(self) -> Dict:
        """Резервные вопросы - гарантированно правильные"""
        fallback_questions = [
            # Вопросы: марийский -> русский
            {
                "question": "Как переводится марийское слово салам?",
                "correct_answer": "привет",
                "options": ["привет", "пока", "спасибо", "извини"],
                "explanation": "салам = привет",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как переводится марийское слово тау?",
                "correct_answer": "спасибо",
                "options": ["спасибо", "привет", "пока", "здравствуй"],
                "explanation": "тау = спасибо",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как переводится марийское слово вӱд?",
                "correct_answer": "вода",
                "options": ["вода", "хлеб", "мясо", "молоко"],
                "explanation": "вӱд = вода",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как переводится марийское слово кинде?",
                "correct_answer": "хлеб",
                "options": ["хлеб", "вода", "мясо", "соль"],
                "explanation": "кинде = хлеб",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как переводится марийское слово пӧрт?",
                "correct_answer": "дом",
                "options": ["дом", "лес", "река", "поле"],
                "explanation": "пӧрт = дом",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как переводится марийское слово кече?",
                "correct_answer": "солнце",
                "options": ["солнце", "луна", "звезда", "небо"],
                "explanation": "кече = солнце",
                "type": "translation",
                "difficulty": "medium"
            },
            {
                "question": "Как переводится марийское слово мланде?",
                "correct_answer": "земля",
                "options": ["земля", "небо", "вода", "огонь"],
                "explanation": "мланде = земля",
                "type": "translation",
                "difficulty": "medium"
            },
            {
                "question": "Как переводится марийское слово чодыра?",
                "correct_answer": "лес",
                "options": ["лес", "поле", "река", "гора"],
                "explanation": "чодыра = лес",
                "type": "translation",
                "difficulty": "medium"
            },
            # Вопросы: русский -> марийский
            {
                "question": "Как сказать привет на марийском?",
                "correct_answer": "салам",
                "options": ["салам", "тау", "чеверын", "поро"],
                "explanation": "привет = салам",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как сказать спасибо на марийском?",
                "correct_answer": "тау",
                "options": ["тау", "салам", "поро", "чеверын"],
                "explanation": "спасибо = тау",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как сказать вода на марийском?",
                "correct_answer": "вӱд",
                "options": ["вӱд", "кинде", "шыл", "пӧрт"],
                "explanation": "вода = вӱд",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как сказать хлеб на марийском?",
                "correct_answer": "кинде",
                "options": ["кинде", "вӱд", "шыл", "шӧр"],
                "explanation": "хлеб = кинде",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как сказать дом на марийском?",
                "correct_answer": "пӧрт",
                "options": ["пӧрт", "чодыра", "эҥер", "курык"],
                "explanation": "дом = пӧрт",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как сказать солнце на марийском?",
                "correct_answer": "кече",
                "options": ["кече", "тылзе", "шӱдыр", "каваш"],
                "explanation": "солнце = кече",
                "type": "translation",
                "difficulty": "medium"
            },
            {
                "question": "Как сказать лес на марийском?",
                "correct_answer": "чодыра",
                "options": ["чодыра", "пасу", "эҥер", "курык"],
                "explanation": "лес = чодыра",
                "type": "translation",
                "difficulty": "medium"
            },
            {
                "question": "Как сказать мать на марийском?",
                "correct_answer": "ава",
                "options": ["ава", "ача", "коча", "кува"],
                "explanation": "мать = ава",
                "type": "translation",
                "difficulty": "easy"
            },
        ]
        
        # Выбираем вопрос, который ещё не использовался
        available = [q for q in fallback_questions if q["correct_answer"].lower() not in self.used_words]
        
        if not available:
            # Если все использованы, очищаем и начинаем заново
            self.used_words.clear()
            available = fallback_questions
        
        question = random.choice(available)
        self.used_words.add(question["correct_answer"].lower())
        
        # Перемешиваем варианты
        options = question["options"].copy()
        random.shuffle(options)
        question["options"] = options
        
        return question
    
    def generate_quiz(self, num_questions: int = 5, difficulty: str = "medium") -> List[Dict]:
        """Генерация полного теста"""
        # Очищаем использованные слова для нового теста
        self.used_words.clear()
        
        questions = []
        
        for i in range(num_questions):
            # Чередуем типы вопросов
            question_type = self.question_types[i % len(self.question_types)]
            question = self.generate_question(difficulty=difficulty, question_type=question_type)
            questions.append(question)
        
        return questions


class QuizSession:
    """Класс для управления сессией теста"""
    
    def __init__(self, user_id: int, questions: List[Dict]):
        self.user_id = user_id
        self.questions = questions
        self.current_question_index = 0
        self.answers = []
        self.score = 0
        self.start_time = datetime.now()
        self.end_time = None
    
    def get_current_question(self) -> Optional[Dict]:
        """Получить текущий вопрос"""
        if self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None
    
    def submit_answer(self, answer: str) -> Dict:
        """Отправить ответ на текущий вопрос"""
        current_question = self.get_current_question()
        
        if not current_question:
            return {"error": "Нет активного вопроса"}
        
        is_correct = answer == current_question["correct_answer"]
        
        if is_correct:
            self.score += 1
        
        result = {
            "correct": is_correct,
            "user_answer": answer,
            "correct_answer": current_question["correct_answer"],
            "explanation": current_question.get("explanation", ""),
            "score": self.score,
            "total": len(self.questions)
        }
        
        self.answers.append(result)
        self.current_question_index += 1
        
        return result
    
    def is_finished(self) -> bool:
        """Проверка завершения теста"""
        return self.current_question_index >= len(self.questions)
    
    def get_final_results(self) -> Dict:
        """Получить итоговые результаты"""
        if not self.is_finished():
            return {"error": "Тест еще не завершен"}
        
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        percentage = (self.score / len(self.questions)) * 100
        
        if percentage >= 90:
            level = "Отлично! 🌟"
        elif percentage >= 70:
            level = "Хорошо! 👍"
        elif percentage >= 50:
            level = "Неплохо! 💪"
        else:
            level = "Нужно практиковаться! 📚"
        
        return {
            "score": self.score,
            "total": len(self.questions),
            "percentage": percentage,
            "level": level,
            "duration_seconds": int(duration),
            "answers": self.answers,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_progress(self) -> str:
        """Получить прогресс"""
        return f"{self.current_question_index + 1}/{len(self.questions)}"
