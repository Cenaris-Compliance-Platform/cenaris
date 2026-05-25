from app.services.rag_query_service import rag_query_service


def main() -> None:
    rag_query_service.warmup(corpus_path='data/rag/ndis/ndis_chunks.jsonl')
    print('Warmup complete.')


if __name__ == '__main__':
    main()
