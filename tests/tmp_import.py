import importlib, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
	sys.path.insert(0, ROOT)
importlib.invalidate_caches()
m = importlib.import_module('app.services.rag_query_service')
print('Imported', getattr(m, '__name__', 'rag_query_service'))
print('Has rag_query_service:', hasattr(m, 'rag_query_service'))
print('Done')
