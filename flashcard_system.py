"""
Flashcard System - Система карточек для Mari Lingo Bot
С интервальным повторением и отслеживанием прогресса
"""

import json
import random
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FlashCard:
    """Одна карточка"""
    
    def __init__(self, word_mari: str, word_russian: str, 
                 example_mari: str = "", example_russian: str = "",
                 category: str = "общее", difficulty: str = "easy"):
        self.word_mari = word_mari
        self.word_russian = word_russian
        self.example_mari = example_mari
        self.example_russian = example_russian
        self.category = category
        self.difficulty = difficulty
        
        # Spaced repetition данные
        self.ease_factor = 2.5  # Множитель интервала
        self.interval = 1  # Дней до следующего повторения
        self.repetitions = 0  # Количество успешных повторений
        self.next_review = datetime.now()  # Когда показать снова
        self.last_review = None
    
    def to_dict(self) -> Dict:
        return {
            "word_mari": self.word_mari,
            "word_russian": self.word_russian,
            "example_mari": self.example_mari,
            "example_russian": self.example_russian,
            "category": self.category,
            "difficulty": self.difficulty,
            "ease_factor": self.ease_factor,
            "interval": self.interval,
            "repetitions": self.repetitions,
            "next_review": self.next_review.isoformat() if self.next_review else None,
            "last_review": self.last_review.isoformat() if self.last_review else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FlashCard':
        card = cls(
            word_mari=data["word_mari"],
            word_russian=data["word_russian"],
            example_mari=data.get("example_mari", ""),
            example_russian=data.get("example_russian", ""),
            category=data.get("category", "общее"),
            difficulty=data.get("difficulty", "easy")
        )
        card.ease_factor = data.get("ease_factor", 2.5)
        card.interval = data.get("interval", 1)
        card.repetitions = data.get("repetitions", 0)
        if data.get("next_review"):
            card.next_review = datetime.fromisoformat(data["next_review"])
        if data.get("last_review"):
            card.last_review = datetime.fromisoformat(data["last_review"])
        return card
    
    def update_after_review(self, quality: int):
        """
        Обновление карточки после ответа (алгоритм SM-2)
        quality: 0-5 (0-2 = не знаю, 3-5 = знаю)
        """
        self.last_review = datetime.now()
        
        if quality < 3:
            # Не знает - сбрасываем
            self.repetitions = 0
            self.interval = 1
        else:
            # Знает - увеличиваем интервал
            if self.repetitions == 0:
                self.interval = 1
            elif self.repetitions == 1:
                self.interval = 3
            else:
                self.interval = int(self.interval * self.ease_factor)
            
            self.repetitions += 1
        
        # Обновляем ease factor
        self.ease_factor = max(1.3, self.ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        
        # Следующее повторение
        self.next_review = datetime.now() + timedelta(days=self.interval)


class FlashcardDeck:
    """Колода карточек пользователя"""
    
    def __init__(self, user_id: int, data_path: str = "./user_data"):
        self.user_id = user_id
        self.data_path = Path(data_path)
        self.file_path = self.data_path / f"flashcards_{user_id}.json"
        self.cards: Dict[str, FlashCard] = {}  # key = word_mari
        self.current_session: List[str] = []  # Текущая сессия изучения
        self.session_index = 0
        self._load()
    
    def _load(self):
        """Загрузка карточек"""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for card_data in data.get("cards", []):
                        card = FlashCard.from_dict(card_data)
                        self.cards[card.word_mari] = card
            except Exception as e:
                logger.error(f"Ошибка загрузки карточек: {e}")
    
    def save(self):
        """Сохранение карточек"""
        self.data_path.mkdir(exist_ok=True)
        data = {
            "user_id": self.user_id,
            "cards": [card.to_dict() for card in self.cards.values()],
            "updated_at": datetime.now().isoformat()
        }
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_card(self, card: FlashCard) -> bool:
        """Добавить карточку"""
        if card.word_mari not in self.cards:
            self.cards[card.word_mari] = card
            self.save()
            return True
        return False
    
    def get_cards_for_review(self, limit: int = 10) -> List[FlashCard]:
        """Получить карточки для повторения"""
        now = datetime.now()
        due_cards = [
            card for card in self.cards.values()
            if card.next_review <= now
        ]
        
        # Сортируем: сначала те, что давно не повторяли
        due_cards.sort(key=lambda c: c.next_review)
        
        return due_cards[:limit]
    
    def get_new_cards(self, limit: int = 5) -> List[FlashCard]:
        """Получить новые карточки (ещё не изучавшиеся)"""
        new_cards = [
            card for card in self.cards.values()
            if card.repetitions == 0
        ]
        random.shuffle(new_cards)
        return new_cards[:limit]
    
    def start_session(self, mode: str = "mixed", limit: int = 10) -> Optional[FlashCard]:
        """
        Начать сессию изучения
        mode: "review" (повторение), "new" (новые), "mixed" (смешанный)
        """
        if mode == "review":
            cards = self.get_cards_for_review(limit)
        elif mode == "new":
            cards = self.get_new_cards(limit)
        else:
            # Смешанный: 70% повторение, 30% новые
            review_cards = self.get_cards_for_review(int(limit * 0.7))
            new_cards = self.get_new_cards(limit - len(review_cards))
            cards = review_cards + new_cards
            random.shuffle(cards)
        
        self.current_session = [card.word_mari for card in cards]
        self.session_index = 0
        
        if self.current_session:
            return self.cards[self.current_session[0]]
        return None
    
    def get_current_card(self) -> Optional[FlashCard]:
        """Получить текущую карточку в сессии"""
        if self.session_index < len(self.current_session):
            word = self.current_session[self.session_index]
            return self.cards.get(word)
        return None
    
    def answer_current(self, knew: bool) -> Dict:
        """
        Ответ на текущую карточку
        knew: True = знал, False = не знал
        """
        card = self.get_current_card()
        if not card:
            return {"error": "Нет текущей карточки"}
        
        quality = 4 if knew else 1
        card.update_after_review(quality)
        self.save()
        
        # Переходим к следующей
        self.session_index += 1
        
        return {
            "knew": knew,
            "word": card.word_mari,
            "next_review_days": card.interval,
            "remaining": len(self.current_session) - self.session_index,
            "total": len(self.current_session)
        }
    
    def get_next_card(self) -> Optional[FlashCard]:
        """Получить следующую карточку"""
        if self.session_index < len(self.current_session):
            word = self.current_session[self.session_index]
            return self.cards.get(word)
        return None
    
    def is_session_finished(self) -> bool:
        """Проверка завершения сессии"""
        return self.session_index >= len(self.current_session)
    
    def get_stats(self) -> Dict:
        """Статистика по карточкам"""
        total = len(self.cards)
        if total == 0:
            return {
                "total": 0,
                "learning": 0,
                "mastered": 0,
                "due_today": 0
            }
        
        now = datetime.now()
        learning = sum(1 for c in self.cards.values() if 0 < c.repetitions < 5)
        mastered = sum(1 for c in self.cards.values() if c.repetitions >= 5)
        due_today = sum(1 for c in self.cards.values() if c.next_review <= now)
        
        return {
            "total": total,
            "learning": learning,
            "mastered": mastered,
            "new": total - learning - mastered,
            "due_today": due_today
        }


class FlashcardManager:
    """Менеджер карточек с базовым набором слов"""
    
    # Базовый словарь марийского языка
    BASE_VOCABULARY = [
        # Приветствия
        {"mari": "салам", "russian": "привет", "example_mari": "Салам, эргым!", "example_russian": "Привет, сынок!", "category": "приветствия", "difficulty": "easy"},
        {"mari": "тау", "russian": "спасибо", "example_mari": "Тау, шуко тау!", "example_russian": "Спасибо, большое спасибо!", "category": "приветствия", "difficulty": "easy"},
        {"mari": "чеверын", "russian": "до свидания", "example_mari": "Чеверын, йолташ!", "example_russian": "До свидания, друг!", "category": "приветствия", "difficulty": "easy"},
        {"mari": "поро кече", "russian": "добрый день", "example_mari": "Поро кече лийже!", "example_russian": "Добрый день!", "category": "приветствия", "difficulty": "easy"},
        
        # Семья
        {"mari": "ава", "russian": "мать", "example_mari": "Мыйын авам", "example_russian": "Моя мать", "category": "семья", "difficulty": "easy"},
        {"mari": "ача", "russian": "отец", "example_mari": "Мыйын ачам", "example_russian": "Мой отец", "category": "семья", "difficulty": "easy"},
        {"mari": "эрге", "russian": "сын", "example_mari": "Эргем школыш коштеш", "example_russian": "Сын ходит в школу", "category": "семья", "difficulty": "easy"},
        {"mari": "ӱдыр", "russian": "дочь", "example_mari": "Ӱдырем лудеш", "example_russian": "Дочь читает", "category": "семья", "difficulty": "easy"},
        {"mari": "коча", "russian": "дедушка", "example_mari": "Коча куэм ончаш", "example_russian": "Дедушка смотрит берёзу", "category": "семья", "difficulty": "easy"},
        {"mari": "кува", "russian": "бабушка", "example_mari": "Кува киндым кӱэш", "example_russian": "Бабушка печёт хлеб", "category": "семья", "difficulty": "easy"},
        
        # Природа
        {"mari": "кече", "russian": "солнце", "example_mari": "Кече волгалтеш", "example_russian": "Солнце светит", "category": "природа", "difficulty": "easy"},
        {"mari": "тылзе", "russian": "луна", "example_mari": "Тылзе кавашке лектын", "example_russian": "Луна вышла на небо", "category": "природа", "difficulty": "medium"},
        {"mari": "вӱд", "russian": "вода", "example_mari": "Вӱд йӱаш", "example_russian": "Пить воду", "category": "природа", "difficulty": "easy"},
        {"mari": "мланде", "russian": "земля", "example_mari": "Мланде шарла", "example_russian": "Земля круглая", "category": "природа", "difficulty": "medium"},
        {"mari": "чодыра", "russian": "лес", "example_mari": "Чодырашке каена", "example_russian": "Идём в лес", "category": "природа", "difficulty": "easy"},
        {"mari": "эҥер", "russian": "река", "example_mari": "Эҥер йога", "example_russian": "Река течёт", "category": "природа", "difficulty": "easy"},
        {"mari": "кӱ", "russian": "камень", "example_mari": "Кӱ пеҥгыде", "example_russian": "Камень твёрдый", "category": "природа", "difficulty": "easy"},
        {"mari": "пушеҥге", "russian": "дерево", "example_mari": "Пушеҥге кушкеш", "example_russian": "Дерево растёт", "category": "природа", "difficulty": "medium"},
        
        # Еда
        {"mari": "кинде", "russian": "хлеб", "example_mari": "Кинде тамле", "example_russian": "Хлеб вкусный", "category": "еда", "difficulty": "easy"},
        {"mari": "шӧр", "russian": "молоко", "example_mari": "Шӧрым йӱаш", "example_russian": "Пить молоко", "category": "еда", "difficulty": "easy"},
        {"mari": "шыл", "russian": "мясо", "example_mari": "Шылым кочкаш", "example_russian": "Есть мясо", "category": "еда", "difficulty": "easy"},
        {"mari": "кол", "russian": "рыба", "example_mari": "Кол эҥерыште", "example_russian": "Рыба в реке", "category": "еда", "difficulty": "easy"},
        {"mari": "пура", "russian": "квас", "example_mari": "Пура юштӧ", "example_russian": "Квас холодный", "category": "еда", "difficulty": "medium"},
        
        # Дом
        {"mari": "пӧрт", "russian": "дом", "example_mari": "Пӧрт кугу", "example_russian": "Дом большой", "category": "дом", "difficulty": "easy"},
        {"mari": "окна", "russian": "окно", "example_mari": "Окна почылтын", "example_russian": "Окно открыто", "category": "дом", "difficulty": "easy"},
        {"mari": "омса", "russian": "дверь", "example_mari": "Омсам петыраш", "example_russian": "Закрыть дверь", "category": "дом", "difficulty": "easy"},
        {"mari": "ӱстел", "russian": "стол", "example_mari": "Ӱстел воктене", "example_russian": "Возле стола", "category": "дом", "difficulty": "easy"},
        
        # Цвета
        {"mari": "ош", "russian": "белый", "example_mari": "Ош лум", "example_russian": "Белый снег", "category": "цвета", "difficulty": "easy"},
        {"mari": "шем", "russian": "чёрный", "example_mari": "Шем пий", "example_russian": "Чёрная собака", "category": "цвета", "difficulty": "easy"},
        {"mari": "йошкар", "russian": "красный", "example_mari": "Йошкар пеледыш", "example_russian": "Красный цветок", "category": "цвета", "difficulty": "easy"},
        {"mari": "ужар", "russian": "зелёный", "example_mari": "Ужар шудо", "example_russian": "Зелёная трава", "category": "цвета", "difficulty": "easy"},
        
        # Животные
        {"mari": "пий", "russian": "собака", "example_mari": "Пий опта", "example_russian": "Собака лает", "category": "животные", "difficulty": "easy"},
        {"mari": "пырыс", "russian": "кошка", "example_mari": "Пырыс мурка", "example_russian": "Кошка мурлычет", "category": "животные", "difficulty": "easy"},
        {"mari": "ушкал", "russian": "корова", "example_mari": "Ушкал шӧрым пуа", "example_russian": "Корова даёт молоко", "category": "животные", "difficulty": "easy"},
        {"mari": "имне", "russian": "лошадь", "example_mari": "Имне куржеш", "example_russian": "Лошадь бежит", "category": "животные", "difficulty": "easy"},
        {"mari": "маска", "russian": "медведь", "example_mari": "Маска чодырашто", "example_russian": "Медведь в лесу", "category": "животные", "difficulty": "medium"},
        
        # Числа
        {"mari": "ик", "russian": "один", "example_mari": "Ик пӧрт", "example_russian": "Один дом", "category": "числа", "difficulty": "easy"},
        {"mari": "кок", "russian": "два", "example_mari": "Кок кид", "example_russian": "Две руки", "category": "числа", "difficulty": "easy"},
        {"mari": "кум", "russian": "три", "example_mari": "Кум йол", "example_russian": "Три ноги", "category": "числа", "difficulty": "easy"},
        {"mari": "ныл", "russian": "четыре", "example_mari": "Ныл лукым", "example_russian": "Четыре угла", "category": "числа", "difficulty": "easy"},
        {"mari": "вич", "russian": "пять", "example_mari": "Вич парня", "example_russian": "Пять пальцев", "category": "числа", "difficulty": "easy"},
        
        # Глаголы
        {"mari": "лудаш", "russian": "читать", "example_mari": "Книгам лудаш", "example_russian": "Читать книгу", "category": "глаголы", "difficulty": "medium"},
        {"mari": "сераш", "russian": "писать", "example_mari": "Серышым сераш", "example_russian": "Писать письмо", "category": "глаголы", "difficulty": "medium"},
        {"mari": "каяш", "russian": "идти", "example_mari": "Школыш каяш", "example_russian": "Идти в школу", "category": "глаголы", "difficulty": "easy"},
        {"mari": "кочкаш", "russian": "есть", "example_mari": "Киндым кочкаш", "example_russian": "Есть хлеб", "category": "глаголы", "difficulty": "easy"},
        {"mari": "йӱаш", "russian": "пить", "example_mari": "Вӱдым йӱаш", "example_russian": "Пить воду", "category": "глаголы", "difficulty": "easy"},
        {"mari": "мураш", "russian": "петь", "example_mari": "Мурым мураш", "example_russian": "Петь песню", "category": "глаголы", "difficulty": "medium"},
        {"mari": "кушташ", "russian": "танцевать", "example_mari": "Тӱр марла кушташ", "example_russian": "Танцевать по-марийски", "category": "глаголы", "difficulty": "medium"},
    ]
    
    @classmethod
    def get_categories(cls) -> List[str]:
        """Получить список категорий"""
        categories = set()
        for word in cls.BASE_VOCABULARY:
            categories.add(word["category"])
        return sorted(list(categories))
    
    @classmethod
    def get_words_by_category(cls, category: str) -> List[Dict]:
        """Получить слова по категории"""
        return [w for w in cls.BASE_VOCABULARY if w["category"] == category]
    
    @classmethod
    def initialize_deck(cls, deck: FlashcardDeck, categories: List[str] = None):
        """Инициализировать колоду базовым словарём"""
        words = cls.BASE_VOCABULARY
        
        if categories:
            words = [w for w in words if w["category"] in categories]
        
        added = 0
        for word_data in words:
            card = FlashCard(
                word_mari=word_data["mari"],
                word_russian=word_data["russian"],
                example_mari=word_data.get("example_mari", ""),
                example_russian=word_data.get("example_russian", ""),
                category=word_data.get("category", "общее"),
                difficulty=word_data.get("difficulty", "easy")
            )
            if deck.add_card(card):
                added += 1
        
        return added


def format_flashcard_message(card: FlashCard, show_answer: bool = False) -> str:
    """Форматирование карточки для Telegram"""
    
    # Эмодзи для категорий
    category_emoji = {
        "приветствия": "👋",
        "семья": "👨‍👩‍👧‍👦",
        "природа": "🌿",
        "еда": "🍞",
        "дом": "🏠",
        "цвета": "🎨",
        "животные": "🐾",
        "числа": "🔢",
        "глаголы": "🏃",
        "общее": "📚"
    }
    
    emoji = category_emoji.get(card.category, "📚")
    
    if not show_answer:
        # Показываем только марийское слово
        text = f"""
{emoji} **Карточка**

🇲🇪 **{card.word_mari}**

❓ Как переводится это слово?

_Нажми "Показать ответ" чтобы увидеть перевод_
"""
    else:
        # Показываем полную информацию
        text = f"""
{emoji} **Карточка**

🇲🇪 **{card.word_mari}**
🇷🇺 **{card.word_russian}**
"""
        if card.example_mari and card.example_russian:
            text += f"""
📝 Пример:
_{card.example_mari}_
_{card.example_russian}_
"""
        
        text += f"""
📂 Категория: {card.category}
"""
        
        if card.repetitions > 0:
            text += f"🔄 Повторений: {card.repetitions}\n"
    
    return text


def format_session_stats(deck: FlashcardDeck, knew_count: int, total: int) -> str:
    """Форматирование статистики сессии"""
    percentage = (knew_count / total * 100) if total > 0 else 0
    
    stats = deck.get_stats()
    
    return f"""
🎉 **Сессия завершена!**

📊 **Результаты:**
✅ Знал: {knew_count}/{total} ({percentage:.0f}%)

📚 **Общая статистика:**
📖 Всего карточек: {stats['total']}
📗 Изучаю: {stats['learning']}
⭐ Выучил: {stats['mastered']}
🆕 Новых: {stats['new']}

💪 Продолжай в том же духе!
"""
