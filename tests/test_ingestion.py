"""Unit tests for Kavach Ingestion Subsystem."""

import pytest
from pathlib import Path
from src.ingestion.chunker import split_text_recursive, chunk_documents, _detect_clearance
from src.ingestion.indexer import Indexer


def test_split_text_recursive():
    sample_text = "This is a confidential refinery document. " * 30
    chunks = split_text_recursive(sample_text, chunk_size=200, chunk_overlap=40)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 220


def test_detect_clearance():
    assert _detect_clearance("Emergency shutdown override pin is active") == "secret"
    assert _detect_clearance("Confidential financial allocation for MRPL") == "confidential"
    assert _detect_clearance("General plant safety protocol public overview") == "public"


def test_chunk_documents():
    pages = [
        {
            "text": "CDU-III operational report. Confidential processing numbers.",
            "metadata": {"source": "test_report.pdf", "page": 1}
        }
    ]
    chunks = chunk_documents(pages, chunk_size=300, chunk_overlap=50)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "test_report.pdf_p1_c1"
    assert chunks[0].metadata["source"] == "test_report.pdf"
    assert chunks[0].metadata["page"] == 1


def test_indexer_in_memory(tmp_path):
    idx = Indexer(storage_dir=tmp_path)
    pages = [
        {"text": "Refinery CDU-III processes 7.5 MMTPA crude oil.", "metadata": {"source": "doc1.pdf", "page": 1}},
        {"text": "FCCU unit produces high octane gasoline using zeolite.", "metadata": {"source": "doc1.pdf", "page": 2}},
    ]
    chunks = chunk_documents(pages, chunk_size=200, chunk_overlap=20)
    indexed = idx.index_chunks(chunks)
    assert indexed == 2
    assert idx.count() == 2

    # Query search
    res = idx.search("crude oil capacity", top_k=1)
    assert len(res) == 1
    assert "CDU-III" in res[0]["text"]
