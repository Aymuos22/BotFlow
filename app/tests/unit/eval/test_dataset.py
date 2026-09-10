"""
Unit tests for eval/dataset.py.

Tests cover:
  - load_dataset: valid YAML, missing required fields, unknown categories
  - DatasetItem: has_ground_truth, grade_for
  - EvalDataset: filter methods, summary
  - Edge cases: empty items list, duplicate IDs, malformed YAML
"""
import tempfile
from pathlib import Path

import pytest
import yaml

from eval.dataset import load_dataset, DatasetItem, EvalDataset


def _write_yaml(items: list, version: str = "v1") -> Path:
    """Helper: write a YAML dataset to a temp file."""
    d = tempfile.mkdtemp()
    path = Path(d) / "test_dataset.yaml"
    path.write_text(
        yaml.dump({"version": version, "items": items}, allow_unicode=True),
        encoding="utf-8",
    )
    return path


class TestLoadDataset:
    def test_valid_dataset(self):
        path = _write_yaml([
            {
                "id": "test_001",
                "question": "What is your return policy?",
                "expected_answer": "30 days.",
                "relevant_chunk_ids": ["doc1-chunk-0"],
                "category": "factual_lookup",
                "difficulty": "easy",
                "language": "english",
                "answerable": True,
            }
        ])
        ds = load_dataset(path)
        assert len(ds) == 1
        assert ds.version == "v1"
        item = ds.items[0]
        assert item.id == "test_001"
        assert item.question == "What is your return policy?"
        assert item.relevant_chunk_ids == ["doc1-chunk-0"]
        assert item.answerable is True

    def test_missing_id_skips_item(self):
        path = _write_yaml([
            {"question": "No ID here"},
            {"id": "valid_001", "question": "Valid question"},
        ])
        ds = load_dataset(path)
        assert len(ds) == 1
        assert ds.items[0].id == "valid_001"

    def test_missing_question_skips_item(self):
        path = _write_yaml([
            {"id": "no_question"},
            {"id": "has_question", "question": "Hello?"},
        ])
        ds = load_dataset(path)
        assert len(ds) == 1

    def test_duplicate_id_skipped(self):
        path = _write_yaml([
            {"id": "dup_001", "question": "First"},
            {"id": "dup_001", "question": "Second"},
        ])
        ds = load_dataset(path)
        assert len(ds) == 1
        assert ds.items[0].question == "First"

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_dataset(Path("/nonexistent/dataset.yaml"))

    def test_not_a_mapping_raises(self):
        d = tempfile.mkdtemp()
        path = Path(d) / "bad.yaml"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            load_dataset(path)

    def test_unknown_category_kept_with_warning(self):
        path = _write_yaml([
            {"id": "unknown_cat", "question": "Q?", "category": "not_a_real_category"}
        ])
        # Should not raise; item should be kept
        ds = load_dataset(path)
        assert len(ds) == 1
        assert ds.items[0].category == "not_a_real_category"

    def test_defaults_applied(self):
        path = _write_yaml([{"id": "minimal", "question": "Q?"}])
        ds = load_dataset(path)
        item = ds.items[0]
        assert item.category == "factual_lookup"
        assert item.difficulty == "medium"
        assert item.language == "english"
        assert item.answerable is True
        assert item.relevant_chunk_ids == []

    def test_relevance_grades_parsed(self):
        path = _write_yaml([{
            "id": "graded",
            "question": "Q?",
            "relevant_chunk_ids": ["doc1-chunk-0", "doc1-chunk-1"],
            "relevance_grades": {"doc1-chunk-0": 3, "doc1-chunk-1": 1},
        }])
        ds = load_dataset(path)
        item = ds.items[0]
        assert item.grade_for("doc1-chunk-0") == 3
        assert item.grade_for("doc1-chunk-1") == 1
        assert item.grade_for("doc1-chunk-2") == 0  # not in grades

    def test_empty_items_list(self):
        path = _write_yaml([])
        ds = load_dataset(path)
        assert len(ds) == 0


class TestDatasetItem:
    def test_has_ground_truth_with_chunk_ids(self):
        item = DatasetItem(
            id="t1",
            question="Q?",
            relevant_chunk_ids=["doc1-chunk-0"],
        )
        assert item.has_ground_truth() is True

    def test_has_ground_truth_with_doc_ids(self):
        item = DatasetItem(
            id="t1",
            question="Q?",
            relevant_document_ids=["doc1"],
        )
        assert item.has_ground_truth() is True

    def test_has_no_ground_truth(self):
        item = DatasetItem(id="t1", question="Q?")
        assert item.has_ground_truth() is False

    def test_grade_for_in_relevant_chunks_binary(self):
        item = DatasetItem(
            id="t1",
            question="Q?",
            relevant_chunk_ids=["doc1-chunk-0"],
        )
        assert item.grade_for("doc1-chunk-0") == 1
        assert item.grade_for("doc1-chunk-1") == 0

    def test_grade_for_with_grades(self):
        item = DatasetItem(
            id="t1",
            question="Q?",
            relevant_chunk_ids=["doc1-chunk-0"],
            relevance_grades={"doc1-chunk-0": 3},
        )
        assert item.grade_for("doc1-chunk-0") == 3


class TestEvalDataset:
    def _make_ds(self, items):
        return EvalDataset(version="v1", items=items)

    def test_filter_by_language(self):
        items = [
            DatasetItem(id="en1", question="Q1", language="english"),
            DatasetItem(id="hi1", question="Q2", language="hindi"),
            DatasetItem(id="en2", question="Q3", language="english"),
        ]
        ds = self._make_ds(items)
        filtered = ds.filter_by_language("english")
        assert len(filtered) == 2

    def test_filter_by_category(self):
        items = [
            DatasetItem(id="f1", question="Q1", category="factual_lookup"),
            DatasetItem(id="a1", question="Q2", category="adversarial"),
        ]
        ds = self._make_ds(items)
        filtered = ds.filter_by_category("adversarial")
        assert len(filtered) == 1

    def test_filter_answerable(self):
        items = [
            DatasetItem(id="a1", question="Q1", answerable=True),
            DatasetItem(id="u1", question="Q2", answerable=False),
        ]
        ds = self._make_ds(items)
        filtered = ds.filter_answerable()
        assert len(filtered) == 1
        assert filtered.items[0].answerable is True

    def test_summary(self):
        items = [
            DatasetItem(id="e1", question="Q1", category="factual_lookup", language="english"),
            DatasetItem(id="h1", question="Q2", category="multilingual", language="hindi"),
            # Explicitly set language=hindi for the unanswerable item to avoid
            # relying on the default (which is english)
            DatasetItem(id="u1", question="Q3", answerable=False, category="unanswerable",
                        language="hindi"),
        ]
        ds = self._make_ds(items)
        summary = ds.summary()
        assert summary["total"] == 3
        assert summary["answerable"] == 2
        assert summary["unanswerable"] == 1
        assert summary["categories"]["factual_lookup"] == 1
        assert summary["languages"]["english"] == 1
        assert summary["languages"]["hindi"] == 2
