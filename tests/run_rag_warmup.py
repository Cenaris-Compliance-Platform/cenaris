import os, sys, json
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import importlib
importlib.invalidate_caches()

from app.services import rag_query_service as rqs_mod
rqs = rqs_mod.rag_query_service

# Point cache to data/rag/cache unless caller already set one
cache_dir = os.path.abspath(os.path.join(ROOT, 'data', 'rag', 'cache'))
os.environ.setdefault('RAG_EMBED_CACHE_DIR', cache_dir)
os.environ.setdefault('HF_HOME', os.path.abspath(os.path.join(ROOT, 'data', 'rag', 'hf_cache')))

selected_model = os.environ.get('RAG_EMBEDDING_MODEL') or os.environ.get('RAG_EMBEDDING_MODEL'.upper())
if selected_model:
    rqs.EMBEDDING_MODEL = selected_model

corpus_path = os.path.abspath(os.path.join(ROOT, 'data', 'rag', 'test_chunks.jsonl'))
print('Corpus path:', corpus_path)
print('Cache dir:', cache_dir)
print('Selected model:', rqs.EMBEDDING_MODEL)

if (os.environ.get('RAG_WARMUP_DRY_RUN') or '0').strip().lower() in {'1', 'true', 'yes', 'on'}:
    print('Dry run enabled; skipping warmup.')
    raise SystemExit(0)

# Run warmup
print('Starting warmup...')
rqs.warmup(corpus_path=corpus_path)
print('Warmup finished.')

# List cache files and print meta
npy_name = os.path.join(cache_dir, 'test_chunks_embeddings.npy')
meta_name = os.path.join(cache_dir, 'test_chunks_embeddings_meta.json')
print('Exists npy:', os.path.exists(npy_name))
print('Exists meta:', os.path.exists(meta_name))
if os.path.exists(meta_name):
    with open(meta_name, 'r', encoding='utf-8') as fh:
        print('Meta:', json.load(fh))
