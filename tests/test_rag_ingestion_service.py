from app.services.rag_ingestion_service import RagIngestionService


def test_chunk_pages_splits_long_text_with_overlap():
    svc = RagIngestionService()
    text = "A" * 900 + " " + "B" * 900
    chunks = svc.chunk_pages([(1, text)], chunk_chars=700, overlap_chars=100)

    assert len(chunks) >= 2
    assert all(chunk["page_number"] == 1 for chunk in chunks)
    assert all(chunk["text"] for chunk in chunks)


def test_chunk_pages_ignores_empty_page_text():
    svc = RagIngestionService()
    chunks = svc.chunk_pages([(1, "   \n\n  "), (2, "Real content")], chunk_chars=300, overlap_chars=50)

    assert len(chunks) == 1
    assert chunks[0]["page_number"] == 2
    assert "Real content" in chunks[0]["text"]
