# books/management/services/recommender_registry.py
"""
Реестр алгоритмов рекомендаций.

Позволяет переключаться между разными реализациями рекомендаций
через настройки Django.
"""

from typing import List, Callable
from django.conf import settings
from django.contrib.auth import get_user_model
from books.models import Book

User = get_user_model()


class RecommenderRegistry:
    """Реестр доступных алгоритмов рекомендаций."""
    
    def __init__(self):
        self._recommenders = {}
        self._default = None
        self._register_builtins()
    
    def _register_builtins(self):
        """Регистрация встроенных рекомендателей."""
        # Старый алгоритм (на основе жанров/авторов)
        from books.management.services.recommendations import recommend_books as recommend_old
        
        def old_recommender(user, top_n=20, **kwargs):
            qs = recommend_old(user, sort=kwargs.get('sort', 'score'), 
                              direction=kwargs.get('direction', 'desc'),
                              min_score=kwargs.get('min_score', 1.1))
            return list(qs[:top_n])
        
        self.register('content_based', old_recommender, 
                     name='Content-Based (Жанры/Авторы)')
        
        # Новый нейросетевой алгоритм (на основе эмбеддингов)
        try:
            from books.management.services.neural_recommender import recommend_books_by_embedding
            
            def neural_recommender(user, top_n=20, **kwargs):
                return recommend_books_by_embedding(user, top_n=top_n)
            
            self.register('neural_embeddings', neural_recommender,
                         name='Neural Embeddings (Sentence Transformer)')
        except ImportError:
            pass  # neural_recommender недоступен
    
    def register(self, key: str, func: Callable, name: str = None):
        """Регистрация функции рекомендателя.
        
        Args:
            key: Уникальный идентификатор (например, 'content_based', 'neural_embeddings')
            func: Callable(user, top_n=20, **kwargs) -> List[Book]
            name: Человеко-читаемое название
        """
        self._recommenders[key] = {
            'func': func,
            'name': name or key
        }
        if self._default is None:
            self._default = key
    
    def get(self, key: str = None):
        """Получение функции рекомендателя по ключу."""
        key = key or self._default
        if key not in self._recommenders:
            available = ', '.join(self._recommenders.keys())
            raise ValueError(f"Неизвестный рекомендатель '{key}'. Доступные: {available}")
        return self._recommenders[key]['func']
    
    def get_name(self, key: str = None) -> str:
        """Получение человеко-читаемого названия рекомендателя."""
        key = key or self._default
        return self._recommenders.get(key, {}).get('name', key)
    
    def list_available(self) -> dict:
        """Возврат словаря доступных рекомендателей: {key: name}."""
        return {k: v['name'] for k, v in self._recommenders.items()}
    
    def set_default(self, key: str):
        """Установка рекомендателя по умолчанию."""
        if key not in self._recommenders:
            raise ValueError(f"Неизвестный рекомендатель '{key}'")
        self._default = key


# Глобальный экземпляр реестра
_registry = RecommenderRegistry()


def get_recommender(key: str = None):
    """Получение функции рекомендателя из реестра.
    
    Args:
        key: Ключ рекомендателя, или None для значения по умолчанию из настроек
        
    Returns:
        Callable(user, top_n=20, **kwargs) -> List[Book]
    """
    if key is None:
        key = getattr(settings, 'RECOMMENDER_ALGORITHM', 'neural_embeddings')
    return _registry.get(key)


def get_available_recommenders() -> dict:
    """Получение словаря доступных рекомендателей для UI."""
    return _registry.list_available()


def get_recommender_name(key: str = None) -> str:
    """Получение человеко-читаемого названия рекомендателя."""
    if key is None:
        key = getattr(settings, 'RECOMMENDER_ALGORITHM', 'neural_embeddings')
    return _registry.get_name(key)