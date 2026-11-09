# books/management/services/neural_recommender.py
"""
Content-Based Neural Recommendation System (исправленная версия).

Использует предварительно вычисленные эмбеддинги книг (полученные во внешней среде,
например Google Colab) и формирует персональный профиль пользователя только на
основе его собственных оценок. Не использует данные других пользователей.

Основные принципы:
- Фиксированное нейтральное значение 3.0 (шкала 1–5 из BookRating).
- Отдельные положительный и отрицательный профили предпочтений.
- Итоговая оценка = сходство с положительным профилем − weight * сходство с отрицательным профилем.
- Все эмбеддинги нормируются перед использованием (L2-норма).
- Проверка целостности файлов эмбеддингов при загрузке.
- Метод reload_embeddings() для подгрузки файлов без перезапуска Django.

ВАЖНО: итоговый score является показателем ранжирования, а не предсказанной оценкой книги.
"""

import hashlib
import json
import logging
import os
import re
from typing import List, Optional, Tuple

import numpy as np
from django.conf import settings
from django.contrib.auth import get_user_model

from books.models import Book, BookRating

User = get_user_model()
logger = logging.getLogger(__name__)


class NeuralRecommenderError(Exception):
    """Исключение с понятным сообщением о причине отказа рекомендаций."""
    pass


class NeuralContentRecommender:
    """
    Content-Based рекомендатель на эмбеддингах книг.

    Эмбеддинги загружаются из файлов:
      - book_embeddings.npy  (матрица float32, shape = [n_books, embedding_dim])
      - book_id_to_index.json (отображение id книги из Django -> индекс в матрице)
      - embeddings_metadata.json (обязательные метаданные о генерации эмбеддингов)

    Файлы должны быть подготовлены заранее (например, в Google Colab) и положены
    в директорию, указанную в настройках или по умолчанию <BASE_DIR>/embeddings.
    """

    # Фактический диапазон оценок из модели BookRating (value: IntegerField, 1–5).
    MIN_RATING: float = 1.0
    MAX_RATING: float = 5.0
    NEUTRAL_RATING: float = 3.0

    # Документированный допустимый диапазон коэффициента отрицательных предпочтений.
    # 0.0 — отрицательный профиль игнорируется, 1.0 — равный вес с положительным.
    NEGATIVE_WEIGHT_MIN: float = 0.0
    NEGATIVE_WEIGHT_MAX: float = 10.0

    # Обязательные поля файла метаданных.
    REQUIRED_METADATA_FIELDS: Tuple[str, ...] = (
        'generation_id',
        'model_name',
        'model_version',
        'embedding_dim',
        'num_books',
        'sha256_matrix',
        'sha256_mapping',
        'text_schema_version',
    )

    # Регулярное выражение для валидации SHA-256 (64 шестнадцатеричных символа).
    SHA256_RE = re.compile(r'^[0-9a-f]{64}$')

    def __init__(self):
        self._embeddings: Optional[np.ndarray] = None
        self._id_to_index: Optional[dict] = None
        self._index_to_id: Optional[dict] = None
        self._embedding_dim: Optional[int] = None
        self._loaded: bool = False
        self._load_error: Optional[str] = None
        self._negative_weight: Optional[float] = None
        self._metadata: Optional[dict] = None

    # ------------------------------------------------------------------ #
    # Внутренние helpers
    # ------------------------------------------------------------------ #
    def _embeddings_dir(self) -> str:
        return getattr(
            settings,
            'NEURAL_RECOMMENDER_EMBEDDINGS_DIR',
            os.path.join(settings.BASE_DIR, 'embeddings'),
        )

    def _matrix_path(self) -> str:
        return os.path.join(self._embeddings_dir(), 'book_embeddings.npy')

    def _map_path(self) -> str:
        return os.path.join(self._embeddings_dir(), 'book_id_to_index.json')

    def _metadata_path(self) -> str:
        return os.path.join(self._embeddings_dir(), 'embeddings_metadata.json')

    @staticmethod
    def _sha256_file(path: str) -> str:
        """Вычисляет SHA-256 хеш файла."""
        sha256 = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def _is_valid_sha256(value) -> bool:
        """Проверяет, что значение — строка из 64 шестнадцатеричных символов."""
        if not isinstance(value, str):
            return False
        return bool(NeuralContentRecommender.SHA256_RE.fullmatch(value))

    @staticmethod
    def _reject_duplicate_json_keys(pairs):
        """object_pairs_hook: запрещает повторяющиеся ключи в JSON."""
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Дублирующийся ключ в JSON: {key!r}")
            result[key] = value
        return result

    @staticmethod
    def _strict_int(value, field_name: str) -> int:
        """Строгое преобразование в int: запрет bool и дробных чисел."""
        if isinstance(value, bool):
            raise ValueError(f"Поле {field_name!r} не может быть булевым значением, получено {value!r}")
        if isinstance(value, float) and not value.is_integer():
            raise ValueError(
                f"Поле {field_name!r} должно быть целым числом, "
                f"получено дробное число {value!r}"
            )
        try:
            return int(value)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Невозможно преобразовать поле {field_name!r} в целое число: {value!r} ({exc})")

    def _clear_load_state(self) -> None:
        """Очистка частично загруженных данных при ошибке загрузки."""
        self._embeddings = None
        self._id_to_index = None
        self._index_to_id = None
        self._embedding_dim = None
        self._metadata = None

    def _get_negative_weight(self) -> float:
        """Возвращает коэффициент штрафа за отрицательные предпочтения.

        Читается из настройки NEURAL_RECOMMENDER_NEGATIVE_WEIGHT (по умолчанию 1.0).
        bool недопустим. Значение должно быть конечным, неотрицательным и
        лежать в документированном диапазоне [NEGATIVE_WEIGHT_MIN, NEGATIVE_WEIGHT_MAX].
        """
        if self._negative_weight is None:
            raw_value = getattr(settings, 'NEURAL_RECOMMENDER_NEGATIVE_WEIGHT', 1.0)

            # Явный запрет bool.
            if isinstance(raw_value, bool):
                raise NeuralRecommenderError(
                    f"NEURAL_RECOMMENDER_NEGATIVE_WEIGHT не может быть булевым значением, "
                    f"получено {raw_value!r}"
                )

            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise NeuralRecommenderError(
                    f"NEURAL_RECOMMENDER_NEGATIVE_WEIGHT должен быть числом, "
                    f"получено {raw_value!r} ({exc})"
                )

            if not np.isfinite(value):
                raise NeuralRecommenderError(
                    f"NEURAL_RECOMMENDER_NEGATIVE_WEIGHT должен быть конечным числом, "
                    f"получено {value!r}"
                )
            if value < self.NEGATIVE_WEIGHT_MIN or value > self.NEGATIVE_WEIGHT_MAX:
                raise NeuralRecommenderError(
                    f"NEURAL_RECOMMENDER_NEGATIVE_WEIGHT должен лежать в диапазоне "
                    f"[{self.NEGATIVE_WEIGHT_MIN}, {self.NEGATIVE_WEIGHT_MAX}], "
                    f"получено {value!r}"
                )

            self._negative_weight = value
        return self._negative_weight

    def reload_embeddings(self) -> None:
        """Сброс кэша и принудительная повторная загрузка эмбеддингов.

        Позволяет подгрузить файлы, которые появились или были исправлены после
        первого запуска Django, без перезапуска сервера.
        """
        self._embeddings = None
        self._id_to_index = None
        self._index_to_id = None
        self._embedding_dim = None
        self._loaded = False
        self._load_error = None
        self._negative_weight = None
        self._metadata = None
        self._load()

    def _load(self) -> None:
        if self._loaded:
            return

        matrix_path = self._matrix_path()
        map_path = self._map_path()
        metadata_path = self._metadata_path()

        missing = []
        if not os.path.exists(matrix_path):
            missing.append(f"матрица эмбеддингов: {matrix_path}")
        if not os.path.exists(map_path):
            missing.append(f"отображение ID: {map_path}")
        if not os.path.exists(metadata_path):
            missing.append(f"метаданные эмбеддингов: {metadata_path}")

        if missing:
            self._load_error = "Не найдены файлы: " + ", ".join(missing)
            self._clear_load_state()
            self._loaded = True
            logger.warning(self._load_error)
            return

        try:
            # Загрузка метаданных с запретом дублирующихся ключей.
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f, object_pairs_hook=self._reject_duplicate_json_keys)

            if not isinstance(metadata, dict):
                raise ValueError(
                    f"Файл метаданных должен содержать JSON-объект, "
                    f"получен {type(metadata).__name__}"
                )

            # Проверка наличия всех обязательных полей.
            missing_fields = [f for f in self.REQUIRED_METADATA_FIELDS if f not in metadata]
            if missing_fields:
                raise NeuralRecommenderError(
                    f"В файле метаданных отсутствуют обязательные поля: "
                    f"{', '.join(missing_fields)}"
                )

            # Валидация текстовых полей.
            text_fields = ('generation_id', 'model_name', 'model_version', 'text_schema_version')
            for field in text_fields:
                val = metadata[field]
                if not isinstance(val, str) or not val.strip():
                    raise NeuralRecommenderError(
                        f"Поле {field!r} в метаданных должно быть непустой строкой, "
                        f"получено {val!r}"
                    )

            # Строгая проверка embedding_dim (запрет bool и дробных значений).
            meta_embedding_dim = self._strict_int(metadata['embedding_dim'], 'embedding_dim')
            if meta_embedding_dim <= 0:
                raise NeuralRecommenderError(
                    f"Поле embedding_dim в метаданных должно быть положительным, "
                    f"получено {meta_embedding_dim!r}"
                )

            # Строгая проверка num_books (запрет bool и дробных значений).
            meta_num_books = self._strict_int(metadata['num_books'], 'num_books')
            if meta_num_books <= 0:
                raise NeuralRecommenderError(
                    f"Поле num_books в метаданных должно быть положительным, "
                    f"получено {meta_num_books!r}"
                )

            # Валидация SHA-256 хешей (обязательные).
            sha256_matrix = metadata['sha256_matrix']
            sha256_mapping = metadata['sha256_mapping']
            if not self._is_valid_sha256(sha256_matrix):
                raise NeuralRecommenderError(
                    f"Поле sha256_matrix в метаданных должно быть строкой из 64 "
                    f"шестнадцатеричных символов, получено {sha256_matrix!r}"
                )
            if not self._is_valid_sha256(sha256_mapping):
                raise NeuralRecommenderError(
                    f"Поле sha256_mapping в метаданных должно быть строкой из 64 "
                    f"шестнадцатеричных символов, получено {sha256_mapping!r}"
                )

            # Загрузка матрицы без pickle для безопасности.
            embeddings = np.load(matrix_path, allow_pickle=False)

            # Проверка: матрица должна быть двумерной.
            if embeddings.ndim != 2:
                raise ValueError(
                    f"Матрица эмбеддингов должна быть двумерной, "
                    f"получен размерность {embeddings.ndim} (shape={embeddings.shape})"
                )

            n_rows, dim = embeddings.shape
            if n_rows == 0:
                raise ValueError("Матрица эмбеддингов пуста (ноль строк)")
            if dim == 0:
                raise ValueError("Матрица эмбеддингов пуста (ноль столбцов)")

            # Проверка num_books относительно количества строк матрицы.
            if meta_num_books != n_rows:
                raise NeuralRecommenderError(
                    f"Поле num_books в метаданных ({meta_num_books}) не соответствует "
                    f"количеству строк матрицы ({n_rows})"
                )

            # Строгая проверка embedding_dim относительно размерности матрицы.
            if meta_embedding_dim != dim:
                raise NeuralRecommenderError(
                    f"Поле embedding_dim в метаданных ({meta_embedding_dim}) не соответствует "
                    f"размерности матрицы ({dim})"
                )

            # Запрет комплексных чисел — эмбеддинги должны быть вещественными.
            if (
                np.issubdtype(embeddings.dtype, np.complexfloating)
                or np.iscomplexobj(embeddings)
            ):
                raise ValueError(
                    f"Матрица эмбеддингов содержит комплексные числа "
                    f"(тип {embeddings.dtype}). Допускаются только вещественные "
                    f"значения, преобразуемые в float32 без потери данных."
                )

            # Проверка типа данных матрицы.
            if not np.issubdtype(embeddings.dtype, np.number):
                raise ValueError(
                    f"Матрица эмбеддингов должна содержать числа, "
                    f"получен тип {embeddings.dtype}"
                )

            # Приведение к float32 с повторной проверкой на NaN/Inf.
            embeddings = embeddings.astype(np.float32, copy=False)
            if not np.all(np.isfinite(embeddings)):
                bad_count = int(np.sum(~np.isfinite(embeddings)))
                raise ValueError(
                    f"Матрица содержит {bad_count} неконечных значений (NaN или inf)"
                )

            # Проверка SHA-256 хеша матрицы.
            actual_matrix_hash = self._sha256_file(matrix_path)
            if actual_matrix_hash != sha256_matrix:
                raise NeuralRecommenderError(
                    f"SHA-256 хеш матрицы не совпадает с метаданными: "
                    f"ожидалось {sha256_matrix}, "
                    f"получено {actual_matrix_hash}"
                )

            # Загрузка отображения ID с запретом дублирующихся ключей.
            with open(map_path, 'r', encoding='utf-8') as f:
                raw = json.load(f, object_pairs_hook=self._reject_duplicate_json_keys)

            if not isinstance(raw, dict):
                raise ValueError(
                    f"Файл отображения ID должен содержать JSON-объект, "
                    f"получен {type(raw).__name__}"
                )

            # Проверка SHA-256 хеша отображения ID.
            actual_map_hash = self._sha256_file(map_path)
            if actual_map_hash != sha256_mapping:
                raise NeuralRecommenderError(
                    f"SHA-256 хеш отображения ID не совпадает с метаданными: "
                    f"ожидалось {sha256_mapping}, "
                    f"получено {actual_map_hash}"
                )

            pk_field = Book._meta.pk
            id_to_index: dict = {}
            used_indices: dict = {}  # index -> book_id

            for k, v in raw.items():
                # Корректное преобразование идентификатора книги с учётом типа PK.
                try:
                    book_id = pk_field.to_python(k)
                except Exception as exc:
                    raise NeuralRecommenderError(
                        f"Невозможно преобразовать ключ {k!r} в идентификатор книги: {exc}"
                    )

                # Проверка на дублирование идентификатора книги.
                if book_id in id_to_index:
                    raise NeuralRecommenderError(
                        f"Дублирующийся идентификатор книги {book_id!r} в отображении ID"
                    )

                # Индекс должен быть целым числом: не boolean, не дробное число.
                if isinstance(v, bool):
                    raise NeuralRecommenderError(
                        f"Индекс для книги {book_id!r} не может быть булевым значением, "
                        f"получено {v!r}"
                    )
                if isinstance(v, float) and not v.is_integer():
                    raise NeuralRecommenderError(
                        f"Индекс для книги {book_id!r} должен быть целым числом, "
                        f"получено дробное число {v!r}"
                    )
                try:
                    idx = int(v)
                except (ValueError, TypeError) as exc:
                    raise NeuralRecommenderError(
                        f"Невозможно преобразовать индекс для книги {book_id!r}: {v!r} ({exc})"
                    )

                # Проверка: индекс в допустимом диапазоне.
                if idx < 0 or idx >= n_rows:
                    raise NeuralRecommenderError(
                        f"Индекс {idx} для книги id={book_id!r} вне допустимого "
                        f"диапазона [0, {n_rows - 1}]"
                    )

                # Проверка: каждый индекс матрицы соответствует только одной книге.
                if idx in used_indices:
                    raise NeuralRecommenderError(
                        f"Индекс матрицы {idx} дублируется: книги "
                        f"{used_indices[idx]!r} и {book_id!r} соответствуют "
                        f"одному и тому же индексу"
                    )

                id_to_index[book_id] = idx
                used_indices[idx] = book_id

            # Проверка соответствия матрицы и отображения:
            # строго одна книга на одну строку матрицы.
            if len(id_to_index) != n_rows:
                raise NeuralRecommenderError(
                    f"Количество записей в отображении ID ({len(id_to_index)}) "
                    f"не соответствует количеству строк матрицы ({n_rows}). "
                    f"Ожидается строго одно соответствие на строку матрицы."
                )

            # Все индексы от 0 до n_rows - 1 должны использоваться ровно один раз.
            expected_indices = set(range(n_rows))
            actual_indices = set(used_indices.keys())
            if actual_indices != expected_indices:
                missing_indices = sorted(expected_indices - actual_indices)
                extra_indices = sorted(actual_indices - expected_indices)
                msg = "Индексы матрицы используются некорректно."
                if missing_indices:
                    msg += f" Не используются индексы: {missing_indices}."
                if extra_indices:
                    msg += f" Лишние индексы: {extra_indices}."
                raise NeuralRecommenderError(msg)

            self._embeddings = embeddings
            self._id_to_index = id_to_index
            self._index_to_id = {idx: bid for bid, idx in id_to_index.items()}
            self._embedding_dim = dim
            self._metadata = metadata
            self._load_error = None
            logger.info(
                f"Загружены эмбеддинги: {n_rows} книг, размерность {dim}, "
                f"записей в отображении: {len(id_to_index)}, "
                f"generation_id={metadata.get('generation_id')}"
            )

        except NeuralRecommenderError as exc:
            self._clear_load_state()
            self._load_error = str(exc)
            self._loaded = True
            raise
        except Exception as exc:  # noqa: BLE001 — причина логируется и пробрасывается
            self._clear_load_state()
            self._load_error = str(exc)
            self._loaded = True
            logger.error(f"Ошибка загрузки эмбеддингов: {exc}")
            raise NeuralRecommenderError(f"Не удалось загрузить эмбеддинги: {exc}")

        self._loaded = True

    def is_available(self) -> bool:
        """Возвращает True, если эмбеддинги успешно загружены и готовы к использованию.

        Повреждённые или отсутствующие файлы не считываются повторно при
        каждом вызове: результат первого intentos кэшируется в _loaded /
        _load_error. Повторная попытка возможна только через reload_embeddings().
        """
        self._load()
        return (
            self._embeddings is not None
            and self._id_to_index is not None
            and self._load_error is None
        )

    # ------------------------------------------------------------------ #
    # Вспомогательные методы для работы с профилями
    # ------------------------------------------------------------------ #
    @staticmethod
    def _safe_normalize(vector: np.ndarray) -> Optional[np.ndarray]:
        """L2-нормирование вектора. Возвращает None для нулевого/некорректного вектора."""
        if vector is None or vector.size == 0:
            return None
        try:
            norm = float(np.linalg.norm(vector))
        except Exception:  # числовое переполнение при вычислении нормы
            return None
        if norm == 0.0 or not np.isfinite(norm):
            return None
        return vector / norm

    def _build_profiles(
        self, ratings_qs
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Формирует отдельные положительный и отрицательный профили preference.

        Правила весов (шкала 1–5, нейтрал = 3):
          - оценка > 3: положительный вес = (оценка − 3) / (5 − 3)
          - оценка < 3: отрицательный вес = (3 − оценка) / (3 − 1)
          - оценка == 3: нейтральная, не включается ни в один профиль.

        Оценки за пределами фактического диапазона модели BookRating игнорируются.
        Каждый эмбеддинг предварительно L2-нормируется.

        Возвращает (positive_profile, negative_profile). Каждый профиль —
        нормированный вектор или None, если подходящих оценок нет.
        """
        positive_embs: List[np.ndarray] = []
        positive_weights: List[float] = []
        negative_embs: List[np.ndarray] = []
        negative_weights: List[float] = []

        for r in ratings_qs:
            bid = r.book_id
            if bid not in self._id_to_index:
                continue  # для книги нет эмбеддинга — пропускаем

            idx = self._id_to_index[bid]
            raw_emb = self._embeddings[idx]

            emb = self._safe_normalize(raw_emb)
            if emb is None:
                continue  # нулевой или некорректный вектор — не влияет на профиль

            val = float(r.value)

            # Проверка фактического диапазона оценок модели BookRating.
            if val < self.MIN_RATING or val > self.MAX_RATING:
                logger.warning(
                    f"Оценка {val} для книги id={bid} вне диапазона "
                    f"[{self.MIN_RATING}, {self.MAX_RATING}], игнорируется при "
                    f"построении профиля пользователя {r.user_id}"
                )
                continue

            if val > self.NEUTRAL_RATING:
                weight = (val - self.NEUTRAL_RATING) / (self.MAX_RATING - self.NEUTRAL_RATING)
                positive_embs.append(emb)
                positive_weights.append(weight)
            elif val < self.NEUTRAL_RATING:
                weight = (self.NEUTRAL_RATING - val) / (self.NEUTRAL_RATING - self.MIN_RATING)
                negative_embs.append(emb)
                negative_weights.append(weight)
            # val == NEUTRAL_RATING: не добавляем ни в какой профиль.

        # -------- Положительный профиль -------- #
        positive_profile: Optional[np.ndarray] = None
        if positive_embs:
            pe = np.asarray(positive_embs, dtype=np.float32)
            pw = np.asarray(positive_weights, dtype=np.float32)
            pos = np.sum(pe * pw[:, np.newaxis], axis=0)
            positive_profile = self._safe_normalize(pos)
            if positive_profile is None:
                logger.warning("Положительный профиль выродился в нулевой вектор")

        # -------- Отрицательный профиль -------- #
        negative_profile: Optional[np.ndarray] = None
        if negative_embs:
            ne = np.asarray(negative_embs, dtype=np.float32)
            nw = np.asarray(negative_weights, dtype=np.float32)
            neg = np.sum(ne * nw[:, np.newaxis], axis=0)
            negative_profile = self._safe_normalize(neg)
            if negative_profile is None:
                logger.warning("Отрицательный профиль выродился в нулевой вектор")

        return positive_profile, negative_profile

    # ------------------------------------------------------------------ #
    # Публичный API
    # ------------------------------------------------------------------ #
    def recommend(self, user, top_n: int = 20) -> List[Book]:
        """
        Возвращает список книг, отсортированный по убыванию итогового скорa.

        Итоговый скор:
          score = cosine_sim(candidate, positive_profile)
                − negative_weight * cosine_sim(candidate, negative_profile)

        Если только один профиль доступен, используется только он
        (без штрафа или без базы сходства соответственно).
        Если оба профиля отсутствуют — возбуждается NeuralRecommenderError.

        score является показателем ранжирования, а не предсказанной оценкой книги.

        Каждому объекту Book добавляется атрибут recommend_score (float).
        """
        self._load()

        # --- Валидация top_n --------------------------------------------- #
        if not isinstance(top_n, int) or isinstance(top_n, bool) or top_n <= 0:
            raise NeuralRecommenderError(
                f"top_n должен быть положительным целым числом, получено: {top_n!r}"
            )

        if not user.is_authenticated:
            raise NeuralRecommenderError("Пользователь не аутентифицирован.")

        if not self.is_available():
            msg = self._load_error or "Эмбеддинги книг не загружены."
            raise NeuralRecommenderError(
                f"{msg} Поместите book_embeddings.npy, book_id_to_index.json и "
                f"embeddings_metadata.json в директорию {self._embeddings_dir()}. "
                "После появления файлов вызовите reload_embeddings()."
            )

        # Валидация коэффициента отрицательных предпочтений.
        negative_weight = self._get_negative_weight()

        # --- Оценки текущего пользователя -------------------------------- #
        # select_related('book') не требуется: используются только book_id и value.
        ratings_qs = BookRating.objects.filter(user=user)
        if not ratings_qs.exists():
            raise NeuralRecommenderError(
                f"Пользователь {user.get_username()} не имеет оценок книг. "
                "Невозможно сформировать персональный профиль."
            )

        rated_book_ids = {r.book_id for r in ratings_qs}
        read_book_ids = set(
            user.read_books.values_list('pk', flat=True)
        )
        excluded_ids = rated_book_ids | read_book_ids

        # --- Профили предпочтений --------------------------------------- #
        positive_profile, negative_profile = self._build_profiles(ratings_qs)

        if positive_profile is None and negative_profile is None:
            raise NeuralRecommenderError(
                "Не удалось сформировать профили предпочтений. "
                "Все оценки нейтральные (3) или для оценённых книг нет валидных эмбеддингов."
            )

        # --- Кандидаты: существуют в БД, имеют эмбеддинг, не исключены --- #
        embedding_book_ids = set(self._id_to_index.keys())

        # Проверяем, что книги из JSON действительно существуют в PostgreSQL.
        existing_book_ids = set(
            Book.objects
            .filter(pk__in=embedding_book_ids)
            .values_list('pk', flat=True)
        )

        candidate_ids = list(existing_book_ids - excluded_ids)

        if not candidate_ids:
            return []

        candidate_indices = [self._id_to_index[bid] for bid in candidate_ids]
        candidate_embeddings = self._embeddings[candidate_indices]

        # Исключаем книги с нулевыми, неконечными или переполненными эмбеддингами.
        cand_norms = np.linalg.norm(candidate_embeddings, axis=1, keepdims=True)
        cand_norms_flat = cand_norms.squeeze(axis=1)
        finite_embs = np.all(np.isfinite(candidate_embeddings), axis=1)
        finite_norms = np.isfinite(cand_norms_flat)
        valid_mask = (
            finite_embs
            & finite_norms
            & (cand_norms_flat > 0.0)
        )

        if not np.any(valid_mask):
            return []

        candidate_embeddings = candidate_embeddings[valid_mask]
        candidate_ids = [bid for bid, keep in zip(candidate_ids, valid_mask) if keep]
        candidate_indices = [idx for idx, keep in zip(candidate_indices, valid_mask) if keep]

        # Повторный расчёт норм для оставшихся (теперь гарантированно > 0 и конечны).
        cand_norms = np.linalg.norm(candidate_embeddings, axis=1, keepdims=True)
        candidate_normalized = candidate_embeddings / cand_norms

        # --- Итоговый скор: плюс за similarity к положительному, минус за similarity к отрицательному ---
        scores = np.zeros(len(candidate_ids), dtype=np.float32)

        if positive_profile is not None:
            pos_sim = candidate_normalized @ positive_profile
            scores = scores + pos_sim.astype(np.float32)

        if negative_profile is not None:
            neg_sim = candidate_normalized @ negative_profile
            scores = scores - (negative_weight * neg_sim).astype(np.float32)

        # Проверка итоговых оценок: недопустимы NaN и Infinity.
        if not np.all(np.isfinite(scores)):
            bad_count = int(np.sum(~np.isfinite(scores)))
            raise NeuralRecommenderError(
                f"Итоговые score содержат {bad_count} неконечных значений "
                f"(NaN или inf). Рекомендации невозможны."
            )

        # --- Фильтрация: исключаем книги с неположительным score -------------
        # Рекомендуем только книги со score > 0 (строго положительным сходством)
        positive_mask = scores > 0.0
        if not np.any(positive_mask):
            return []
        
        scores = scores[positive_mask]
        candidate_ids = [cid for cid, keep in zip(candidate_ids, positive_mask) if keep]
        candidate_indices = [idx for idx, keep in zip(candidate_indices, positive_mask) if keep]

        # --- Детерминированная сортировка -------------------------------- #
        # Первичный ключ: убывание score. Вторичный: возрастание индекса эмбеддинга
        # (воспроизводимый порядок при равных score).
        order = np.lexsort(
            (np.asarray(candidate_indices, dtype=np.int64), -scores)
        )
        top_order = order[:min(top_n, len(order))]

        top_ids = [candidate_ids[i] for i in top_order]
        top_scores = [float(scores[i]) for i in top_order]

        # --- Загружаем объекты Book и прикрепляем очки ------------------- #
        books_qs = Book.objects.filter(pk__in=top_ids)
        book_map = {b.pk: b for b in books_qs}

        result: List[Book] = []
        for bid, score in zip(top_ids, top_scores):
            book = book_map.get(bid)
            if book is not None:
                book.recommend_score = score
                result.append(book)

        return result


# --- Модульный экземпляр и удобная функция -------------------------------- #

_recommender: Optional[NeuralContentRecommender] = None


def _get_recommender() -> NeuralContentRecommender:
    global _recommender
    if _recommender is None:
        _recommender = NeuralContentRecommender()
    return _recommender


def recommend_books_by_embedding(user, top_n: int = 20) -> List[Book]:
    """
    Публичная функция рекомендаций.

    Args:
        user: объект пользователя Django.
        top_n: сколько книг вернуть (по умолчанию 20).

    Returns:
        Список объектов Book, отсортированных по убыванию recommend_score.
        У каждого объекта установлен атрибут recommend_score (float).

    Raises:
        NeuralRecommenderError: если эмбеддинги отсутствуют, у пользователя
            нет оценок, или нет подходящих кандидатов.
    """
    return _get_recommender().recommend(user, top_n=top_n)
