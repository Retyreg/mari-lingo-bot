"""
Spaced Repetition System - Система интервального повторения
Использует алгоритм SM-2 (SuperMemo 2) для оптимального повторения карточек
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FlashCard:
    """Карточка для изучения с метаданными SR"""
    
    def __init__(
        self,
        card_id: str,
        front: str,
        back: str,
        category: str = "general",
        easiness_factor: float = 2.5,
        interval: int = 0,
        repetitions: int = 0,
        next_review: Optional[datetime] = None,
        created_at: Optional[datetime] = None
    ):
        self.card_id = card_id
        self.front = front  # Марийское слово
        self.back = back    # Русский перевод
        self.category = category
        
        # SM-2 параметры
        self.easiness_factor = easiness_factor  # E-Factor (2.5 по умолчанию)
        self.interval = interval  # Интервал в днях
        self.repetitions = repetitions  # Количество успешных повторений
        self.next_review = next_review or datetime.now()
        
        # Метаданные
        self.created_at = created_at or datetime.now()
        self.last_reviewed = None
        self.total_reviews = 0
        self.correct_reviews = 0
        self.difficulty_rating = []  # История оценок сложности
    
    def to_dict(self) -> Dict:
        """Сериализация в словарь"""
        return {
            "card_id": self.card_id,
            "front": self.front,
            "back": self.back,
            "category": self.category,
            "easiness_factor": self.easiness_factor,
            "interval": self.interval,
            "repetitions": self.repetitions,
            "next_review": self.next_review.isoformat() if self.next_review else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_reviewed": self.last_reviewed.isoformat() if self.last_reviewed else None,
            "total_reviews": self.total_reviews,
            "correct_reviews": self.correct_reviews,
            "difficulty_rating": self.difficulty_rating
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FlashCard':
        """Десериализация из словаря"""
        card = cls(
            card_id=data["card_id"],
            front=data["front"],
            back=data["back"],
            category=data.get("category", "general"),
            easiness_factor=data.get("easiness_factor", 2.5),
            interval=data.get("interval", 0),
            repetitions=data.get("repetitions", 0),
            next_review=datetime.fromisoformat(data["next_review"]) if data.get("next_review") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        )
        
        if data.get("last_reviewed"):
            card.last_reviewed = datetime.fromisoformat(data["last_reviewed"])
        
        card.total_reviews = data.get("total_reviews", 0)
        card.correct_reviews = data.get("correct_reviews", 0)
        card.difficulty_rating = data.get("difficulty_rating", [])
        
        return card
    
    def is_due(self) -> bool:
        """Проверка, нужно ли повторять карточку"""
        return datetime.now() >= self.next_review
    
    def get_mastery_level(self) -> str:
        """Получить уровень владения"""
        if self.repetitions == 0:
            return "новая"
        elif self.repetitions < 3:
            return "изучается"
        elif self.repetitions < 6:
            return "знакомая"
        else:
            return "освоена"
    
    def get_accuracy(self) -> float:
        """Процент правильных ответов"""
        if self.total_reviews == 0:
            return 0.0
        return (self.correct_reviews / self.total_reviews) * 100


class SM2Algorithm:
    """
    Реализация алгоритма SuperMemo 2 (SM-2)
    
    Алгоритм разработан Петром Возняком в 1987 году
    Оптимизирует интервалы повторения для максимального запоминания
    """
    
    @staticmethod
    def calculate_next_interval(
        quality: int,
        easiness_factor: float,
        interval: int,
        repetitions: int
    ) -> Tuple[float, int, int]:
        """
        Вычисление следующего интервала повторения
        
        Args:
            quality: Оценка качества ответа (0-5)
                0 - полный провал
                1 - неправильно, но помню после подсказки
                2 - неправильно, но вспомнил легко
                3 - правильно, но с трудом
                4 - правильно, после раздумий
                5 - правильно, легко
            easiness_factor: Коэффициент легкости (E-Factor)
            interval: Текущий интервал в днях
            repetitions: Количество успешных повторений
            
        Returns:
            Tuple[новый E-Factor, новый интервал, новое количество повторений]
        """
        
        # Обновление E-Factor
        new_ef = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        
        # E-Factor не может быть меньше 1.3
        if new_ef < 1.3:
            new_ef = 1.3
        
        # Если качество < 3, начинаем сначала
        if quality < 3:
            new_repetitions = 0
            new_interval = 1
        else:
            new_repetitions = repetitions + 1
            
            if new_repetitions == 1:
                new_interval = 1
            elif new_repetitions == 2:
                new_interval = 6
            else:
                new_interval = int(interval * new_ef)
        
        return new_ef, new_interval, new_repetitions


class SpacedRepetitionSystem:
    """Система интервального повторения для управления карточками"""
    
    def __init__(self, user_id: int, data_path: str = "./user_data"):
        self.user_id = user_id
        self.data_path = Path(data_path)
        self.data_path.mkdir(exist_ok=True)
        
        self.cards_file = self.data_path / f"{user_id}_cards.json"
        self.cards: Dict[str, FlashCard] = {}
        
        self.load_cards()
    
    def load_cards(self):
        """Загрузка карточек из файла"""
        if self.cards_file.exists():
            try:
                with open(self.cards_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cards = {
                        card_id: FlashCard.from_dict(card_data)
                        for card_id, card_data in data.items()
                    }
                logger.info(f"Загружено {len(self.cards)} карточек для пользователя {self.user_id}")
            except Exception as e:
                logger.error(f"Ошибка загрузки карточек: {e}")
                self.cards = {}
    
    def save_cards(self):
        """Сохранение карточек в файл"""
        try:
            data = {
                card_id: card.to_dict()
                for card_id, card in self.cards.items()
            }
            with open(self.cards_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(self.cards)} карточек")
        except Exception as e:
            logger.error(f"Ошибка сохранения карточек: {e}")
    
    def add_card(self, front: str, back: str, category: str = "general") -> FlashCard:
        """Добавление новой карточки"""
        card_id = f"card_{len(self.cards)}_{int(datetime.now().timestamp())}"
        
        card = FlashCard(
            card_id=card_id,
            front=front,
            back=back,
            category=category
        )
        
        self.cards[card_id] = card
        self.save_cards()
        
        logger.info(f"Добавлена карточка: {front} -> {back}")
        return card
    
    def get_due_cards(self, limit: int = 10) -> List[FlashCard]:
        """Получить карточки, которые нужно повторить"""
        due_cards = [
            card for card in self.cards.values()
            if card.is_due()
        ]
        
        # Сортировка: сначала новые, потом по дате повторения
        due_cards.sort(key=lambda c: (c.repetitions > 0, c.next_review))
        
        return due_cards[:limit]
    
    def get_new_cards(self, limit: int = 5) -> List[FlashCard]:
        """Получить новые карточки (ещё не изученные)"""
        new_cards = [
            card for card in self.cards.values()
            if card.repetitions == 0 and card.is_due()
        ]
        
        new_cards.sort(key=lambda c: c.created_at)
        return new_cards[:limit]
    
    def review_card(self, card_id: str, quality: int) -> FlashCard:
        """
        Отметить повторение карточки
        
        Args:
            card_id: ID карточки
            quality: Оценка качества ответа (0-5)
                0 - Не знаю совсем
                1 - Не знаю
                2 - С трудом вспомнил
                3 - Правильно, с усилием
                4 - Правильно, легко
                5 - Очень легко
        """
        card = self.cards.get(card_id)
        
        if not card:
            raise ValueError(f"Карточка {card_id} не найдена")
        
        # Применяем алгоритм SM-2
        new_ef, new_interval, new_repetitions = SM2Algorithm.calculate_next_interval(
            quality=quality,
            easiness_factor=card.easiness_factor,
            interval=card.interval,
            repetitions=card.repetitions
        )
        
        # Обновляем карточку
        card.easiness_factor = new_ef
        card.interval = new_interval
        card.repetitions = new_repetitions
        card.next_review = datetime.now() + timedelta(days=new_interval)
        card.last_reviewed = datetime.now()
        card.total_reviews += 1
        
        if quality >= 3:
            card.correct_reviews += 1
        
        card.difficulty_rating.append(quality)
        
        # Ограничиваем историю последними 50 оценками
        if len(card.difficulty_rating) > 50:
            card.difficulty_rating = card.difficulty_rating[-50:]
        
        self.save_cards()
        
        logger.info(f"Повторение карточки {card_id}: качество={quality}, новый интервал={new_interval} дней")
        
        return card
    
    def get_statistics(self) -> Dict:
        """Получить статистику по всем карточкам"""
        total_cards = len(self.cards)
        
        if total_cards == 0:
            return {
                "total_cards": 0,
                "new_cards": 0,
                "learning_cards": 0,
                "familiar_cards": 0,
                "mastered_cards": 0,
                "due_today": 0,
                "total_reviews": 0,
                "average_accuracy": 0.0
            }
        
        new = sum(1 for c in self.cards.values() if c.repetitions == 0)
        learning = sum(1 for c in self.cards.values() if 0 < c.repetitions < 3)
        familiar = sum(1 for c in self.cards.values() if 3 <= c.repetitions < 6)
        mastered = sum(1 for c in self.cards.values() if c.repetitions >= 6)
        due = sum(1 for c in self.cards.values() if c.is_due())
        
        total_reviews = sum(c.total_reviews for c in self.cards.values())
        total_correct = sum(c.correct_reviews for c in self.cards.values())
        avg_accuracy = (total_correct / total_reviews * 100) if total_reviews > 0 else 0
        
        return {
            "total_cards": total_cards,
            "new_cards": new,
            "learning_cards": learning,
            "familiar_cards": familiar,
            "mastered_cards": mastered,
            "due_today": due,
            "total_reviews": total_reviews,
            "average_accuracy": avg_accuracy
        }
    
    def get_cards_by_category(self, category: str) -> List[FlashCard]:
        """Получить карточки по категории"""
        return [
            card for card in self.cards.values()
            if card.category == category
        ]
    
    def get_difficult_cards(self, limit: int = 10) -> List[FlashCard]:
        """Получить самые сложные карточки"""
        cards_with_reviews = [
            card for card in self.cards.values()
            if card.total_reviews > 0
        ]
        
        # Сортируем по точности (от меньшего к большему)
        cards_with_reviews.sort(key=lambda c: c.get_accuracy())
        
        return cards_with_reviews[:limit]
    
    def reset_card(self, card_id: str):
        """Сбросить прогресс карточки"""
        card = self.cards.get(card_id)
        
        if card:
            card.easiness_factor = 2.5
            card.interval = 0
            card.repetitions = 0
            card.next_review = datetime.now()
            self.save_cards()
            
            logger.info(f"Сброс прогресса карточки {card_id}")
    
    def delete_card(self, card_id: str):
        """Удалить карточку"""
        if card_id in self.cards:
            del self.cards[card_id]
            self.save_cards()
            logger.info(f"Удалена карточка {card_id}")
