#!/usr/bin/env python3
"""
RAG Search Interface
Интерактивный поиск по векторной базе данных
"""

import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    from chromadb.config import Settings
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("\n📦 Установите зависимости:")
    print("pip install chromadb sentence-transformers")
    sys.exit(1)


class RAGSearcher:
    """Класс для поиска по RAG базе.

    Если базы нет или коллекция не загружается — переходит в degraded-режим:
    `search()` возвращает None, бот продолжает работать, но без RAG-контекста.
    """

    def __init__(self, db_path: str = "./rag_database"):
        self.db_path = Path(db_path)
        self.model = None
        self.client = None
        self.collection = None
        self.available = False

        if not self.db_path.exists():
            logger.warning(
                "RAG база не найдена: %s. Бот стартует без RAG (ответы без контекста). "
                "Создайте базу через pdf_to_rag.py.",
                self.db_path,
            )
            return

        try:
            logger.info("Загрузка модели эмбеддингов…")
            self.model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')

            logger.info("Подключение к RAG базе…")
            self.client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(anonymized_telemetry=False),
            )
            self.collection = self.client.get_collection("documents")
            doc_count = self.collection.count()
            self.available = True
            logger.info("RAG база загружена (%d документов)", doc_count)
        except Exception as e:
            logger.warning("RAG init failed: %s. Бот работает без контекста.", e)
            self.available = False
    
    def search(self, query: str, n_results: int = 5):
        """
        Поиск по запросу. В degraded-режиме (база не загружена) возвращает None.
        """
        if not self.available:
            return None

        print(f"🔍 Поиск: '{query}'")
        print("   Создание эмбеддинга запроса...")

        # Создание эмбеддинга
        query_embedding = self.model.encode([query])[0]

        # Поиск
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results
        )

        if not results['documents'][0]:
            print("\n❌ Результаты не найдены")
            return
        
        print(f"\n📋 Найдено {len(results['documents'][0])} релевантных фрагментов:\n")
        print("=" * 80)
        
        for i, (doc, metadata, distance) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        ), 1):
            relevance = (1 - distance) * 100
            
            print(f"\n{i}. 📄 Файл: {metadata['filename']}")
            print(f"   📍 Чанк: {metadata.get('chunk_id', 'N/A')} / Страниц в файле: {metadata.get('pages', 'N/A')}")
            print(f"   🎯 Релевантность: {relevance:.1f}%")
            print(f"   📅 Обработан: {metadata.get('processed_at', 'N/A')[:19]}")
            print(f"\n   💬 Текст:")
            
            # Форматирование текста
            text = doc[:500] + "..." if len(doc) > 500 else doc
            for line in text.split('\n'):
                if line.strip():
                    print(f"      {line.strip()}")
            
            print("\n" + "-" * 80)
        
        return results
    
    def interactive_mode(self):
        """Интерактивный режим поиска"""
        print("\n" + "=" * 80)
        print("🔍 Интерактивный режим поиска")
        print("=" * 80)
        print("\nКоманды:")
        print("  - Введите запрос для поиска")
        print("  - 'stats' - показать статистику базы")
        print("  - 'quit' или 'exit' - выход")
        print("\n" + "=" * 80 + "\n")
        
        while True:
            try:
                query = input("🔍 Ваш запрос: ").strip()
                
                if not query:
                    continue
                
                if query.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 До свидания!")
                    break
                
                if query.lower() == 'stats':
                    self.show_stats()
                    continue
                
                # Запрос на количество результатов
                try:
                    n = input("   Сколько результатов показать? [5]: ").strip()
                    n_results = int(n) if n else 5
                except ValueError:
                    n_results = 5
                
                print()
                self.search(query, n_results)
                print()
                
            except KeyboardInterrupt:
                print("\n\n👋 До свидания!")
                break
            except Exception as e:
                print(f"\n❌ Ошибка: {e}\n")
    
    def show_stats(self):
        """Показать статистику базы данных"""
        count = self.collection.count()
        
        # Получение уникальных файлов
        sample = self.collection.get(limit=count)
        unique_files = set()
        
        if sample['metadatas']:
            for metadata in sample['metadatas']:
                unique_files.add(metadata.get('filename', 'unknown'))
        
        print("\n📊 Статистика базы данных:")
        print("=" * 80)
        print(f"   Всего фрагментов: {count}")
        print(f"   Уникальных файлов: {len(unique_files)}")
        print(f"   Размерность эмбеддингов: {self.model.get_sentence_embedding_dimension()}")
        print("\n   📁 Файлы в базе:")
        for filename in sorted(unique_files):
            print(f"      - {filename}")
        print("=" * 80 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Поиск по RAG базе данных"
    )
    parser.add_argument(
        "--db-path",
        default="./rag_database",
        help="Путь к базе данных (по умолчанию: ./rag_database)"
    )
    parser.add_argument(
        "--query",
        help="Поисковый запрос (если не указан - интерактивный режим)"
    )
    parser.add_argument(
        "--results",
        type=int,
        default=5,
        help="Количество результатов (по умолчанию: 5)"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Показать только статистику"
    )
    
    args = parser.parse_args()
    
    # Инициализация поисковика
    searcher = RAGSearcher(args.db_path)
    
    # Режим статистики
    if args.stats:
        searcher.show_stats()
        return
    
    # Режим одиночного запроса
    if args.query:
        searcher.search(args.query, args.results)
        return
    
    # Интерактивный режим
    searcher.interactive_mode()


if __name__ == "__main__":
    main()
