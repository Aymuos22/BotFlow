"""
Golden dataset schema, loader, and validator.

Dataset format: YAML with a top-level ``version`` key and an ``items`` list.

Each item supports:
  - id                  str (required, unique within dataset)
  - question            str (required)
  - expected_answer     str (optional but strongly recommended)
  - relevant_document_ids  list[str] (UUIDs of ground-truth documents)
  - relevant_chunk_ids     list[str] (e.g. "doc-uuid-chunk-3")
  - relevance_grades       dict[str, int] chunk_id -> 0-3 for graded NDCG
  - category            str (see VALID_CATEGORIES)
  - difficulty          easy | medium | hard
  - language            english | hindi | hinglish
  - answerable          bool (False for unanswerable test cases)
  - metadata            dict (free-form extras)

The loader validates all required fields and logs warnings for soft issues.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

VALID_CATEGORIES = frozenset(
    [
        "factual_lookup",
        "semantic_paraphrase",
        "multi_hop",
        "ambiguous",
        "unanswerable",
        "adversarial",
        "long_context",
        "multilingual",
        "product_recommendation",
        "price_query",
    ]
)

VALID_DIFFICULTIES = frozenset(["easy", "medium", "hard"])
VALID_LANGUAGES = frozenset(["english", "hindi", "hinglish"])


@dataclass
class DatasetItem:
    """One evaluation example."""

    id: str
    question: str
    expected_answer: Optional[str] = None
    relevant_document_ids: List[str] = field(default_factory=list)
    relevant_chunk_ids: List[str] = field(default_factory=list)
    # chunk_id -> relevance grade (0=not relevant, 1=marginally, 2=relevant, 3=highly relevant)
    relevance_grades: Dict[str, int] = field(default_factory=dict)
    category: str = "factual_lookup"
    difficulty: str = "medium"
    language: str = "english"
    answerable: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_ground_truth(self) -> bool:
        """True when the item has at least one ground-truth chunk or document."""
        return bool(self.relevant_chunk_ids or self.relevant_document_ids)

    def grade_for(self, chunk_id: str) -> int:
        """Return the relevance grade for a chunk (defaults to 1 if relevant, 0 otherwise)."""
        if chunk_id in self.relevance_grades:
            return int(self.relevance_grades[chunk_id])
        # Binary relevance: 1 if in the relevant set, 0 otherwise
        if chunk_id in self.relevant_chunk_ids:
            return 1
        return 0


@dataclass
class EvalDataset:
    """Loaded and validated evaluation dataset."""

    version: str
    items: List[DatasetItem]
    source_path: Optional[Path] = None

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def filter_by_language(self, language: str) -> "EvalDataset":
        filtered = [i for i in self.items if i.language == language]
        return EvalDataset(version=self.version, items=filtered, source_path=self.source_path)

    def filter_by_category(self, category: str) -> "EvalDataset":
        filtered = [i for i in self.items if i.category == category]
        return EvalDataset(version=self.version, items=filtered, source_path=self.source_path)

    def filter_answerable(self) -> "EvalDataset":
        filtered = [i for i in self.items if i.answerable]
        return EvalDataset(version=self.version, items=filtered, source_path=self.source_path)

    def summary(self) -> Dict[str, Any]:
        categories: Dict[str, int] = {}
        languages: Dict[str, int] = {}
        for item in self.items:
            categories[item.category] = categories.get(item.category, 0) + 1
            languages[item.language] = languages.get(item.language, 0) + 1
        return {
            "version": self.version,
            "total": len(self.items),
            "answerable": sum(1 for i in self.items if i.answerable),
            "unanswerable": sum(1 for i in self.items if not i.answerable),
            "with_ground_truth": sum(1 for i in self.items if i.has_ground_truth()),
            "categories": categories,
            "languages": languages,
        }


def load_dataset(path: Path) -> EvalDataset:
    """
    Load and validate a golden dataset from a YAML file.

    Raises ``FileNotFoundError`` if the file does not exist.
    Raises ``ValueError`` if the file is malformed.
    Returns an ``EvalDataset`` (may contain items with warnings).
    """
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Dataset YAML must be a mapping, got {type(raw).__name__}")

    version = str(raw.get("version", "unknown"))
    raw_items = raw.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError("Dataset 'items' must be a list")

    items: List[DatasetItem] = []
    seen_ids: set[str] = set()

    for idx, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            logger.warning("Dataset item %d is not a dict; skipping", idx)
            continue

        item_id = raw_item.get("id")
        if not item_id:
            logger.warning("Dataset item %d missing 'id'; skipping", idx)
            continue

        item_id = str(item_id)
        if item_id in seen_ids:
            logger.warning("Duplicate item id %r at index %d; skipping", item_id, idx)
            continue
        seen_ids.add(item_id)

        question = raw_item.get("question")
        if not question:
            logger.warning("Item %r missing 'question'; skipping", item_id)
            continue

        # Optional fields with defaults
        category = str(raw_item.get("category", "factual_lookup"))
        if category not in VALID_CATEGORIES:
            logger.warning(
                "Item %r has unknown category %r; keeping item", item_id, category
            )

        difficulty = str(raw_item.get("difficulty", "medium"))
        if difficulty not in VALID_DIFFICULTIES:
            difficulty = "medium"

        language = str(raw_item.get("language", "english"))
        if language not in VALID_LANGUAGES:
            language = "english"

        relevant_docs = [str(d) for d in (raw_item.get("relevant_document_ids") or [])]
        relevant_chunks = [str(c) for c in (raw_item.get("relevant_chunk_ids") or [])]
        grades_raw = raw_item.get("relevance_grades") or {}
        grades: Dict[str, int] = {}
        if isinstance(grades_raw, dict):
            for k, v in grades_raw.items():
                try:
                    grades[str(k)] = int(v)
                except (TypeError, ValueError):
                    pass

        answerable = bool(raw_item.get("answerable", True))
        expected_answer = raw_item.get("expected_answer")
        if expected_answer is not None:
            expected_answer = str(expected_answer)

        if answerable and not relevant_chunks and not relevant_docs:
            logger.debug(
                "Item %r is answerable but has no ground-truth chunk/doc IDs; "
                "retrieval metrics will be skipped for this item",
                item_id,
            )

        items.append(
            DatasetItem(
                id=item_id,
                question=str(question),
                expected_answer=expected_answer,
                relevant_document_ids=relevant_docs,
                relevant_chunk_ids=relevant_chunks,
                relevance_grades=grades,
                category=category,
                difficulty=difficulty,
                language=language,
                answerable=answerable,
                metadata=raw_item.get("metadata") or {},
            )
        )

    logger.info(
        "Loaded dataset version=%r with %d items from %s", version, len(items), path
    )
    return EvalDataset(version=version, items=items, source_path=path)
