import os
import tempfile

import pytest

from backend.ingestion.chunking.recursive_chunker import RecursiveChunker
from backend.ingestion.cleaning.text_cleaner import clean_page_text
from backend.ingestion.parsers.base import ParsedPage
from backend.ingestion.parsers.txt_parser import TXTParser


def test_txt_parser_reads_content():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("Hello world. This is a test document for Verity.")
        path = f.name

    try:
        pages = TXTParser().parse(path)
        assert len(pages) == 1
        assert "Hello world" in pages[0].text
        assert pages[0].page_number is None
    finally:
        os.unlink(path)


def test_recursive_chunker_splits_large_text():
    pages = [ParsedPage(text="word " * 500, page_number=1)]
    chunks = RecursiveChunker(chunk_size=100, chunk_overlap=20).chunk(pages)
    assert len(chunks) > 1
    assert all(c.word_count > 0 for c in chunks)


def test_chunk_indexes_are_sequential():
    pages = [ParsedPage(text="word " * 1000, page_number=1)]
    chunks = RecursiveChunker(chunk_size=100, chunk_overlap=0).chunk(pages)
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_chunker_preserves_page_number():
    pages = [ParsedPage(text="word " * 300, page_number=7)]
    chunks = RecursiveChunker(chunk_size=100, chunk_overlap=0).chunk(pages)
    assert all(c.page_number == 7 for c in chunks)


def test_clean_page_text_strips_control_chars():
    # PDF extraction can emit NUL/control bytes that PostgreSQL TEXT rejects.
    raw = "Readable sentence one.\x00 Readable sentence two\x0b with a vertical tab."
    cleaned = clean_page_text(raw)
    assert "\x00" not in cleaned
    assert "\x0b" not in cleaned
    assert "Readable sentence one" in cleaned
    assert "Readable sentence two" in cleaned
