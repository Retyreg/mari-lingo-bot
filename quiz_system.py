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


# Источники RAG-базы, сгруппированные по уровню сложности.
# Каждый уровень включает файлы своего уровня и всех уровней ниже,
# поэтому "лёгкий" тянет слова только из учебников для новичков.
#
# В генерацию тестов сознательно допущены ТОЛЬКО источники словарного
# типа ("слово — перевод"), где у модели есть шанс достать реальную пару
# слово/значение, а не придумать её. Остальные материалы базы (грамматика
# диалектов, сравнительные обороты, этнография, мифология) для этой цели
# не годятся: это связная академическая проза и таблицы словоизменения,
# а не словарные статьи. Например, "rhm.pdf" когда-то отдал модели таблицу
# спряжения глагола "кияш" (лежать), а её попросили назвать словом "кий/кие"
# и придумать перевод с нуля — так родился вопрос с четырьмя неверными
# вариантами ответа. Эти источники по-прежнему доступны боту в режиме
# свободного чата, где связный контекст уместен — просто не для тестов.
_BEGINNER_TEXTBOOKS = [
    "marijskij jazyk dlja vseh 1.pdf",
    "marijskij jazyk dlja vseh 2.pdf",
    "omj_2017.pdf",  # сводный переработанный учебник (объединяет оба тома)
]

_STANDARD_REFERENCE = _BEGINNER_TEXTBOOKS + [
    "дмитриев_2013_Русско-марийский словарь.pdf",
    "eg2022.pdf",  # "Mari: An Essential Grammar for International Learners", 2022
]

# На сегодня у нас нет отдельного чистого источника для по-настоящему
# "продвинутой" лексики (описанные выше материалы для этого не годятся) —
# поэтому "сложный" уровень пока использует тот же корпус, что и "средний",
# и полагается на явную инструкцию модели искать менее частотное слово.
DIFFICULTY_SOURCES = {
    "easy": _BEGINNER_TEXTBOOKS,
    "medium": _STANDARD_REFERENCE,
    "hard": _STANDARD_REFERENCE,
}

_DIFFICULTY_GUIDANCE = {
    "easy": "Выбирай только самые базовые, повседневные слова (приветствия, семья, еда, части тела, простые предметы быта). Слово должно быть таким, которое встречается на первых страницах учебника для начинающих.",
    "medium": "Выбирай слово обычной бытовой или грамматической лексики среднего уровня — не самое базовое, но и не редкое/специальное.",
    "hard": "Выбирай менее распространённое, специальное или диалектное слово — то, что не входит в базовый словарный запас новичка.",
}


class QuizGenerator:
    """Генератор тестов на основе RAG базы и Groq AI"""

    def __init__(self, rag_searcher, groq_client, verifier_client=None):
        self.rag_searcher = rag_searcher
        self.groq_client = groq_client
        # Независимый проверяющий (например, клиент Anthropic) — второе
        # мнение о сгенерированном вопросе перед показом пользователю.
        # Необязателен: если не передан, эта проверка просто пропускается.
        self.verifier_client = verifier_client
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
                question_data = self._generate_translation_question(to_russian=True, difficulty=difficulty)
            elif question_type == "translation_to_mari":
                question_data = self._generate_translation_question(to_russian=False, difficulty=difficulty)
            else:
                question_data = self._generate_translation_question(to_russian=True, difficulty=difficulty)
        except Exception as e:
            logger.error(f"Ошибка генерации вопроса: {e}")
            question_data = self._generate_fallback_question(difficulty=difficulty)

        # Явно фиксируем пару "марийское слово / русское слово" по тексту
        # вопроса — независимо от того, каким путём вопрос был получен
        # (сгенерирован или взят из fallback-банка). Это нужно, чтобы бот
        # мог позже синхронизировать результат теста с колодой карточек
        # (см. FlashcardDeck) — без этого прогресс теста нигде, кроме
        # геймификации, не отражался.
        word_mari, word_russian = self._extract_word_pair(question_data)
        question_data["word_mari"] = word_mari
        question_data["word_russian"] = word_russian

        return question_data

    _MARI_WORD_RE = re.compile(r"марийское слово\s+([^?]+)\?", re.IGNORECASE)
    _RUSSIAN_WORD_RE = re.compile(r"как сказать\s+(.+?)\s+на марийском", re.IGNORECASE)

    @classmethod
    def _extract_word_pair(cls, question_data: Dict):
        """По тексту вопроса восстанавливает пару (марийское слово, русское слово)"""
        question = question_data.get("question", "")
        correct_answer = question_data.get("correct_answer", "")

        m = cls._MARI_WORD_RE.search(question)
        if m:
            return m.group(1).strip(), correct_answer

        m = cls._RUSSIAN_WORD_RE.search(question)
        if m:
            return correct_answer, m.group(1).strip()

        # Не удалось разобрать формулировку — используем то, что есть,
        # чтобы вызывающий код не падал (карточка получится не идеальной,
        # но лучше, чем полное отсутствие данных).
        return correct_answer, correct_answer
    
    def _get_rag_context(self, query: str, n_results: int = 3, difficulty: str = "medium") -> str:
        """Получение контекста из RAG базы, ограниченного источниками нужного уровня сложности"""
        import io
        import contextlib

        filenames = DIFFICULTY_SOURCES.get(difficulty, DIFFICULTY_SOURCES["medium"])

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            results = self.rag_searcher.search(query, n_results=n_results, filenames=filenames)
        
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
        context = self._get_rag_context(random.choice(queries), difficulty=difficulty)

        if not context:
            return self._generate_fallback_question(difficulty=difficulty)

        difficulty_note = _DIFFICULTY_GUIDANCE.get(difficulty, _DIFFICULTY_GUIDANCE["medium"])

        if to_russian:
            prompt = f"""Из этого словаря выбери ОДНО марийское слово и создай вопрос на перевод.

Словарь:
{context}

УРОВЕНЬ СЛОЖНОСТИ: {difficulty}. {difficulty_note}

ЗАДАЧА: Создай вопрос "Как переводится марийское слово X?" где X - марийское слово.
Все 4 варианта ответа должны быть на РУССКОМ языке.

ВАЖНО: Слово и его перевод должны БУКВАЛЬНО присутствовать в словаре выше.
Не придумывай перевод сам — только то, что реально написано в тексте.
В поле "source_quote" процитируй ДОСЛОВНО ту строку словаря, где встречаются
и марийское слово, и его перевод. Если такой строки нет — не выбирай это слово.

Верни ТОЛЬКО JSON:
{{"question": "Как переводится марийское слово [марийское]?", "correct_answer": "[русский перевод]", "options": ["[русский1]", "[русский2]", "[русский3]", "[русский4]"], "explanation": "[марийское] = [русское]", "source_quote": "[дословная строка из словаря выше]"}}

Пример правильного ответа:
{{"question": "Как переводится марийское слово шӱкаш?", "correct_answer": "толкать", "options": ["толкать", "бежать", "идти", "стоять"], "explanation": "шӱкаш = толкать", "source_quote": "шӱкаш толкать"}}"""

        else:
            prompt = f"""Из этого словаря выбери ОДНО русское слово и создай вопрос на перевод.

Словарь:
{context}

УРОВЕНЬ СЛОЖНОСТИ: {difficulty}. {difficulty_note}

ЗАДАЧА: Создай вопрос "Как сказать X на марийском?" где X - русское слово.
Все 4 варианта ответа должны быть на МАРИЙСКОМ языке (с буквами ӱ, ӧ, ӓ, ӹ если нужно).

ВАЖНО: Слово и его перевод должны БУКВАЛЬНО присутствовать в словаре выше.
Не придумывай перевод сам — только то, что реально написано в тексте.
В поле "source_quote" процитируй ДОСЛОВНО ту строку словаря, где встречаются
и русское слово, и его марийский перевод. Если такой строки нет — не выбирай это слово.

Верни ТОЛЬКО JSON:
{{"question": "Как сказать [русское] на марийском?", "correct_answer": "[марийский перевод]", "options": ["[марийский1]", "[марийский2]", "[марийский3]", "[марийский4]"], "explanation": "[русское] = [марийское]", "source_quote": "[дословная строка из словаря выше]"}}

Пример правильного ответа:
{{"question": "Как сказать толкать на марийском?", "correct_answer": "шӱкаш", "options": ["шӱкаш", "кошташ", "ошкылаш", "шогаш"], "explanation": "толкать = шӱкаш", "source_quote": "шӱкаш толкать"}}"""

        try:
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.8,
                max_tokens=600,
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

            # Валидация: строка-цитата реально есть в контексте
            if not self._validate_question(question_data, to_russian, context):
                logger.warning("Вопрос не прошёл валидацию (нет реальной цитаты), используем fallback")
                return self._generate_fallback_question(difficulty=difficulty)

            # Второе мнение: независимая модель проверяет, что перевод
            # действительно верный, а не просто "правдоподобная цитата".
            # Проверка цитаты выше не ловит случаи, когда Groq честно
            # цитирует реальную строку словаря, но неверно её понимает.
            if not self._verify_with_second_opinion(question_data, to_russian):
                logger.warning("Вопрос не прошёл проверку вторым мнением, используем fallback")
                return self._generate_fallback_question(difficulty=difficulty)

            # Отмечаем как использованные ОБЕ стороны пары (марийскую и
            # русскую) — иначе в рамках одного теста может проскочить та
            # же пара слов, но в обратном направлении ("дом→пӧрт" и
            # затем "пӧрт→дом" воспринимаются пользователем как повтор).
            mari_word, russian_word = self._extract_word_pair(question_data)
            self.used_words.add(mari_word.lower())
            self.used_words.add(russian_word.lower())
            
            # Перемешиваем варианты
            random.shuffle(question_data["options"])
            
            question_data["type"] = "translation"
            question_data["difficulty"] = difficulty
            
            return question_data
            
        except Exception as e:
            logger.error(f"Ошибка парсинга вопроса: {e}")
            return self._generate_fallback_question(difficulty=difficulty)
    
    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        """Схлопывает пробелы/переносы строк, приводит к нижнему регистру — для сравнения подстрок"""
        return re.sub(r"\s+", " ", text).strip().lower()

    def _validate_question(self, question_data: Dict, to_russian: bool, context: str = "") -> bool:
        """Валидация сгенерированного вопроса"""
        try:
            # Проверяем наличие всех полей
            required = ["question", "correct_answer", "options", "explanation", "source_quote"]
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

            # Проверка обоснованности (anti-hallucination): модель обязана
            # процитировать реальную строку контекста, и в этой же строке
            # должны буквально встречаться и марийское слово, и перевод.
            # Без этого модель может изобрести правдоподобный, но неверный
            # перевод несуществующего или неверно понятого слова.
            quote = self._normalize_for_matching(str(question_data["source_quote"]))
            normalized_context = self._normalize_for_matching(context)

            if not quote or quote not in normalized_context:
                return False

            mari_word = question_data["question"] if to_russian else question_data["correct_answer"]

            # Извлекаем марийское слово из формулировки вопроса, если оно не в correct_answer
            # (грубая эвристика: последнее "словообразное" слово в вопросе)
            mari_candidates = re.findall(r"[a-zа-яёӱӧӓӹ]+", mari_word.lower())
            mari_token = mari_candidates[-1] if mari_candidates else mari_word.lower()

            if mari_token not in quote:
                return False

            return True

        except Exception:
            return False

    def _verify_with_second_opinion(self, question_data: Dict, to_russian: bool) -> bool:
        """
        Просит независимую модель (Claude) подтвердить перевод.
        Если проверяющий не подключён или сам упал с ошибкой — проверку
        пропускаем (не роняем тест из-за недоступности стороннего API),
        но если модель явно ответила "неверно" — отклоняем вопрос.
        """
        if self.verifier_client is None:
            return True

        if to_russian:
            mari_word = question_data["question"]
            russian_word = question_data["correct_answer"]
        else:
            mari_word = question_data["correct_answer"]
            russian_word = question_data["question"]

        prompt = f"""Ты — эксперт по марийскому языку. Проверь пару перевода.

Вопрос теста: "{mari_word}"
Заявленный правильный ответ: "{russian_word}"
Цитата из источника, на которую опирались: "{question_data['source_quote']}"

Это действительно верный перевод? Ответь ТОЛЬКО одним словом: ДА или НЕТ."""

        try:
            response = self.verifier_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = response.content[0].text.strip().lower()
            return answer.startswith("да")
        except Exception as e:
            logger.warning(f"Проверка вторым мнением недоступна, пропускаем: {e}")
            return True

    def _generate_fallback_question(self, difficulty: str = "medium") -> Dict:
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
        
        # Сначала пробуем найти неиспользованный вопрос нужного уровня сложности.
        # В резервном банке одна и та же пара слов встречается в обеих
        # формулировках ("дом→пӧрт" и "пӧрт→дом") — фильтруем по ОБЕИМ
        # сторонам пары, иначе такая пара может выпасть дважды подряд.
        by_difficulty = [q for q in fallback_questions if q["difficulty"] == difficulty]
        pool = by_difficulty or fallback_questions

        def pair_already_used(q):
            mari_word, russian_word = self._extract_word_pair(q)
            return mari_word.lower() in self.used_words or russian_word.lower() in self.used_words

        available = [q for q in pool if not pair_already_used(q)]

        if not available:
            # Пул этого уровня сложности слишком мал (например, для
            # "medium" в банке всего 3 уникальные пары слов на 5
            # вопросов теста) — прежде чем повторяться, пробуем взять
            # неиспользованную пару из ВСЕГО резервного банка целиком.
            available = [q for q in fallback_questions if not pair_already_used(q)]

        if not available:
            # Весь банк без исключения исчерпан — только тогда сбрасываем
            # и разрешаем повтор.
            self.used_words.clear()
            available = pool

        question = random.choice(available)
        mari_word, russian_word = self._extract_word_pair(question)
        self.used_words.add(mari_word.lower())
        self.used_words.add(russian_word.lower())
        
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
            "word_mari": current_question.get("word_mari"),
            "word_russian": current_question.get("word_russian"),
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
