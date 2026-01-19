"""
Quiz System - Система тестов и викторин для Mari Lingo Bot
Автоматическая генерация вопросов из RAG базы
"""

import json
import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class QuizGenerator:
    """Генератор тестов на основе RAG базы и Groq AI"""
    
    def __init__(self, rag_searcher, groq_client):
        self.rag_searcher = rag_searcher
        self.groq_client = groq_client
        self.question_types = [
            "translation_to_russian",
            "translation_to_mari",
            "multiple_choice",
            "fill_blank",
            "grammar"
        ]
    
    def generate_question(self, difficulty: str = "medium", question_type: str = None) -> Dict:
        """
        Генерация одного вопроса
        
        Args:
            difficulty: easy, medium, hard
            question_type: тип вопроса или None для случайного
            
        Returns:
            Dict с вопросом, вариантами ответов и правильным ответом
        """
        if question_type is None:
            question_type = random.choice(self.question_types)
        
        try:
            if question_type == "translation_to_russian":
                return self._generate_translation_question(to_russian=True, difficulty=difficulty)
            elif question_type == "translation_to_mari":
                return self._generate_translation_question(to_russian=False, difficulty=difficulty)
            elif question_type == "multiple_choice":
                return self._generate_multiple_choice_question(difficulty=difficulty)
            elif question_type == "fill_blank":
                return self._generate_fill_blank_question(difficulty=difficulty)
            elif question_type == "grammar":
                return self._generate_grammar_question(difficulty=difficulty)
            else:
                return self._generate_multiple_choice_question(difficulty=difficulty)
        except Exception as e:
            logger.error(f"Ошибка генерации вопроса: {e}")
            return self._generate_fallback_question()
    
    def _get_rag_context(self, query: str, n_results: int = 2) -> str:
        """Получение контекста из RAG базы без вывода в консоль"""
        import io
        import contextlib
        
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            results = self.rag_searcher.search(query, n_results=n_results)
        
        if results and results.get('documents') and results['documents'][0]:
            return results['documents'][0][0][:1000]
        return ""
    
    def _generate_translation_question(self, to_russian: bool, difficulty: str) -> Dict:
        """Генерация вопроса на перевод"""
        
        # Получаем контекст с марийскими словами
        context = self._get_rag_context("марийские слова перевод")
        
        if not context:
            return self._generate_fallback_question()
        
        prompt = f"""На основе этого текста о марийском языке, создай вопрос на перевод.

Текст: {context}

Создай вопрос уровня {difficulty}:
- easy: простые базовые слова (привет, спасибо, да, нет)
- medium: обычные слова (семья, дом, еда)
- hard: сложные слова и выражения

Формат ответа (строго JSON):
{{
    "question": "{'Как переводится на русский' if to_russian else 'Как переводится на марийский'}: [слово]?",
    "correct_answer": "[правильный ответ]",
    "options": ["[вариант 1]", "[вариант 2]", "[вариант 3]", "[вариант 4]"],
    "explanation": "[краткое объяснение]"
}}

ВАЖНО: 
- Используй только слова из предоставленного текста
- Все 4 варианта должны быть правдоподобными
- Правильный ответ должен быть среди options
- Ответ ТОЛЬКО в формате JSON, без дополнительного текста"""

        try:
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Удаляем markdown форматирование если есть
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            question_data = json.loads(content)
            
            # Перемешиваем варианты ответов
            random.shuffle(question_data["options"])
            
            question_data["type"] = "translation"
            question_data["difficulty"] = difficulty
            
            return question_data
            
        except Exception as e:
            logger.error(f"Ошибка парсинга вопроса: {e}")
            return self._generate_fallback_question()
    
    def _generate_multiple_choice_question(self, difficulty: str) -> Dict:
        """Генерация вопроса с множественным выбором"""
        
        context = self._get_rag_context("марийский язык грамматика культура")
        
        if not context:
            return self._generate_fallback_question()
        
        prompt = f"""На основе этого текста о марийском языке, создай вопрос с множественным выбором.

Текст: {context}

Уровень: {difficulty}
- easy: базовые факты
- medium: средняя сложность
- hard: детальные знания

Формат ответа (строго JSON):
{{
    "question": "[вопрос о марийском языке или культуре]",
    "correct_answer": "[правильный ответ]",
    "options": ["[вариант 1]", "[вариант 2]", "[вариант 3]", "[вариант 4]"],
    "explanation": "[объяснение с фактами]"
}}

ВАЖНО:
- Вопрос должен быть основан на предоставленном тексте
- Все варианты должны быть правдоподобными
- Ответ ТОЛЬКО в формате JSON"""

        try:
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content.strip()
            
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            question_data = json.loads(content)
            random.shuffle(question_data["options"])
            
            question_data["type"] = "multiple_choice"
            question_data["difficulty"] = difficulty
            
            return question_data
            
        except Exception as e:
            logger.error(f"Ошибка генерации вопроса: {e}")
            return self._generate_fallback_question()
    
    def _generate_fill_blank_question(self, difficulty: str) -> Dict:
        """Генерация вопроса на заполнение пропуска"""
        
        context = self._get_rag_context("марийский язык предложения примеры")
        
        if not context:
            return self._generate_fallback_question()
        
        prompt = f"""На основе этого текста, создай вопрос на заполнение пропуска.

Текст: {context}

Уровень: {difficulty}

Формат ответа (строго JSON):
{{
    "question": "Заполните пропуск: [предложение с ___]",
    "correct_answer": "[слово для пропуска]",
    "options": ["[вариант 1]", "[вариант 2]", "[вариант 3]", "[вариант 4]"],
    "explanation": "[объяснение]"
}}

Ответ ТОЛЬКО в формате JSON."""

        try:
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content.strip()
            
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            question_data = json.loads(content)
            random.shuffle(question_data["options"])
            
            question_data["type"] = "fill_blank"
            question_data["difficulty"] = difficulty
            
            return question_data
            
        except Exception as e:
            logger.error(f"Ошибка генерации вопроса: {e}")
            return self._generate_fallback_question()
    
    def _generate_grammar_question(self, difficulty: str) -> Dict:
        """Генерация вопроса по грамматике"""
        
        context = self._get_rag_context("марийская грамматика падежи глаголы")
        
        if not context:
            return self._generate_fallback_question()
        
        prompt = f"""На основе этого текста, создай вопрос по грамматике марийского языка.

Текст: {context}

Уровень: {difficulty}

Формат ответа (строго JSON):
{{
    "question": "[вопрос о грамматике]",
    "correct_answer": "[правильный ответ]",
    "options": ["[вариант 1]", "[вариант 2]", "[вариант 3]", "[вариант 4]"],
    "explanation": "[грамматическое объяснение]"
}}

Ответ ТОЛЬКО в формате JSON."""

        try:
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content.strip()
            
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            question_data = json.loads(content)
            random.shuffle(question_data["options"])
            
            question_data["type"] = "grammar"
            question_data["difficulty"] = difficulty
            
            return question_data
            
        except Exception as e:
            logger.error(f"Ошибка генерации вопроса: {e}")
            return self._generate_fallback_question()
    
    def _generate_fallback_question(self) -> Dict:
        """Резервный вопрос если генерация не удалась"""
        fallback_questions = [
            {
                "question": "Как сказать 'привет' на марийском языке?",
                "correct_answer": "Салам",
                "options": ["Салам", "Привет", "Здраво", "Мерҥге"],
                "explanation": "Салам - стандартное приветствие в марийском языке",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "Как сказать 'спасибо' на марийском?",
                "correct_answer": "Тау",
                "options": ["Тау", "Спасибо", "Благо", "Рахмат"],
                "explanation": "Тау - выражение благодарности на марийском",
                "type": "translation",
                "difficulty": "easy"
            },
            {
                "question": "К какой языковой семье относится марийский язык?",
                "correct_answer": "Финно-угорская",
                "options": ["Финно-угорская", "Тюркская", "Славянская", "Монгольская"],
                "explanation": "Марийский язык относится к финно-угорской языковой семье",
                "type": "multiple_choice",
                "difficulty": "medium"
            }
        ]
        
        return random.choice(fallback_questions)
    
    def generate_quiz(self, num_questions: int = 5, difficulty: str = "medium") -> List[Dict]:
        """
        Генерация полного теста
        
        Args:
            num_questions: количество вопросов
            difficulty: уровень сложности
            
        Returns:
            Список вопросов
        """
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
        """
        Отправить ответ на текущий вопрос
        
        Returns:
            Dict с результатом (correct, explanation, score)
        """
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
        
        # Определение уровня
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
        """Получить прогресс в виде строки"""
        return f"{self.current_question_index + 1}/{len(self.questions)}"
