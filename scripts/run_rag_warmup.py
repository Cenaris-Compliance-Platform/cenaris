from app.services.rag_query_service import rag_query_service


def main() -> None:
<<<<<<< HEAD
    rag_query_service.warmup(corpus_path='data/rag/ndis/ndis_chunks.jsonl')
    print('Warmup complete.')
=======
    result = rag_query_service.query(
        corpus_path='data/rag/ndis/ndis_chunks.jsonl',
        query_text='NDIS consent procedures and privacy requirements',
        requirement_id='',
        top_k=3,
    )
    print('retrieval_mode:', result.retrieval_mode)
    print('citations:', len(result.citations))
>>>>>>> origin/Preview


if __name__ == '__main__':
    main()
