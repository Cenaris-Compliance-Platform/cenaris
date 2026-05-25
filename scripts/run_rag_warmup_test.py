from app.services.rag_query_service import rag_query_service
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
corpus = os.path.join(ROOT, 'data', 'rag', 'test_corpus.jsonl')
print('Using corpus:', corpus)
rag_query_service.warmup(corpus_path=corpus)
print('Warmup finished')
