# 🚀 Cenaris RAG Improvement Roadmap
## NDIS Corpus-Only Approach (No Training Required)

**Goal:** Improve RAG retrieval quality using only NDIS official documents as corpus, with zero custom training and minimal hardware requirements.

**Current Status:** ⚠️ Working but with accuracy issues
**Target Status:** ✅ High-quality compliance assessment with better citations

---

## Table of Contents

1. [Understanding Your Current Setup](#understanding-your-current-setup)
2. [What We're NOT Doing (Important!)](#what-were-not-doing)
3. [What We ARE Doing](#what-we-are-doing)
4. [Week 1: Quick Wins (Immediate Impact)](#week-1-quick-wins)
5. [Week 2: Core Improvements](#week-2-core-improvements)
6. [Week 3: Polish & Testing](#week-3-polish--testing)
7. [Complete Code Changes](#complete-code-changes)
8. [Testing & Validation](#testing--validation)
9. [Future Roadmap (When You Have User Data)](#future-roadmap)

---

## Understanding Your Current Setup

### Your Architecture (Correct Approach!)

```
┌─────────────────────────────────────────────────────────────┐
│                     USER UPLOADS DOCUMENT                   │
│                      (Policy/Procedure)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  TEXT EXTRACTION                            │
│              (pypdf, fitz, pdfplumber)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  YOUR RAG SYSTEM                            │
│                                                             │
│  1. Build query from document content                       │
│  2. Search NDIS corpus (embeddings + lexical)               │
│  3. Return top 3 matching NDIS standards                    │
│                                                             │
│  CORPUS: NDIS Practice Standards (official docs)            │
│  MODEL: all-MiniLM-L6-v2 (pre-trained, downloaded)          │
│  SEARCH: Cosine similarity + keyword matching               │
│                                                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  SCORING ENGINE                             │
│                                                             │
│  Score document against NDIS requirements                   │
│  using retrieved citations as evidence                      │
│                                                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  SHOW RESULTS TO USER                       │
│                                                             │
│  Status: Critical Gap / High Risk / OK / Mature             │
│  Confidence: 25%                                            │
│  Citations: 3 NDIS standards                                │
│  Actions: What to fix                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**✅ This is the RIGHT architecture!**

---

## What We're NOT Doing

### ❌ Things You DON'T Need (Ignore These)

1. **❌ Training a custom LLM**
   - Cost: $10,000 - $100,000+
   - Hardware: Requires expensive GPUs
   - Time: Weeks/months
   - **You DON'T need this!**

2. **❌ Fine-tuning an embedding model**
   - Cost: $1,000 - $5,000
   - Hardware: Requires GPU
   - Data: Needs 10,000+ training examples
   - **You DON'T need this!**

3. **❌ Building a custom model from scratch**
   - Cost: $50,000+
   - Hardware: Massive GPU clusters
   - Time: Months
   - **You DON'T need this!**

4. **❌ Collecting user documents as training data**
   - Privacy issues
   - Need thousands of examples
   - Labeling cost: $10,000+
   - **You DON'T need this yet!**

### Why You Don't Need These

**RAG works by searching, not learning:**
- You already have the "knowledge" (NDIS corpus)
- You just need better search/retrieval
- Pre-trained models already understand English, compliance language, etc.
- You're just swapping tools, not training them

**Analogy:**
- ❌ Training = Building a search engine from scratch (Google-level effort)
- ✅ RAG = Using Google to search your own documents (easy!)

---

## What We ARE Doing

### ✅ Simple, No-Training Improvements

1. **✅ Download a better pre-trained embedding model**
   - Cost: $0 (free, open-source)
   - Hardware: CPU only, no GPU needed
   - Time: 10 minutes to download
   - One-time effort

2. **✅ Re-embed your NDIS corpus with better model**
   - Cost: $0
   - Hardware: CPU is fine (takes 5-30 minutes once)
   - One-time effort
   - After this, searches are instant

3. **✅ Improve query construction (code changes)**
   - Cost: $0
   - Hardware: None needed
   - Time: 1-2 hours of coding
   - Better search queries = better results

4. **✅ Retrieve more citations, filter for quality**
   - Cost: $0
   - Hardware: None needed
   - Time: 1-2 hours of coding
   - More comprehensive results

5. **✅ Add pre-validation gates (code changes)**
   - Cost: $0
   - Hardware: None needed
   - Time: 2-3 hours of coding
   - Reject bad documents before scoring

---

## Week 1: Quick Wins (Immediate Impact)

### 🎯 Goal: Fix the biggest issues with minimal code changes

**Estimated Time:** 6-8 hours total
**Hardware Needed:** Your current laptop/server (CPU only)
**Cost:** $0

---

### Task 1.1: Add Pre-Validation Gates (2 hours)

**Problem:** Blank templates and irrelevant documents score too high

**Solution:** Reject bad documents BEFORE scoring

**Files to Edit:**
- `document_analysis_service.py`

**What to Do:**

1. Add new function at the top of `document_analysis_service.py`:

```python
def validate_document_before_scoring(text, file_path):
    """
    Validate document before any scoring begins.
    Returns rejection if document is invalid.
    """
    import re
    import os
    
    # ==========================================
    # GATE 1: Minimum Length Check
    # ==========================================
    if len(text.strip()) < 100:
        return {
            'valid': False,
            'reason': 'DOCUMENT_TOO_SHORT',
            'confidence': 12,
            'status': 'CRITICAL_GAP',
            'message': 'Document contains less than 100 characters. Cannot perform meaningful compliance assessment.'
        }
    
    # ==========================================
    # GATE 2: Blank Template Detection
    # ==========================================
    
    # Count template markers
    bracket_placeholders = len(re.findall(r'\[[^\]]{0,30}\]', text))  # [NAME], [DATE]
    underscores = len(re.findall(r'_{4,}', text))  # ____
    dots = len(re.findall(r'\.{4,}', text))  # ....
    form_labels = len(re.findall(r'(?:name|date|signature|signed):\s*[_\.]{2,}', text, re.IGNORECASE))
    
    total_markers = bracket_placeholders + underscores + dots + form_labels
    
    # Calculate fill ratio
    text_no_markers = text
    for pattern in [r'\[[^\]]{0,30}\]', r'_{4,}', r'\.{4,}']:
        text_no_markers = re.sub(pattern, '', text_no_markers)
    
    fill_ratio = len(text_no_markers.strip()) / max(len(text), 1)
    word_count = len(re.findall(r'\b\w+\b', text))
    
    # HARD REJECTION for blank templates
    if (total_markers >= 10 and fill_ratio < 0.40) or \
       (total_markers >= 6 and word_count < 300) or \
       (total_markers >= 5 and fill_ratio < 0.25):
        return {
            'valid': False,
            'reason': 'BLANK_TEMPLATE',
            'confidence': 15,
            'status': 'CRITICAL_GAP',
            'message': f'Document is a blank template with {total_markers} unfilled sections. Complete all placeholders before assessment.',
            'markers_found': total_markers
        }
    
    # SOFT PENALTY for partial templates
    if (total_markers >= 4 and fill_ratio < 0.65):
        return {
            'valid': True,  # Allow scoring but penalize
            'reason': 'PARTIAL_TEMPLATE',
            'confidence_cap': 42,
            'penalty_multiplier': 0.50,
            'message': f'Document appears partially incomplete ({total_markers} unfilled sections).'
        }
    
    # ==========================================
    # GATE 3: Invalid Document Type Detection
    # ==========================================
    
    text_lower = text.lower()
    
    # Check for non-policy document types
    invalid_types = {
        'email': ['from:', 'to:', 'subject:', 'sent:', 'dear', 'regards,'],
        'resume': ['curriculum vitae', 'work experience', 'education:', 'references available'],
        'invoice': ['invoice number', 'total due', 'payment terms', 'abn:'],
        'marketing': ['call us now', 'visit our website', 'book now', 'limited time'],
        'news': ['breaking news', 'announced today', 'sources say'],
    }
    
    for doc_type, keywords in invalid_types.items():
        matches = sum(1 for kw in keywords if kw in text_lower)
        if matches >= 2:  # 2+ matches = likely that type
            return {
                'valid': False,
                'reason': f'INVALID_TYPE_{doc_type.upper()}',
                'confidence': 18,
                'status': 'CRITICAL_GAP',
                'message': f'Document appears to be a {doc_type}, not a compliance policy or procedure.'
            }
    
    # ==========================================
    # GATE 4: PDF Quality Check
    # ==========================================
    
    if file_path and file_path.endswith('.pdf'):
        try:
            file_size_kb = os.path.getsize(file_path) / 1024
            chars_per_kb = len(text) / max(file_size_kb, 0.1)
            
            # Image-only PDF (very low text density)
            if chars_per_kb < 150:
                return {
                    'valid': False,
                    'reason': 'IMAGE_PDF',
                    'confidence': 14,
                    'status': 'CRITICAL_GAP',
                    'message': 'Scanned/image-only PDF with minimal extractable text. Please upload a text-based PDF or use OCR software.'
                }
            
            # Low-quality scan
            if chars_per_kb < 500:
                return {
                    'valid': True,
                    'reason': 'LOW_QUALITY_SCAN',
                    'confidence_cap': 38,
                    'penalty_multiplier': 0.62,
                    'message': f'Low text extraction quality ({chars_per_kb:.0f} chars/KB). Consider uploading higher quality scan.'
                }
        except:
            pass  # If file size check fails, continue anyway
    
    # ==========================================
    # All Gates Passed
    # ==========================================
    return {'valid': True, 'reason': 'OK'}
```

2. Call this function EARLY in your analysis pipeline:

```python
# In document_analysis_service.py - inside analyze_document() function
# ADD THIS right after text extraction, BEFORE any scoring

validation = validate_document_before_scoring(normalized_text, file_path)

if not validation['valid']:
    # Return rejection immediately - no scoring needed
    return {
        'status': validation['status'],
        'confidence': validation['confidence'],
        'raw_score': validation['confidence'],
        'reason': validation['reason'],
        'summary': validation['message'],
        'warning_items': [{
            'category': 'VALIDATION',
            'severity': 'CRITICAL',
            'message': validation['message']
        }],
        'score_breakdown': None,
        'citations': [],
        'evidence_snippets': []
    }

# If valid but with penalties, store for later use
document_penalty = validation.get('penalty_multiplier', 1.0)
confidence_cap = validation.get('confidence_cap', 100)
```

3. Apply penalties during final scoring:

```python
# Later in your scoring code, AFTER calculating raw_score:

if document_penalty < 1.0:
    raw_score = raw_score * document_penalty
    
if confidence_cap < 100:
    final_confidence = min(final_confidence, confidence_cap)
```

**Expected Result:**
- Blank templates: Now 15% (was 25%)
- Marketing docs: Now rejected (was 40-50%)
- Scanned PDFs: Now rejected or capped at 38%

**Time:** 2 hours (copy code, test)

---

### Task 1.2: Retrieve More Citations (1 hour)

**Problem:** Only retrieving 3 citations misses relevant NDIS standards

**Solution:** Retrieve 15 initially, filter to top 5-7

**Files to Edit:**
- `document_analysis_service.py`

**What to Do:**

1. Find where you call `self.rag_service.retrieve()`:

```python
# OLD CODE (find this line)
citations = self.rag_service.retrieve(expanded_query, top_k=3)

# REPLACE WITH
raw_citations = self.rag_service.retrieve(expanded_query, top_k=15)
```

2. Add filtering function:

```python
def filter_quality_citations(citations, document_text, min_score=0.65):
    """
    Filter citations for quality and relevance.
    Returns top 5-7 high-quality citations.
    """
    import re
    
    filtered = []
    
    for citation in citations:
        # Rule 1: Minimum score threshold
        if citation.get('score', 0) < min_score:
            continue
        
        citation_text = citation.get('text', '').lower()
        
        # Rule 2: Must contain actionable language
        has_action_words = any(word in citation_text for word in [
            'must', 'shall', 'will', 'ensure', 'required', 
            'responsible', 'documented', 'procedure'
        ])
        
        if not has_action_words:
            continue
        
        # Rule 3: Not too short (avoid headers only)
        if len(citation.get('text', '')) < 80:
            continue
        
        # Rule 4: Terminology overlap with document
        doc_words = set(re.findall(r'\b\w{5,}\b', document_text.lower()))
        citation_words = set(re.findall(r'\b\w{5,}\b', citation_text))
        
        if len(doc_words) > 0 and len(citation_words) > 0:
            overlap = len(doc_words & citation_words) / len(doc_words | citation_words)
        else:
            overlap = 0
        
        # Need at least 5% overlap
        if overlap < 0.05:
            continue
        
        # Boost score if citation addresses gap
        # (Simple version: check if citation contains terms missing from doc)
        citation['adjusted_score'] = citation.get('score', 0) * (1 + overlap)
        
        filtered.append(citation)
    
    # Sort by adjusted score
    filtered.sort(key=lambda x: x.get('adjusted_score', 0), reverse=True)
    
    # Return top 5-7
    return filtered[:7]
```

3. Use filtered citations:

```python
# After retrieving 15
raw_citations = self.rag_service.retrieve(expanded_query, top_k=15)

# Filter for quality
quality_citations = filter_quality_citations(raw_citations, normalized_text)

# Use these instead of raw_citations
citations = quality_citations
```

**Expected Result:**
- More relevant NDIS standards in results
- Better coverage of different compliance areas
- Fewer generic/useless citations

**Time:** 1 hour

---

### Task 1.3: Remove Template Penalty from Scoring Logic (30 min)

**Problem:** Template detection runs in two places (confusing)

**Solution:** Since we're now rejecting templates in pre-validation, remove the OLD template logic

**Files to Edit:**
- `document_analysis_service.py`

**What to Do:**

1. Find `_derive_status()` function
2. Look for template detection code (around line 742 based on your docs)
3. **COMMENT OUT or DELETE** the template penalty logic

```python
# In _derive_status() function

# OLD CODE (find and delete/comment out):
# if template_detected:
#     structure_score *= 0.3  # 70% penalty
#     ...

# REPLACE WITH:
# Template validation now handled in pre-validation gate
# No need to check here anymore
```

4. Find `_calibrate_status()` function
5. **COMMENT OUT or DELETE** template downgrade logic

```python
# In _calibrate_status() function

# OLD CODE (find and delete/comment out):
# if template_detected:
#     status = 'HIGH_RISK_GAP'
#     confidence = min(confidence, 52)
#     ...

# REPLACE WITH:
# Template validation now handled in pre-validation gate
```

**Expected Result:**
- Cleaner code (one place for validation)
- Consistent behavior
- No duplicate logic

**Time:** 30 minutes

---

### Task 1.4: Test Your Changes (2 hours)

**What to Test:**

Create test documents:

1. **Blank template PDF:**
   - Create a Word doc with [NAME], [DATE], _____ fields
   - Save as PDF
   - Upload → Should get 15% confidence with rejection message

2. **Marketing brochure:**
   - Copy text from any NDIS provider website
   - Add "Call us now!" "Visit our website"
   - Save as PDF
   - Upload → Should be rejected

3. **Good policy document:**
   - Use a real NDIS-compliant policy
   - Upload → Should score 60-80%

4. **Scanned PDF:**
   - Take a photo of printed text
   - Save as PDF (no OCR)
   - Upload → Should be rejected with "image PDF" message

**Test Results Log:**

```
Document Type          | Expected      | Actual        | Pass/Fail
-----------------------|---------------|---------------|----------
Blank template         | 15% rejected  | ???           | ???
Marketing brochure     | 18% rejected  | ???           | ???
Good policy            | 60-80%        | ???           | ???
Scanned image PDF      | 14% rejected  | ???           | ???
Partial template       | 35-45%        | ???           | ???
```

**Time:** 2 hours

---

### Week 1 Summary

**Total Time:** 6-8 hours
**Cost:** $0
**Hardware:** CPU only

**Expected Improvements:**
- ✅ Blank templates properly rejected (15% instead of 25%)
- ✅ Irrelevant documents filtered out
- ✅ More comprehensive NDIS citations (5-7 instead of 3)
- ✅ Cleaner, single-path validation logic

---

## Week 2: Core Improvements

### 🎯 Goal: Upgrade embedding model and improve query construction

**Estimated Time:** 8-12 hours
**Hardware:** CPU is fine (one-time re-indexing will take 20-40 minutes)
**Cost:** $0

---

### Task 2.1: Download Better Embedding Model (30 min)

**Current:** `all-MiniLM-L6-v2` (384 dimensions, general-purpose)
**Upgrade To:** `BAAI/bge-large-en-v1.5` (1024 dimensions, retrieval-optimized)

**Why This Model:**
- ✅ Free, open-source
- ✅ Trained specifically for retrieval (not just general text)
- ✅ Better at legal/compliance terminology
- ✅ Works on CPU (no GPU needed)
- ✅ 2-3x better accuracy for your use case

**Files to Edit:**
- `rag_query_service.py`

**What to Do:**

1. Install the model (one-time download):

```bash
pip install sentence-transformers
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-large-en-v1.5')"
```

This will download the model (~1.3 GB) to your cache. Takes 5-10 minutes depending on internet speed.

2. Update `rag_query_service.py`:

```python
# Find where you initialize the model
# OLD CODE:
# self.model = SentenceTransformer('all-MiniLM-L6-v2')

# REPLACE WITH:
self.model = SentenceTransformer('BAAI/bge-large-en-v1.5')
self.embedding_dimension = 1024  # Update from 384
```

3. **IMPORTANT:** Add BGE-specific query prefix:

```python
# In rag_query_service.py - where you encode queries

def encode_query(self, query_text):
    """
    Encode query with BGE instruction prefix for better retrieval
    """
    # BGE models work better with this instruction prefix for queries
    instruction = "Represent this sentence for searching relevant passages: "
    
    query_with_instruction = instruction + query_text
    
    return self.model.encode(
        query_with_instruction, 
        convert_to_tensor=False,
        normalize_embeddings=True  # Normalize for cosine similarity
    )

def encode_document(self, doc_text):
    """
    Encode document chunks (no instruction prefix for documents)
    """
    return self.model.encode(
        doc_text,
        convert_to_tensor=False,
        normalize_embeddings=True
    )
```

4. Update any dimension checks:

```python
# Find any hardcoded dimension checks
# OLD: if embedding.shape[0] != 384:
# NEW: if embedding.shape[0] != 1024:
```

**Time:** 30 minutes

---

### Task 2.2: Re-Embed Your NDIS Corpus (Once) (30-40 min)

**What This Means:** You need to convert all NDIS documents to embeddings using the new model.

**This is a ONE-TIME operation.** After this, all searches are instant.

**Files to Edit:**
- `rag_ingestion_service.py`

**What to Do:**

1. Make sure your ingestion service uses the new model:

```python
# In rag_ingestion_service.py

# Update model initialization
self.model = SentenceTransformer('BAAI/bge-large-en-v1.5')
```

2. Run re-ingestion script:

```bash
# This will re-embed all NDIS documents with the new model
python -m scripts.ingest_rag_corpus --force-reindex

# OR if you have a different command:
python ingest_ndis_corpus.py --rebuild
```

**What Happens:**
- Script reads all NDIS Practice Standards documents
- Chunks them (1200 chars per chunk with 180 overlap)
- Generates new embeddings using BGE model
- Saves to disk (.npy cache file)
- **Takes 20-40 minutes** depending on corpus size

**⚠️ Important:** Keep old embeddings as backup

```bash
# Before re-indexing, backup old embeddings
cp embeddings.npy embeddings_old_minilm.npy.backup
```

**Monitor Progress:**

Your script should show:
```
Processing NDIS Practice Standards...
Chunk 1/350: Section 1.1 - Rights and Respect [✓]
Chunk 2/350: Section 1.2 - Privacy and Dignity [✓]
...
Saving embeddings to disk...
Done! 350 chunks embedded in 28 minutes.
```

**Verify Success:**

```python
# Quick test script
import numpy as np

# Load new embeddings
embeddings = np.load('embeddings.npy')

print(f"Embedding shape: {embeddings.shape}")
# Should show: (num_chunks, 1024) not (num_chunks, 384)

print(f"Number of chunks: {embeddings.shape[0]}")
# Should show: ~300-500 chunks depending on your corpus
```

**Time:** 30-40 minutes (mostly waiting)

---

### Task 2.3: Improve Query Construction (3-4 hours)

**Problem:** Current query is keyword spam with no structure

**Solution:** Build gap-focused, structured queries

**Files to Edit:**
- `document_analysis_service.py`

**What to Do:**

1. Add helper functions for topic identification:

```python
def _identify_present_topics(self, document_text):
    """
    Identify which NDIS topics ARE in the document
    """
    topic_keywords = {
        'Participant Rights': ['rights', 'dignity', 'respect', 'choice', 'control'],
        'Consent': ['consent', 'informed consent', 'permission', 'authorization'],
        'Safeguarding': ['safeguard', 'protection', 'abuse', 'neglect', 'exploitation'],
        'Incident Management': ['incident', 'reportable', 'notification'],
        'Complaints': ['complaint', 'grievance', 'feedback', 'resolution'],
        'Risk Management': ['risk', 'hazard', 'mitigation', 'assessment'],
        'Governance': ['governance', 'oversight', 'accountability'],
        'Privacy': ['privacy', 'confidential', 'personal information'],
        'Service Delivery': ['service', 'support', 'delivery'],
        'Workforce': ['staff', 'training', 'qualification', 'screening'],
    }
    
    doc_lower = document_text.lower()
    present = []
    
    for topic, keywords in topic_keywords.items():
        # If 2+ keywords match, topic is present
        matches = sum(1 for kw in keywords if kw in doc_lower)
        if matches >= 2:
            present.append(topic)
    
    return present


def _identify_missing_topics(self, document_text):
    """
    Identify CRITICAL topics that are MISSING
    """
    critical_topics = {
        'participant consent procedures': ['consent', 'informed consent', 'permission'],
        'safeguarding procedures': ['safeguard', 'abuse prevention', 'protection'],
        'incident reporting': ['incident', 'reportable', 'notification'],
        'complaints handling': ['complaint', 'grievance', 'resolution'],
        'risk assessment': ['risk assessment', 'risk management'],
        'privacy procedures': ['privacy', 'confidential', 'personal information'],
        'restrictive practice': ['restrictive practice', 'restraint'],
        'staff training': ['training', 'competency', 'qualification'],
        'governance structure': ['governance', 'oversight', 'accountability'],
    }
    
    doc_lower = document_text.lower()
    missing = []
    
    for topic, keywords in critical_topics.items():
        # If NONE of the keywords appear, topic is missing
        found = any(kw in doc_lower for kw in keywords)
        if not found:
            missing.append(topic)
    
    return missing
```

2. Replace your `_build_rag_query()` function:

```python
def _build_rag_query(self, document_text, assessment_question, matched_requirement=None):
    """
    Build a structured, gap-focused RAG query
    
    Instead of keyword spam, build natural language query focusing on gaps
    """
    
    # Identify what's present and missing
    present_topics = self._identify_present_topics(document_text)
    missing_topics = self._identify_missing_topics(document_text)
    
    # Classify document type
    doc_lower = document_text.lower()
    if 'policy' in doc_lower[:500]:
        doc_type = 'policy'
    elif 'procedure' in doc_lower[:500]:
        doc_type = 'procedure'
    else:
        doc_type = 'document'
    
    # Build query parts
    query_parts = []
    
    # Part 1: Base context
    query_parts.append(f"NDIS compliance requirements for {doc_type} documents")
    
    # Part 2: What document covers (for relevance)
    if present_topics:
        topics_str = ", ".join(present_topics[:3])  # Top 3 only
        query_parts.append(f"addressing {topics_str}")
    
    # Part 3: GAPS - what's missing (most important!)
    if missing_topics:
        # Focus on top 5 gaps only
        missing_str = ", ".join(missing_topics[:5])
        query_parts.append(f"Requirements for {missing_str}")
    
    # Part 4: Specific requirement context (if available)
    if matched_requirement:
        req_name = matched_requirement.get('name', '')
        if req_name:
            query_parts.append(f"Standards for {req_name}")
    
    # Join into natural language query
    structured_query = ". ".join(query_parts) + "."
    
    return structured_query
```

**Example Outputs:**

**Before (current):**
```
"Assess this document participant rights privacy dignity consent governance 
operational management risk management NDIS-CM-1 Complaints Management Complaints"
```

**After (improved):**
```
"NDIS compliance requirements for policy documents addressing Participant Rights, 
Governance, Privacy. Requirements for participant consent procedures, safeguarding 
procedures, incident reporting, complaints handling, risk assessment."
```

**Why This Works Better:**
- Natural language → embeddings understand it better
- Gap-focused → retrieves standards for what's MISSING
- Structured → clear signal vs noise
- Concise → no keyword spam

**Time:** 3-4 hours (includes testing)

---

### Task 2.4: Test Improvements (2 hours)

**Test Cases:**

1. **Upload same documents from Week 1:**
   - Compare citation quality before/after
   - Are citations more relevant?
   - Do they address actual gaps?

2. **New test - Consent Policy:**
   - Create policy with consent sections
   - Upload
   - Check if citations match consent requirements
   - Before: May get generic governance citations
   - After: Should get specific consent standards

3. **New test - Incomplete Policy:**
   - Create policy missing incident reporting
   - Upload
   - Check if citations include incident management standards
   - Before: May miss this gap
   - After: Should retrieve incident standards

**Log Results:**

```
Test Case                   | Citations Before | Citations After | Improvement
----------------------------|------------------|-----------------|-------------
Consent policy              | Generic (3)      | ???             | ???
Policy missing incidents    | Missed gap       | ???             | ???
Blank template              | 3 irrelevant     | ???             | ???
```

**Time:** 2 hours

---

### Week 2 Summary

**Total Time:** 8-12 hours
**Cost:** $0
**Hardware:** CPU only

**Expected Improvements:**
- ✅ Citation relevance: 65% → 85%+
- ✅ Better gap identification
- ✅ More specific, actionable standards retrieved
- ✅ Fewer false positives in scoring

---

## Week 3: Polish & Testing

### 🎯 Goal: Add depth scoring and comprehensive testing

**Estimated Time:** 6-8 hours
**Cost:** $0

---

### Task 3.1: Add Coverage Depth Weighting (3 hours)

**Problem:** Current coverage treats "mentioned once" same as "2-page section"

**Solution:** Weight by depth, not just presence

**Files to Edit:**
- `document_analysis_service.py`

**What to Do:**

1. Replace coverage calculation in scoring logic:

```python
def calculate_coverage_with_depth(self, document_text, required_terms):
    """
    Calculate coverage considering both breadth and depth
    
    Returns score out of 25 points
    """
    import re
    
    term_scores = {}
    doc_lower = document_text.lower()
    
    for term in required_terms:
        # Count occurrences
        count = doc_lower.count(term.lower())
        
        # Check procedural context (action words nearby)
        has_procedure = self._check_procedural_context(document_text, term)
        
        # Assign depth score
        if count == 0:
            depth = 0.0
        elif count == 1 and not has_procedure:
            depth = 0.3  # Just mentioned
        elif count <= 2 and has_procedure:
            depth = 0.6  # Some context
        elif count <= 4 and has_procedure:
            depth = 0.8  # Good coverage
        elif count > 4 and has_procedure:
            depth = 1.0  # Comprehensive
        else:
            depth = 0.5  # Multiple mentions but no procedure
        
        term_scores[term] = depth
    
    # Calculate breadth (how many terms covered at all)
    covered_count = sum(1 for score in term_scores.values() if score > 0)
    breadth_ratio = covered_count / max(len(required_terms), 1)
    
    # Calculate average depth of covered terms
    if covered_count > 0:
        avg_depth = sum(term_scores.values()) / len(required_terms)
    else:
        avg_depth = 0
    
    # Combined score: 60% breadth, 40% depth
    coverage_score = (
        (breadth_ratio ** 0.6) * 0.6 +  # Breadth with diminishing returns
        avg_depth * 0.4                   # Depth component
    ) * 25
    
    return {
        'score': coverage_score,
        'breadth_ratio': breadth_ratio,
        'avg_depth': avg_depth,
        'term_scores': term_scores
    }


def _check_procedural_context(self, text, term):
    """
    Check if term appears near action/procedural words
    """
    import re
    
    action_words = [
        'must', 'shall', 'will', 'ensure', 'required',
        'procedure', 'process', 'steps', 'responsible',
        'documented', 'recorded', 'maintained'
    ]
    
    # Find term occurrences
    pattern = re.compile(rf'\b{re.escape(term)}\b', re.IGNORECASE)
    
    for match in pattern.finditer(text):
        # Get 60 chars before and after
        start = max(0, match.start() - 60)
        end = min(len(text), match.end() + 60)
        context = text[start:end].lower()
        
        # Check if action words nearby
        if any(word in context for word in action_words):
            return True
    
    return False
```

2. Use it in your scoring:

```python
# Replace your current coverage calculation
# OLD: coverage_score = (coverage_ratio ** 0.6) * 25

# NEW:
coverage_result = self.calculate_coverage_with_depth(
    document_text=normalized_text,
    required_terms=ndis_required_terms
)

coverage_score = coverage_result['score']
breadth_ratio = coverage_result['breadth_ratio']
avg_depth = coverage_result['avg_depth']
```

**Expected Result:**
- Documents with superficial mentions score lower
- Documents with procedural depth score higher
- More accurate coverage assessment

**Time:** 3 hours

---

### Task 3.2: Comprehensive Testing Suite (3 hours)

Create diverse test cases covering all scenarios:

**Test Document Set:**

1. **Perfect Policy (Target: 75-85%)**
   ```
   - 5+ pages
   - All NDIS topics covered
   - Procedures well-defined
   - Action language throughout
   ```

2. **Good but Short (Target: 60-70%)**
   ```
   - 2 pages
   - Focused on 2-3 NDIS areas
   - Clear procedures
   - Some gaps
   ```

3. **Template with Instructions (Target: 35-45%)**
   ```
   - Some filled sections
   - 4-5 blank placeholders
   - Partial procedures
   ```

4. **Blank Template (Target: 15% rejection)**
   ```
   - All placeholders
   - No content
   - Just form fields
   ```

5. **Marketing Brochure (Target: rejection)**
   ```
   - NDIS keywords present
   - But no policies
   - Call-to-action language
   ```

6. **Scanned Image PDF (Target: rejection)**
   ```
   - Image of text
   - No extractable text
   - Poor OCR
   ```

7. **Generic Procedure (Target: 40-55%)**
   ```
   - Generic HR/operations doc
   - Minimal NDIS-specific content
   - No participant focus
   ```

**Create Test Report:**

```markdown
# Test Results Report - Week 3

## Test Environment
- Date: [DATE]
- Model: BAAI/bge-large-en-v1.5
- Validation Gates: Enabled
- Citation Filter: Enabled

## Results

| Document | Expected | Actual | Pass | Notes |
|----------|----------|--------|------|-------|
| Perfect Policy | 75-85% | ??% | ??? | |
| Good Short | 60-70% | ??% | ??? | |
| Partial Template | 35-45% | ??% | ??? | |
| Blank Template | 15% reject | ??% | ??? | |
| Marketing | reject | ??% | ??? | |
| Scanned PDF | reject | ??% | ??? | |
| Generic Doc | 40-55% | ??% | ??? | |

## Citation Quality

| Document | Citations | Relevant | Notes |
|----------|-----------|----------|-------|
| Perfect Policy | ?? | ??/7 | |
| Good Short | ?? | ??/7 | |

## Issues Found

1. [Issue 1 description]
2. [Issue 2 description]

## Overall Assessment

- Rejection Rate: ??% (target: 30-40% for bad docs)
- False Positives: ?? (target: <5%)
- False Negatives: ?? (target: <10%)
- Citation Relevance: ??% (target: >80%)
```

**Time:** 3 hours

---

### Task 3.3: Performance Optimization (2 hours)

Check if everything is still fast:

```python
# Add timing to your analysis
import time

def analyze_document(self, ...):
    timings = {}
    
    start = time.time()
    # Text extraction
    text = self.extract_text(file)
    timings['extraction'] = time.time() - start
    
    start = time.time()
    # Validation
    validation = validate_document_before_scoring(text, file_path)
    timings['validation'] = time.time() - start
    
    start = time.time()
    # RAG retrieval
    citations = self.rag_service.retrieve(query, top_k=15)
    timings['rag'] = time.time() - start
    
    start = time.time()
    # Scoring
    score = self.calculate_score(...)
    timings['scoring'] = time.time() - start
    
    print(f"Performance Breakdown:")
    print(f"  Extraction: {timings['extraction']:.2f}s")
    print(f"  Validation: {timings['validation']:.2f}s")
    print(f"  RAG: {timings['rag']:.2f}s")
    print(f"  Scoring: {timings['scoring']:.2f}s")
    print(f"  TOTAL: {sum(timings.values()):.2f}s")
```

**Target Performance:**
- Text extraction: <0.2s
- Validation: <0.05s
- RAG retrieval: <0.2s (may be slower with BGE, but still acceptable)
- Scoring: <0.01s
- **Total: <0.5s** (excluding LLM summary)

If RAG is too slow (>0.5s), consider:
- Using FAISS for faster similarity search
- Reducing corpus size (only essential NDIS sections)
- Batch processing for multiple documents

**Time:** 2 hours

---

### Week 3 Summary

**Total Time:** 6-8 hours
**Cost:** $0

**Deliverables:**
- ✅ Depth-weighted coverage scoring
- ✅ Comprehensive test suite with 7+ scenarios
- ✅ Performance benchmarks
- ✅ Test report documenting improvements

---

## Complete Code Changes Summary

### Files Modified

1. **`document_analysis_service.py`** (main changes)
   - Added `validate_document_before_scoring()` - 100 lines
   - Modified `_build_rag_query()` - 50 lines
   - Added `_identify_present_topics()` - 30 lines
   - Added `_identify_missing_topics()` - 40 lines
   - Added `calculate_coverage_with_depth()` - 60 lines
   - Added `filter_quality_citations()` - 50 lines
   - Modified RAG retrieval call - 5 lines
   - **Total new/modified: ~335 lines**

2. **`rag_query_service.py`** (model upgrade)
   - Changed model name - 1 line
   - Added `encode_query()` with instruction - 10 lines
   - Added `encode_document()` - 10 lines
   - Updated dimension constant - 1 line
   - **Total modified: ~25 lines**

3. **`rag_ingestion_service.py`** (corpus re-embedding)
   - Changed model name - 1 line
   - **Total modified: 1 line** (then run re-index script)

### Total Code Changes

- Lines added/modified: ~360
- New functions: 6
- Modified functions: 3
- Files changed: 3

**This is manageable!** Not a complete rewrite.

---

## Testing & Validation

### Validation Checklist

After all changes, verify:

- [ ] Blank templates score 15-20% and show rejection message
- [ ] Marketing docs are rejected with appropriate message
- [ ] Scanned PDFs are rejected or capped at 38%
- [ ] Good policies score 60-80%
- [ ] Citations are relevant to document gaps
- [ ] 5-7 citations returned (not just 3)
- [ ] Performance is <0.5s per document
- [ ] No errors in logs
- [ ] UI displays results correctly

### Regression Testing

Test that old functionality still works:

- [ ] PDF upload works
- [ ] DOCX upload works
- [ ] Score breakdown displays
- [ ] Warnings show correctly
- [ ] Download button works
- [ ] Multiple uploads work

---

## Future Roadmap (When You Have User Data)

### Phase 4: Optional Improvements (3-6 months out)

These require user data and are NOT needed now:

1. **Fine-Tuning Embedding Model** (Optional, later)
   - Requires: 1,000+ labeled document pairs
   - Cost: ~$500-1,000
   - Benefit: +5-10% accuracy improvement
   - **Do this only after 6+ months of usage**

2. **Custom Scoring Model** (Optional, later)
   - Requires: 500+ scored documents with expert labels
   - Cost: $2,000-5,000 for labeling
   - Benefit: More accurate confidence scores
   - **Do this only if your rubric proves insufficient**

3. **Industry-Specific Variants** (Optional, later)
   - Train separate models for different NDIS service types
   - Requires: Segmented corpus and training data
   - **Do this only when you have 10,000+ documents**

### What to Collect Now (For Future Use)

While users interact with your system, log:

```python
# In your database, store:
{
    'document_id': '...',
    'timestamp': '...',
    'score': 67,
    'confidence': 72,
    'user_feedback': {
        'thumbs_up_down': 'up',  # If they rate the result
        'manual_override': 75,    # If they disagree with score
        'comments': 'Too harsh on templates'
    },
    'citations_used': ['NDIS-7.2', 'NDIS-8.D.4'],
    'document_type': 'policy',
    'document_length': 3421
}
```

After 6-12 months, you'll have data to:
- Train custom models
- Tune scoring thresholds
- Identify systematic errors
- Build provider-specific variants

**But DON'T wait for this data to launch!** Your current approach is solid.

---

## Hardware Requirements Summary

### Current Setup (Sufficient)

**Minimum:**
- CPU: Any modern processor (Intel i5/Ryzen 5 or better)
- RAM: 8 GB (16 GB recommended)
- Disk: 20 GB free space
- GPU: NOT required

**What Uses Resources:**

| Operation | CPU | RAM | GPU | Time |
|-----------|-----|-----|-----|------|
| Text extraction | Low | Low | No | <0.2s |
| Validation checks | Low | Low | No | <0.05s |
| RAG query encoding | Medium | Low | No | <0.1s |
| Similarity search | Medium | Medium | No | <0.1s |
| Scoring | Low | Low | No | <0.01s |

**One-Time Operations:**

| Operation | CPU | RAM | GPU | Time |
|-----------|-----|-----|-----|------|
| Download BGE model | Low | Low | No | 5-10 min |
| Re-embed corpus (350 chunks) | High | Medium | No | 20-40 min |

### When You'd Need More Hardware

You do NOT need upgraded hardware unless:

1. **>10,000 simultaneous users** → Need server scaling
2. **>1 million documents in corpus** → Need FAISS GPU acceleration
3. **Real-time streaming analysis** → Need faster inference
4. **Custom model training** → Need GPU (but you're not doing this)

For your current scale (10-1,000 users), **CPU-only is perfect.**

---

## Cost Breakdown

### Total Costs (All 3 Weeks)

| Item | Cost |
|------|------|
| Embedding model (BGE) | $0 (open-source) |
| Development time | Your time only |
| Hardware upgrades | $0 (use existing) |
| Cloud costs | $0 (self-hosted) |
| Training data | $0 (using NDIS corpus) |
| Model training | $0 (not training) |
| **TOTAL** | **$0** |

### Ongoing Costs

| Item | Monthly Cost |
|------|--------------|
| Hosting (if self-hosted) | $0 |
| Hosting (if cloud) | ~$20-50/month |
| API calls | $0 (local embeddings) |
| Model updates | $0 (community updates) |
| **TOTAL** | **$0-50/month** |

---

## Success Metrics

### How to Know It's Working

**Week 1 Success:**
- Blank templates: <20% confidence
- Irrelevant docs: Rejected
- False positive rate: <10%

**Week 2 Success:**
- Citation relevance: >80%
- Gap detection: >70% of missing topics identified
- User feedback: Positive on citation quality

**Week 3 Success:**
- Overall accuracy: >75% for all document types
- Performance: <0.5s per document
- Ready for production launch

---

## Troubleshooting

### Common Issues

**Issue: BGE model too slow**
- Solution: Use `all-mpnet-base-v2` instead (768 dims, faster)
- Trade-off: Slightly lower accuracy

**Issue: Re-embedding takes too long**
- Solution: Process corpus in batches
- Or: Reduce corpus to only essential NDIS sections

**Issue: Citations still not relevant**
- Solution: Check query construction logic
- Debug: Print actual queries being sent
- Adjust: Minimum score threshold (try 0.70 instead of 0.65)

**Issue: False positives still happening**
- Solution: Adjust validation thresholds
- Make template detection stricter
- Lower domain anchor requirements

---

## Final Checklist

Before considering RAG "production-ready":

- [ ] All Week 1 tasks completed and tested
- [ ] All Week 2 tasks completed and tested
- [ ] All Week 3 tasks completed and tested
- [ ] Test suite runs with >75% success rate
- [ ] Performance is <0.5s per document
- [ ] No critical errors in logs
- [ ] User acceptance testing passed
- [ ] Documentation updated
- [ ] Backup/rollback plan in place

---

## Conclusion

**You're on the right track!** Your approach of:
1. Using NDIS corpus only ✅
2. RAG for retrieval (not training) ✅
3. Pre-trained models ✅
4. CPU-only infrastructure ✅

...is **exactly correct** for your use case.

**Total Investment:**
- Time: 20-30 hours over 3 weeks
- Cost: $0
- Hardware: Current laptop/server is fine

**Expected Results:**
- Accuracy: 65% → 85%+
- False positives: 30% → <10%
- User satisfaction: Significant improvement
- Production-ready system

**When to Consider Advanced Approaches:**
- Only after 6-12 months of usage
- Only when you have 1,000+ user documents
- Only if basic RAG proves insufficient

---

**Next Step:** Start with Week 1 tasks. They're the highest impact and easiest to implement.

Good luck! 🚀
