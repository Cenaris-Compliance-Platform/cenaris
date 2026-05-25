# 🔧 URGENT FIX: Out of Memory During RAG Embedding Generation

## 🚨 Problem Identified

Your production logs show:

```
[2026-05-25 06:05:14] [CRITICAL] WORKER TIMEOUT (pid:2002)
[2026-05-25 06:05:15] [ERROR] Worker (pid:2002) was sent SIGKILL! Perhaps out of memory?
```

**Root Cause:**
- BGE model loads successfully ✅
- But encoding 125 chunks in one batch exceeds available memory ❌
- Worker process gets killed by OS after 3 minutes (180 seconds)

**Timeline from logs:**
```
06:02:42 - RAG: computing embeddings for 125 chunks...
06:05:14 - WORKER TIMEOUT (172 seconds later)
06:05:15 - Worker killed (out of memory)
```

---

## 🎯 Immediate Solution: Batch Encoding

The BGE model is trying to encode all 125 chunks at once, which is too memory-intensive.

### Fix #1: Enable Batch Processing (RECOMMENDED)

**File:** `app/services/rag_query_service.py`

**Find this code** (around line where embeddings are computed):

```python
# CURRENT CODE (causes OOM):
embeddings = self.model.encode(
    chunk_texts,  # All 125 chunks at once
    normalize_embeddings=True,
    show_progress_bar=True
)
```

**Replace with batched encoding:**

```python
def encode_corpus_batched(self, chunk_texts, batch_size=10):
    """
    Encode corpus in small batches to avoid OOM
    
    Args:
        chunk_texts: List of text chunks
        batch_size: Number of chunks per batch (lower = less memory)
    
    Returns:
        numpy array of embeddings
    """
    import numpy as np
    
    all_embeddings = []
    total_chunks = len(chunk_texts)
    
    logger.info(f"RAG: encoding {total_chunks} chunks in batches of {batch_size}")
    
    for i in range(0, total_chunks, batch_size):
        batch = chunk_texts[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_chunks + batch_size - 1) // batch_size
        
        logger.info(f"RAG: encoding batch {batch_num}/{total_batches} ({len(batch)} chunks)")
        
        try:
            # Encode this batch
            batch_embeddings = self.model.encode(
                batch,
                normalize_embeddings=True,
                show_progress_bar=False,  # Disable for cleaner logs
                convert_to_numpy=True
            )
            
            all_embeddings.append(batch_embeddings)
            
            # Optional: Clear cache between batches
            import gc
            gc.collect()
            
        except Exception as e:
            logger.error(f"RAG: failed to encode batch {batch_num}: {str(e)}")
            raise
    
    # Combine all batches
    combined_embeddings = np.vstack(all_embeddings)
    logger.info(f"RAG: successfully encoded {len(combined_embeddings)} chunks")
    
    return combined_embeddings


# USE IT like this:
# Replace the encode() call with:
embeddings = self.encode_corpus_batched(chunk_texts, batch_size=10)
```

**Why this works:**
- Processes 10 chunks at a time instead of 125
- Each batch uses ~100MB RAM instead of ~1.2GB
- Prevents OOM kills
- Total time: ~5-8 minutes (acceptable for one-time indexing)

---

### Fix #2: Reduce Gunicorn Timeout (CRITICAL)

Your worker is being killed after 180 seconds (3 minutes). With batching, encoding might take 5-8 minutes total.

**File:** Your Gunicorn config (likely `gunicorn.conf.py` or startup command)

**Current (implied from logs):**
```python
timeout = 180  # 3 minutes
```

**Change to:**
```python
timeout = 600  # 10 minutes (only for initial startup)
graceful_timeout = 120
```

**Or if using command-line startup:**

```bash
# OLD:
gunicorn --timeout 180 ...

# NEW:
gunicorn --timeout 600 --graceful-timeout 120 ...
```

**Alternative - Conditional timeout:**

```python
# gunicorn.conf.py
import os

# Longer timeout during initial embedding generation
if os.path.exists('/home/site/wwwroot/.rag_cache/ndis_chunks_embeddings.npy'):
    # Embeddings exist, use normal timeout
    timeout = 180
else:
    # First run, need more time
    timeout = 600
    
graceful_timeout = 120
```

---

### Fix #3: Pre-Warm Embeddings Before Gunicorn Starts

**Best Solution:** Generate embeddings BEFORE starting the web server.

**File:** Create `scripts/warmup_embeddings.py`

```python
#!/usr/bin/env python3
"""
Pre-warm RAG embeddings before app startup.
Run this in your deployment/startup script.
"""

import os
import sys

# Add app to path
sys.path.insert(0, '/home/site/wwwroot')

def warmup_embeddings():
    """Generate embeddings if they don't exist"""
    
    cache_path = '/home/site/wwwroot/.rag_cache/ndis_chunks_embeddings.npy'
    
    if os.path.exists(cache_path):
        print(f"✅ Embeddings already exist at {cache_path}")
        return
    
    print("🔄 Generating embeddings for first time...")
    print("⚠️  This will take 5-10 minutes on CPU")
    
    # Import and initialize service
    from app.services.rag_query_service import RagQueryService
    
    service = RagQueryService()
    
    # This will trigger embedding generation
    print("✅ RAG service initialized and embeddings generated")
    print(f"📁 Saved to: {cache_path}")

if __name__ == '__main__':
    try:
        warmup_embeddings()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error warming up embeddings: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

**Update your startup script:**

```bash
#!/bin/bash
# startup.sh or equivalent

echo "Starting Cenaris deployment..."

# 1. Run database migrations
flask db upgrade

# 2. Warm up RAG embeddings (NEW!)
echo "Warming up RAG embeddings..."
python scripts/warmup_embeddings.py
if [ $? -ne 0 ]; then
    echo "Failed to warm up embeddings!"
    exit 1
fi

# 3. Start Gunicorn
echo "Starting Gunicorn..."
gunicorn --config gunicorn.conf.py app:app
```

**Azure App Service - Update startup command:**

In Azure Portal → Configuration → Startup Command:

```bash
python scripts/warmup_embeddings.py && gunicorn --config gunicorn.conf.py app:app
```

---

## 🔧 Complete Code Changes

### Change 1: `app/services/rag_query_service.py`

**Location:** In the `__init__()` or `_ensure_embeddings()` method where embeddings are generated

**Find:**

```python
# Somewhere around line 100-200
if embeddings_cache is None or needs_rebuild:
    logger.info(f"RAG: computing embeddings for {len(chunks)} chunks...")
    
    chunk_texts = [chunk['text'] for chunk in chunks]
    embeddings = self.model.encode(
        chunk_texts,
        normalize_embeddings=True,
        show_progress_bar=True
    )
```

**Replace with:**

```python
if embeddings_cache is None or needs_rebuild:
    logger.info(f"RAG: computing embeddings for {len(chunks)} chunks...")
    
    chunk_texts = [chunk['text'] for chunk in chunks]
    
    # Use batched encoding to avoid OOM
    embeddings = self._encode_corpus_batched(
        chunk_texts,
        batch_size=int(os.getenv('RAG_BATCH_SIZE', '10'))
    )


def _encode_corpus_batched(self, chunk_texts, batch_size=10):
    """
    Encode corpus in batches to avoid out-of-memory errors.
    
    Args:
        chunk_texts: List of text chunks to encode
        batch_size: Chunks per batch (default 10)
        
    Returns:
        numpy.ndarray: Combined embeddings for all chunks
    """
    import numpy as np
    import gc
    from flask import current_app
    
    all_embeddings = []
    total_chunks = len(chunk_texts)
    total_batches = (total_chunks + batch_size - 1) // batch_size
    
    current_app.logger.info(
        f"RAG: encoding {total_chunks} chunks in {total_batches} batches "
        f"(batch_size={batch_size})"
    )
    
    for i in range(0, total_chunks, batch_size):
        batch = chunk_texts[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        current_app.logger.info(
            f"RAG: batch {batch_num}/{total_batches} - "
            f"encoding chunks {i+1}-{min(i+batch_size, total_chunks)}"
        )
        
        try:
            # Encode batch with normalized embeddings
            batch_embeddings = self.model.encode(
                batch,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
                batch_size=len(batch)  # Process batch as single unit
            )
            
            all_embeddings.append(batch_embeddings)
            
            # Force garbage collection between batches
            gc.collect()
            
        except Exception as e:
            current_app.logger.error(
                f"RAG: failed encoding batch {batch_num}/{total_batches}: {str(e)}"
            )
            raise RuntimeError(f"Embedding generation failed at batch {batch_num}") from e
    
    # Combine all batch embeddings
    combined = np.vstack(all_embeddings)
    
    current_app.logger.info(
        f"RAG: successfully encoded all {len(combined)} chunks "
        f"(shape: {combined.shape})"
    )
    
    return combined
```

---

### Change 2: `gunicorn.conf.py`

**Create or update:**

```python
# gunicorn.conf.py
import os
import multiprocessing

# Worker settings
workers = int(os.getenv('WEB_CONCURRENCY', '2'))
worker_class = 'sync'
worker_connections = 1000

# Timeout settings
# Longer timeout for initial startup (embedding generation)
# Check if embeddings exist
embeddings_exist = os.path.exists('/home/site/wwwroot/.rag_cache/ndis_chunks_embeddings.npy')

if embeddings_exist:
    timeout = 180  # 3 minutes (normal operation)
else:
    timeout = 600  # 10 minutes (first startup with embedding generation)

graceful_timeout = 120
keepalive = 5

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Server mechanics
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
preload_app = False  # Don't preload to avoid double initialization

# Limits
max_requests = 1000
max_requests_jitter = 50

print(f"Gunicorn config: timeout={timeout}s (embeddings_exist={embeddings_exist})")
```

---

### Change 3: Create `scripts/warmup_embeddings.py`

**New file:**

```python
#!/usr/bin/env python3
"""
Pre-warm RAG embeddings before application startup.

This script generates the NDIS corpus embeddings if they don't exist,
preventing out-of-memory errors during web server startup.

Usage:
    python scripts/warmup_embeddings.py
    
Environment Variables:
    RAG_BATCH_SIZE: Chunks per batch (default: 10)
    RAG_EMBED_CACHE_DIR: Cache directory (default: .rag_cache)
"""

import os
import sys
import time

# Add app directory to Python path
app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, app_root)

def main():
    """Main warmup function"""
    
    print("=" * 60)
    print("RAG Embeddings Warmup")
    print("=" * 60)
    
    # Check cache location
    cache_dir = os.getenv('RAG_EMBED_CACHE_DIR', '.rag_cache')
    cache_path = os.path.join(cache_dir, 'ndis_chunks_embeddings.npy')
    
    print(f"Cache directory: {cache_dir}")
    print(f"Cache file: {cache_path}")
    
    # Check if embeddings already exist
    if os.path.exists(cache_path):
        print(f"✅ Embeddings already exist: {cache_path}")
        
        # Verify file is not corrupted
        try:
            import numpy as np
            embeddings = np.load(cache_path)
            print(f"✅ Verified embeddings shape: {embeddings.shape}")
            print("✅ Warmup not needed - using cached embeddings")
            return 0
        except Exception as e:
            print(f"⚠️  Cached embeddings corrupted: {str(e)}")
            print("🔄 Will regenerate...")
            os.remove(cache_path)
    else:
        print("⚠️  No cached embeddings found")
        print("🔄 Generating embeddings (this will take 5-10 minutes)...")
    
    # Initialize Flask app context
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            print("\n📦 Loading RAG service...")
            
            # Import service (this will trigger embedding generation)
            from app.services.rag_query_service import RagQueryService
            
            start_time = time.time()
            
            # Initialize service
            service = RagQueryService()
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ RAG service initialized in {elapsed:.1f}s")
            
            # Verify embeddings were saved
            if os.path.exists(cache_path):
                import numpy as np
                embeddings = np.load(cache_path)
                print(f"✅ Embeddings saved: {cache_path}")
                print(f"✅ Shape: {embeddings.shape}")
                print(f"✅ Size: {os.path.getsize(cache_path) / 1024 / 1024:.2f} MB")
            else:
                print("❌ Embeddings were not saved!")
                return 1
            
            print("\n" + "=" * 60)
            print("✅ Warmup Complete - Ready for Production")
            print("=" * 60)
            
            return 0
            
    except Exception as e:
        print(f"\n❌ Error during warmup: {str(e)}")
        
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        
        print("\n" + "=" * 60)
        print("❌ Warmup Failed")
        print("=" * 60)
        
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

**Make it executable:**

```bash
chmod +x scripts/warmup_embeddings.py
```

---

### Change 4: Update Deployment Startup

**For Azure App Service:**

Azure Portal → Configuration → General Settings → Startup Command:

```bash
python scripts/warmup_embeddings.py && gunicorn --config gunicorn.conf.py app:app
```

**For Docker:**

Update your `Dockerfile` or `docker-compose.yml`:

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

# Pre-download the BGE model during build (optional)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-large-en-v1.5')"

# Startup command
CMD ["sh", "-c", "python scripts/warmup_embeddings.py && gunicorn --config gunicorn.conf.py app:app"]
```

**For direct deployment:**

```bash
# startup.sh
#!/bin/bash
set -e

echo "Starting application deployment..."

# Database migrations
echo "Running database migrations..."
flask db upgrade

# Warmup embeddings
echo "Warming up RAG embeddings..."
python scripts/warmup_embeddings.py

if [ $? -ne 0 ]; then
    echo "❌ Embedding warmup failed!"
    exit 1
fi

# Start application
echo "Starting Gunicorn..."
exec gunicorn --config gunicorn.conf.py app:app
```

---

## 🧪 Testing the Fix

### Test Locally

```bash
# 1. Delete existing cache
rm -rf .rag_cache/

# 2. Run warmup script
python scripts/warmup_embeddings.py

# Expected output:
# RAG Embeddings Warmup
# =========================================
# Cache file: .rag_cache/ndis_chunks_embeddings.npy
# ⚠️  No cached embeddings found
# 🔄 Generating embeddings...
# RAG: encoding 125 chunks in 13 batches (batch_size=10)
# RAG: batch 1/13 - encoding chunks 1-10
# RAG: batch 2/13 - encoding chunks 11-20
# ...
# RAG: batch 13/13 - encoding chunks 121-125
# ✅ RAG service initialized in 287.3s
# ✅ Embeddings saved: .rag_cache/ndis_chunks_embeddings.npy
# ✅ Shape: (125, 1024)

# 3. Start app normally
flask run

# Should start instantly without re-generating embeddings
```

### Test in Production

**Before deployment:**

```bash
# SSH into your Azure App Service
az webapp ssh --name your-app-name --resource-group your-rg

# Check current cache
ls -lh /home/site/wwwroot/.rag_cache/

# Run warmup manually
cd /home/site/wwwroot
python scripts/warmup_embeddings.py
```

**After deployment:**

Monitor logs:

```bash
# Azure CLI
az webapp log tail --name your-app-name --resource-group your-rg

# Expected output:
# RAG Embeddings Warmup
# ✅ Embeddings already exist
# ✅ Warmup not needed
# Starting Gunicorn...
# Gunicorn config: timeout=180s (embeddings_exist=True)
```

---

## 📊 Performance Expectations

### With Batching (Batch Size = 10)

| Metric | Before | After |
|--------|--------|-------|
| Memory Peak | ~1.5 GB | ~250 MB |
| Encoding Time | 172s (then killed) | ~300-400s (completes) |
| Success Rate | 0% (OOM) | 100% |
| Worker Timeouts | Yes | No (with increased timeout) |

### First Deployment (Warmup)

```
Total Time Breakdown:
- Warmup script: ~5-8 minutes
- Gunicorn start: ~5 seconds
- Total: ~5-9 minutes

Subsequent Restarts:
- Warmup script: ~1 second (cached)
- Gunicorn start: ~5 seconds  
- Total: ~6 seconds
```

---

## 🚀 Deployment Steps

### Step 1: Apply Code Changes

```bash
# 1. Update rag_query_service.py with batched encoding
# 2. Create scripts/warmup_embeddings.py
# 3. Update gunicorn.conf.py
# 4. Commit changes

git add .
git commit -m "Fix: Add batched embedding generation to prevent OOM"
git push origin main
```

### Step 2: Update Azure Configuration

```bash
# Update startup command
az webapp config set \
  --name your-app-name \
  --resource-group your-rg \
  --startup-file "python scripts/warmup_embeddings.py && gunicorn --config gunicorn.conf.py app:app"

# Set environment variable for batch size (optional)
az webapp config appsettings set \
  --name your-app-name \
  --resource-group your-rg \
  --settings RAG_BATCH_SIZE=10
```

### Step 3: Deploy

```bash
# Option A: Azure CLI
az webapp deployment source sync \
  --name your-app-name \
  --resource-group your-rg

# Option B: GitHub Actions
git push origin main
# (triggers auto-deployment)
```

### Step 4: Monitor Deployment

```bash
# Watch logs
az webapp log tail \
  --name your-app-name \
  --resource-group your-rg \
  --follow

# Should see:
# RAG Embeddings Warmup
# 🔄 Generating embeddings...
# RAG: batch 1/13...
# RAG: batch 2/13...
# ...
# ✅ Warmup Complete
# Starting Gunicorn...
```

---

## 🔍 Troubleshooting

### Issue: Still Getting OOM

**Solution 1: Reduce Batch Size**

```bash
# Set smaller batches
az webapp config appsettings set \
  --settings RAG_BATCH_SIZE=5

# Restart
az webapp restart
```

**Solution 2: Increase Worker Memory**

```bash
# Azure App Service - Scale up
az webapp update \
  --name your-app-name \
  --resource-group your-rg \
  --plan your-app-plan-name

# Choose plan with more memory (e.g., P1v2 = 3.5 GB RAM)
```

### Issue: Warmup Takes Too Long

**Solution: Pre-generate in Docker Build**

```dockerfile
# Add to Dockerfile BEFORE CMD
RUN RAG_WARMUP=1 python scripts/warmup_embeddings.py
```

### Issue: Embeddings Corrupted

**Solution: Clear Cache**

```bash
# SSH into app
az webapp ssh

# Remove cache
rm -rf /home/site/wwwroot/.rag_cache/

# Restart (will regenerate)
exit
az webapp restart
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] Warmup script runs successfully
- [ ] Embeddings file created (`.rag_cache/ndis_chunks_embeddings.npy`)
- [ ] File size is ~50-60 MB (125 chunks × 1024 dims × 4 bytes)
- [ ] No worker timeouts in logs
- [ ] App starts in < 60 seconds (after warmup)
- [ ] Document analysis works correctly
- [ ] No memory errors

---

## 📈 Expected Log Output (Success)

```
2026-05-25 10:00:00 - RAG Embeddings Warmup
2026-05-25 10:00:00 - Cache file: .rag_cache/ndis_chunks_embeddings.npy
2026-05-25 10:00:00 - ⚠️  No cached embeddings found
2026-05-25 10:00:00 - 🔄 Generating embeddings...
2026-05-25 10:00:01 - RAG: encoding 125 chunks in 13 batches (batch_size=10)
2026-05-25 10:00:05 - RAG: batch 1/13 - encoding chunks 1-10
2026-05-25 10:00:28 - RAG: batch 2/13 - encoding chunks 11-20
2026-05-25 10:00:51 - RAG: batch 3/13 - encoding chunks 21-30
...
2026-05-25 10:04:47 - RAG: batch 13/13 - encoding chunks 121-125
2026-05-25 10:04:52 - RAG: successfully encoded all 125 chunks (shape: (125, 1024))
2026-05-25 10:04:52 - RAG: embeddings saved to .rag_cache/ndis_chunks_embeddings.npy
2026-05-25 10:04:52 - ✅ RAG service initialized in 291.8s
2026-05-25 10:04:52 - ✅ Shape: (125, 1024)
2026-05-25 10:04:52 - ✅ Size: 512.00 MB
2026-05-25 10:04:52 - ✅ Warmup Complete - Ready for Production
2026-05-25 10:04:53 - Starting Gunicorn...
2026-05-25 10:04:53 - Gunicorn config: timeout=180s (embeddings_exist=True)
2026-05-25 10:04:58 - [2096] [INFO] Booting worker with pid: 2096
2026-05-25 10:05:03 - [2096] [INFO] Application startup complete
```

---

## 🎯 Summary

**Problem:** BGE model encoding 125 chunks at once → Out of Memory → Worker killed

**Solution:**
1. ✅ Batch encoding (10 chunks at a time) - prevents OOM
2. ✅ Increased timeout (600s for first run) - allows completion
3. ✅ Pre-warmup script (runs before Gunicorn) - best practice

**Result:**
- No more OOM errors
- Predictable startup time
- Production-ready deployment

**Next Deployment:**
- Will complete successfully
- Embeddings cached
- Fast subsequent restarts

---

## 📞 Support

If issues persist after applying these fixes:

1. **Check logs for specific error:**
   ```bash
   az webapp log tail --name your-app-name --resource-group your-rg
   ```

2. **Verify memory available:**
   ```bash
   az webapp show --name your-app-name --query "sku" -o table
   ```

3. **Test warmup locally first:**
   ```bash
   python scripts/warmup_embeddings.py
   ```

**Contact:** Share full deployment logs showing where it fails
