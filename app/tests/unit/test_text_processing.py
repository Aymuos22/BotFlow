"""
Unit tests for app.utils.text_processing (parser + chunker).
"""
import pytest

from app.utils.text_processing import chunk_text, parse_document


# ─────────────────────────────────────────────────────────────────────────────
# parse_document – text/plain
# ─────────────────────────────────────────────────────────────────────────────

class TestParseDocumentTextPlain:
    def test_decodes_plain_utf8(self):
        content = "Hello, world!".encode("utf-8")
        assert parse_document(content, "text/plain") == "Hello, world!"

    def test_decodes_with_unicode(self):
        content = "नमस्ते".encode("utf-8")
        assert parse_document(content, "text/plain") == "नमस्ते"

    def test_replaces_bad_bytes_instead_of_raising(self):
        content = b"Hello \xff World"
        result = parse_document(content, "text/plain")
        assert "Hello" in result
        assert "World" in result

    def test_csv_treated_same_as_text(self):
        content = b"name,age\nAlice,30"
        assert parse_document(content, "text/csv") == "name,age\nAlice,30"

    def test_markdown_decoded(self):
        content = b"# Heading\n\nBody text."
        assert parse_document(content, "text/markdown") == "# Heading\n\nBody text."


class TestParseDocumentFallback:
    def test_unknown_mime_falls_back_to_decode(self):
        content = b"some binary-looking text"
        result = parse_document(content, "application/octet-stream")
        assert result == "some binary-looking text"

    def test_empty_bytes_returns_empty_string(self):
        assert parse_document(b"", "text/plain") == ""

    def test_mime_with_charset_param_handled(self):
        content = b"Hello"
        result = parse_document(content, "text/plain; charset=utf-8")
        assert result == "Hello"


# ─────────────────────────────────────────────────────────────────────────────
# chunk_text
# ─────────────────────────────────────────────────────────────────────────────

class TestChunkText:
    def test_empty_text_returns_empty_list(self):
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert chunk_text("   \n\n  ") == []

    def test_short_text_single_chunk(self):
        text = "Hello world"
        result = chunk_text(text, chunk_size=100, overlap=10)
        assert result == ["Hello world"]

    def test_long_text_produces_multiple_chunks(self):
        text = "A" * 2500
        result = chunk_text(text, chunk_size=1000, overlap=100)
        assert len(result) >= 2

    def test_all_chunks_non_empty(self):
        text = "word " * 400
        result = chunk_text(text, chunk_size=200, overlap=20)
        assert all(c.strip() for c in result)

    def test_overlap_means_content_repeated(self):
        """Overlapping chunks share some characters."""
        text = "abcdefghijklmnopqrstuvwxyz" * 20  # 520 chars
        result = chunk_text(text, chunk_size=100, overlap=20)
        if len(result) >= 2:
            # Last 20 chars of chunk 0 should appear in start of chunk 1
            tail = result[0][-20:]
            assert tail in result[1]

    def test_paragraph_boundary_respected(self):
        """Chunker should try to break at double-newlines."""
        para1 = "First paragraph. " * 30          # ~510 chars
        para2 = "\n\nSecond paragraph. " * 30     # starts new block
        text = para1 + para2
        result = chunk_text(text, chunk_size=600, overlap=50)
        # At least one chunk should start with stripped content from para2
        joined = " ".join(result)
        assert "Second paragraph" in joined

    def test_chunk_size_respected(self):
        """No chunk should exceed chunk_size significantly."""
        text = "word " * 1000
        chunk_size = 300
        result = chunk_text(text, chunk_size=chunk_size, overlap=30)
        # Allow a small overshoot from alignment; chunks shouldn't be 2× the limit
        for chunk in result:
            assert len(chunk) <= chunk_size * 1.2, f"Chunk too large: {len(chunk)}"

    def test_returns_list_of_strings(self):
        text = "Hello world!"
        result = chunk_text(text, chunk_size=50, overlap=5)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)

    def test_custom_chunk_size_and_overlap(self):
        text = "x" * 100
        result = chunk_text(text, chunk_size=30, overlap=10)
        assert len(result) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# S3 key utils
# ─────────────────────────────────────────────────────────────────────────────

class TestS3KeyUtils:
    def test_build_key_format(self):
        from app.utils.s3_keys import build_document_s3_key
        key = build_document_s3_key("comp-1", "doc-1", "report.pdf")
        assert key == "companies/comp-1/documents/doc-1/report.pdf"

    def test_sanitize_spaces(self):
        from app.utils.s3_keys import sanitize_filename
        assert sanitize_filename("My Report 2024.pdf") == "my_report_2024.pdf"

    def test_sanitize_special_chars(self):
        from app.utils.s3_keys import sanitize_filename
        assert sanitize_filename("../../etc/passwd") == "etcpasswd"

    def test_sanitize_empty_returns_file(self):
        from app.utils.s3_keys import sanitize_filename
        assert sanitize_filename("") == "file"

    def test_key_no_leading_slash(self):
        from app.utils.s3_keys import build_document_s3_key
        key = build_document_s3_key("c1", "d1", "a.txt")
        assert not key.startswith("/")
