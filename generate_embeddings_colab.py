"""Генерация объединённых эмбеддингов книг в Google Colab.

Загрузите этот скрипт и ``books_export.csv`` в Colab, затем запустите его
командой ``%run generate_embeddings_colab.py``. На выходе получится единая
L2-нормированная матрица для рекомендателя Django.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import sentence_transformers
import transformers
from sentence_transformers import SentenceTransformer


# ---- Настройки --------------------------------------------------------------
MODEL_NAME = 'intfloat/multilingual-e5-base'
# После выбора версии модели укажите здесь её commit hash на Hugging Face.
# Значение None использует версию, которую разрешит Hugging Face.
MODEL_REVISION = None
GENERATION_ID = 'emb_e5_fusion_v3_20261116'
TEXT_SCHEMA_VERSION = 'e5_query_metadata_description_fusion_v3'
METADATA_WEIGHT = 0.4
DESCRIPTION_WEIGHT = 0.6
BATCH_SIZE = 64
CSV_PATH = Path('/content/books_export.csv')
OUTPUT_DIR = Path('/content/embeddings_output')

REQUIRED_COLUMNS = {
    'id', 'title', 'author', 'genres', 'release_year', 'description',
}
WHITESPACE_RE = re.compile(r'\s+')
HTML_RE = re.compile(r'<[^>]+>')
REFERENCE_RE = re.compile(r'\[[^\]]*\]')
SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?…])\s+')


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(8192), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require_text(value: object, field: str, book_id: int) -> str:
    if pd.isna(value) or not str(value).strip():
        raise ValueError(f'Book id={book_id}: required field {field!r} is empty')
    return WHITESPACE_RE.sub(' ', str(value)).strip()


def optional_text(value: object) -> str:
    if pd.isna(value):
        return ''
    return WHITESPACE_RE.sub(' ', str(value)).strip()


def normalise_year(value: object, book_id: int) -> str:
    if pd.isna(value) or not str(value).strip():
        return ''
    try:
        numeric_year = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Book id={book_id}: invalid release_year {value!r}') from exc
    if not np.isfinite(numeric_year) or not numeric_year.is_integer():
        raise ValueError(f'Book id={book_id}: invalid release_year {value!r}')
    return str(int(numeric_year))


def clean_wikipedia_description(value: object) -> str:
    """Убирает артефакты оформления, не меняя источник информации.

Источником остаётся текст Wikipedia/Wikidata. Перед созданием эмбеддинга
удаляются только разметка, сноски в квадратных скобках и лишние пробелы.
    """
    text = optional_text(value)
    text = HTML_RE.sub(' ', text)
    text = REFERENCE_RE.sub(' ', text)
    return WHITESPACE_RE.sub(' ', text).strip()


def truncate_at_sentence_boundary(text: str, tokenizer, max_seq_length: int) -> str:
    """По возможности сохраняет начало статьи Wikipedia в лимите модели."""
    if not text:
        return ''

    def token_count(candidate: str) -> int:
        return len(tokenizer(candidate, add_special_tokens=True)['input_ids'])

    if token_count(text) <= max_seq_length:
        return text

    kept = []
    for sentence in SENTENCE_SPLIT_RE.split(text):
        candidate = ' '.join([*kept, sentence]).strip()
        if candidate and token_count(candidate) <= max_seq_length:
            kept.append(sentence)
        else:
            break
    if kept:
        return ' '.join(kept)

    # Если описание состоит из одного очень длинного предложения, безопасно
    # обрезаем его по токенам.
    token_ids = tokenizer(
        text,
        add_special_tokens=False,
        truncation=True,
        max_length=max(1, max_seq_length - 2),
    )['input_ids']
    return tokenizer.decode(token_ids, skip_special_tokens=True).strip()


def build_metadata_text(row: pd.Series) -> str:
    book_id = int(row['id'])
    title = require_text(row['title'], 'title', book_id)
    author = require_text(row['author'], 'author', book_id)
    genres = optional_text(row['genres'])
    year = normalise_year(row['release_year'], book_id)

    parts = [f'Название: {title}', f'Автор: {author}']
    if genres:
        parts.append(f'Жанры: {genres}')
    if year:
        parts.append(f'Год: {year}')
    return '. '.join(parts) + '.'


def add_e5_prefix(text: str) -> str:
    """Добавляет префикс, с которым E5 обучалась сравнивать тексты.

    Рекомендатель сравнивает книги друг с другом, поэтому это симметричная
    задача: один и тот же префикс ``query: `` ставится перед каждым текстом.
    """
    return f'query: {text}'


def l2_normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if not np.all(np.isfinite(vectors)) or not np.all(np.isfinite(norms)):
        raise ValueError('Embeddings contain NaN or infinity')
    if np.any(norms == 0):
        raise ValueError('Cannot normalise a zero embedding')
    return vectors / norms


def main() -> None:
    if not np.isclose(METADATA_WEIGHT + DESCRIPTION_WEIGHT, 1.0):
        raise ValueError('METADATA_WEIGHT and DESCRIPTION_WEIGHT must sum to 1.0')
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dataframe = pd.read_csv(CSV_PATH)
    missing_columns = REQUIRED_COLUMNS - set(dataframe.columns)
    if missing_columns:
        raise ValueError(f'CSV is missing columns: {sorted(missing_columns)}')
    if dataframe['id'].isna().any() or not dataframe['id'].is_unique:
        raise ValueError('Column id must be populated and unique')

    dataframe['id'] = dataframe['id'].astype(int)
    dataframe = dataframe.sort_values('id', kind='stable').reset_index(drop=True)
    ids = dataframe['id'].tolist()

    model_kwargs = {}
    if MODEL_REVISION:
        model_kwargs['revision'] = MODEL_REVISION
    model = SentenceTransformer(MODEL_NAME, **model_kwargs)
    max_seq_length = int(model.max_seq_length)

    e5_prefix_tokens = len(
        model.tokenizer('query: ', add_special_tokens=False)['input_ids']
    )
    description_token_limit = max(1, max_seq_length - e5_prefix_tokens)

    metadata_texts = [
        add_e5_prefix(build_metadata_text(row))
        for _, row in dataframe.iterrows()
    ]
    raw_descriptions = [
        clean_wikipedia_description(row['description'])
        for _, row in dataframe.iterrows()
    ]
    cleaned_descriptions = [
        add_e5_prefix(
            truncate_at_sentence_boundary(
                description,
                model.tokenizer,
                description_token_limit,
            )
        )
        if description
        else ''
        for description in raw_descriptions
    ]

    metadata_embeddings = model.encode(
        metadata_texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)

    # Без описания используем только метаданные, не создавая вектор пустого текста.
    fused_embeddings = metadata_embeddings.copy()
    described_indices = [i for i, text in enumerate(cleaned_descriptions) if text]
    if described_indices:
        description_embeddings = model.encode(
            [cleaned_descriptions[i] for i in described_indices],
            batch_size=BATCH_SIZE,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)
        fused_embeddings[described_indices] = (
            METADATA_WEIGHT * metadata_embeddings[described_indices]
            + DESCRIPTION_WEIGHT * description_embeddings
        )

    embeddings = l2_normalise(fused_embeddings).astype(np.float32)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(ids):
        raise ValueError(f'Unexpected matrix shape: {embeddings.shape}')

    matrix_path = OUTPUT_DIR / 'book_embeddings.npy'
    map_path = OUTPUT_DIR / 'book_id_to_index.json'
    metadata_path = OUTPUT_DIR / 'embeddings_metadata.json'
    np.save(matrix_path, embeddings)

    id_to_index = {int(book_id): index for index, book_id in enumerate(ids)}
    with map_path.open('w', encoding='utf-8') as file:
        json.dump(id_to_index, file, ensure_ascii=False, separators=(',', ':'))

    metadata = {
        'generation_id': GENERATION_ID,
        'model_name': MODEL_NAME,
        'model_revision': MODEL_REVISION,
        'model_version': 'multilingual-e5-base-metadata-description-fusion-v3',
        'sentence_transformers_version': sentence_transformers.__version__,
        'transformers_version': transformers.__version__,
        'embedding_dim': int(embeddings.shape[1]),
        'num_books': int(embeddings.shape[0]),
        'sha256_matrix': sha256_file(matrix_path),
        'sha256_mapping': sha256_file(map_path),
        'sha256_source_csv': sha256_file(CSV_PATH),
        'text_schema_version': TEXT_SCHEMA_VERSION,
        'metadata_weight': METADATA_WEIGHT,
        'description_weight': DESCRIPTION_WEIGHT,
        'model_max_seq_length': max_seq_length,
        'description_max_seq_length': description_token_limit,
        'e5_prefix': 'query: ',
        'described_books': len(described_indices),
    }
    with metadata_path.open('w', encoding='utf-8') as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2, sort_keys=True)

    print(f'Generated matrix: {embeddings.shape}, dtype={embeddings.dtype}')
    print(f'Books with descriptions: {len(described_indices)}/{len(ids)}')
    print(f'Saved files to: {OUTPUT_DIR}')
    print(f'Matrix SHA-256: {metadata["sha256_matrix"]}')
    print(f'Mapping SHA-256: {metadata["sha256_mapping"]}')


if __name__ == '__main__':
    main()
