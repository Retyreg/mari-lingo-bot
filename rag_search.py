#!/usr/bin/env python3
"""
RAG Search Interface
Интерактивный поиск по векторной базе данных
"""

import sys
from pathlib import Path
from typing import List, Optional

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    from chromadb.config import Settings
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("\n📦 Установите зависимости:")
    print("pip install chromadb sentence-transformers")
    sys.exit(1)


# Источники в общей RAG-базе, не относящиеся к обучению марийскому языку
# или вытесненные более новой версией. Базу не трогаем физически (она
# используется и другими проектами) — просто никогда не подмешиваем эти
# файлы в результаты поиска для Mari Lingo Bot.
#   - Getica: историческая статья о готах Иордана, марийской лексики не содержит
#   - eg-temp.pdf: черновик 2019 г. грамматики, вытеснен финальной eg2022.pdf
EXCLUDED_SOURCES = [
    "The_Peoples_of_Hermanaric_Jordanes,_Getica_116_Irma_Korkkanen_Z.pdf",
    "eg-temp.pdf",
]


class RAGSearcher:
    """Класс для поиска по RAG базе"""
    
    def __init__(self, db_path: str = "./rag_database"):
        """
        Инициализация поисковика
        
        Args:
            db_path: Путь к базе данных
        """
        db_path = Path(db_path)
        
        if not db_path.exists():
            print(f"❌ База данных не найдена: {db_path}")
            print("   Сначала создайте базу с помощью pdf_to_rag.py")
            sys.exit(1)
        
        print(f"🚀 Загрузка модели...")
        self.model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
        
        print(f"📚 Подключение к базе данных...")
        self.client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        try:
            self.collection = self.client.get_collection("documents")
            doc_count = self.collection.count()
            print(f"✅ База загружена ({doc_count} документов)\n")
        except Exception as e:
            print(f"❌ Ошибка загрузки коллекции: {e}")
            sys.exit(1)
    
    def search(self, query: str, n_results: int = 5, filenames: Optional[List[str]] = None):
        """
        Поиск по запросу

        Args:
            query: Поисковый запрос
            n_results: Количество результатов
            filenames: Если указано, ограничить поиск этими файлами-источниками
        """
        print(f"🔍 Поиск: '{query}'")
        print("   Создание эмбеддинга запроса...")

        # Создание эмбеддинга
        query_embedding = self.model.encode([query])[0]

        # Поиск. Если явный список файлов не передан (например, свободный
        # чат-режим), всё равно исключаем заведомо непригодные источники.
        if filenames:
            where = {"filename": {"$in": filenames}}
        else:
            where = {"filename": {"$nin": EXCLUDED_SOURCES}}
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
            where=where
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
