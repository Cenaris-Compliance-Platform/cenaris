# 🚀 Cenaris RAG Improvement Guide (CLEAR VERSION)
## Understanding What We're Actually Changing

---

## 🎯 CRITICAL CLARIFICATION FIRST

### Your System Uses TWO Different Models

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  MODEL #1: EMBEDDING MODEL (For Search/RAG)                │
│  ═══════════════════════════════════════════════════════   │
│                                                             │
│  Current:  all-MiniLM-L6-v2                                 │
│  Location: Runs LOCAL on your server                       │
│  Cost:     $0 (free, open-source)                           │
│  Purpose:  Converts text → numbers for searching           │
│                                                             │
│  ✅ THIS is what we're upgrading                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  MODEL #2: LLM (For Text Generation)                       │
│  ═══════════════════════════════════════════════════════   │
│                                                             │
│  Current:  GPT-4o-mini                                      │
│  Location: OpenRouter API (cloud)                          │
│  Cost:     ~$0.15 per 1M tokens                             │
│  Purpose:  Generates readable summaries/explanations       │
│                                                             │
│  ❌ We are NOT touching this (already perfect)              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 What Each Model Does (Simple Explanation)

### Model #1: Embedding Model = "The Search Engine"

**What it does:**
```
Input:  "participant consent procedures"
         ↓ (converts to numbers)
Output: [0.23, -0.45, 0.78, 0.12, 0.56, ..., 0.34]
        (384 or 1024 numbers representing the meaning)
```

**Why you need it:**
- To find which NDIS standards match the uploaded document
- Like Google search, but for your NDIS corpus
- Runs on your server (free, no API calls)

**Where it's used:**
```python
# In rag_query_service.py
query = "governance procedures"
query_vector = self.model.encode(query)  # ← Embedding model used here
similar_docs = find_similar(query_vector, ndis_corpus)
```

**Current vs Recommended:**

| Current | Recommended | Why Change? |
|---------|-------------|-------------|
| all-MiniLM-L6-v2 | BAAI/bge-large-en-v1.5 | Better at finding relevant NDIS standards |
| 384 dimensions | 1024 dimensions | More accurate matching |
| General-purpose | Retrieval-optimized | Designed specifically for search |
| Free, local | Free, local | No cost increase |

---

### Model #2: LLM = "The Writer"

**What it does:**
```
Input:  Prompt: "Explain why document scored 67%"
         ↓ (generates human text)
Output: "The document demonstrates governance structures 
         but lacks participant consent procedures..."
```

**Why you need it:**
- To write readable explanations for users
- To generate "Why this score" summaries
- To create analysis text

**Where it's used:**
```python
# In document_analysis_service.py
prompt = f"Explain this score: {score}%, gaps: {gaps}"
summary = openrouter_api.call(prompt)  # ← LLM used here
```

**Keep as-is:**

| Current | Alternative | Why NOT Change? |
|---------|-------------|-----------------|
| GPT-4o-mini | GPT-4 | 10x more expensive, only marginally better |
| $0.15/1M tokens | $3/1M tokens | Not worth the cost |
| Fast (1-2s) | Fast (1-2s) | Already fast enough |

---

## 📊 Your Complete System Architecture

### Current Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. USER UPLOADS DOCUMENT                                   │
│     (Policy PDF/DOCX)                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  2. TEXT EXTRACTION                                         │
│     • pypdf, fitz, pdfplumber                               │
│     • No AI model used                                      │
│     • Just reading the file                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  3. PRE-VALIDATION GATES (NEW!)                             │
│     • Check if blank template                               │
│     • Check if marketing doc                                │
│     • Check if scanned PDF                                  │
│     • No AI model used (just Python rules)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  4. BUILD SEARCH QUERY                                      │
│     • Identify what's in document                           │
│     • Identify what's MISSING                               │
│     • Build structured query                                │
│     • No AI model used (just text analysis)                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  5. RAG SEARCH (EMBEDDING MODEL USED HERE!)                 │
│     ═══════════════════════════════════════════════════     │
│                                                             │
│     🔵 EMBEDDING MODEL: all-MiniLM-L6-v2                    │
│        ↓ THIS is what we're upgrading to BGE               │
│                                                             │
│     • Convert query → vector [0.12, 0.56, ...]              │
│     • Search NDIS corpus (pre-embedded)                     │
│     • Find top 15 similar standards                         │
│     • Filter to top 5-7 quality citations                   │
│                                                             │
│     Runs: LOCAL on your server                             │
│     Cost: $0 (free)                                         │
│     Speed: 0.02-0.05 seconds                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  6. SCORING ENGINE                                          │
│     • Calculate coverage score (0-25 pts)                   │
│     • Calculate depth score (0-20 pts)                      │
│     • Calculate substance score (0-40 pts)                  │
│     • Calculate structure score (0-10 pts)                  │
│     • Calculate evidence score (0-5 pts)                    │
│     • Apply penalties/bonuses                               │
│     • Map to status (Critical/High Risk/OK/Mature)          │
│     • No AI model used (just Python math)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  7. GENERATE SUMMARY (LLM USED HERE!)                       │
│     ═══════════════════════════════════════════════════     │
│                                                             │
│     🟢 LLM: GPT-4o-mini via OpenRouter API                  │
│        ↓ We are NOT changing this (already good)           │
│                                                             │
│     • Build prompt with score + citations + gaps            │
│     • Call API: openrouter.ai/api/v1/chat/completions       │
│     • Receive human-readable summary text                   │
│                                                             │
│     Runs: Cloud API call                                    │
│     Cost: ~$0.15 per 1M tokens                              │
│     Speed: 1-2 seconds                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  8. RETURN RESULTS TO USER                                  │
│     • Status badge (Critical Gap / OK / Mature)             │
│     • Confidence percentage                                 │
│     • Score breakdown (5 dimensions)                        │
│     • 5-7 NDIS citations                                    │
│     • Priority actions to fix                               │
│     • LLM-generated summary                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ What We're Actually Changing

### Changes Overview

| Component | Current | Upgrade To | Why | Cost |
|-----------|---------|------------|-----|------|
| **Embedding Model** | all-MiniLM-L6-v2 | BAAI/bge-large-en-v1.5 | Better RAG retrieval | $0 |
| Pre-validation | None | Add gates | Reject bad docs early | $0 |
| Query construction | Keyword spam | Gap-focused | Better search queries | $0 |
| Citation retrieval | Top 3 | Top 15 → filter to 5-7 | More comprehensive | $0 |
| Coverage scoring | Presence only | Presence + depth | Reward actual procedures | $0 |
| **LLM** | GPT-4o-mini | **NO CHANGE** | Already perfect | $0 |

**Total Cost: $0**
**Total Time: 20-30 hours over 3 weeks**

---

## 📅 Week-by-Week Implementation Plan

### Week 1: Quick Wins (6-8 hours)

**Goal:** Fix biggest issues with code-only changes

#### Task 1.1: Add Pre-Validation Gates (2 hours)

**What:** Reject bad documents BEFORE scoring

**Why:** Blank templates and marketing docs currently score too high

**Changes:**
- Add `validate_document_before_scoring()` function
- Check for: blank templates, marketing docs, scanned PDFs, invalid types
- Return rejection immediately if document is bad

**Files Modified:**
- `document_analysis_service.py` (+100 lines)

**Code to Add:**

```python
def validate_document_before_scoring(text, file_path):
    """
    Validate document before any scoring.
    Reject invalid documents immediately.
    """
    import re
    import os
    
    # Gate 1: Minimum length
    if len(text.strip()) < 100:
        return {
            'valid': False,
            'reason': 'DOCUMENT_TOO_SHORT',
            'confidence': 12,
            'status': 'CRITICAL_GAP',
            'message': 'Document contains less than 100 characters.'
        }
    
    # Gate 2: Blank template detection
    bracket_placeholders = len(re.findall(r'\[[^\]]{0,30}\]', text))
    underscores = len(re.findall(r'_{4,}', text))
    dots = len(re.findall(r'\.{4,}', text))
    total_markers = bracket_placeholders + underscores + dots
    
    text_no_markers = text
    for pattern in [r'\[[^\]]{0,30}\]', r'_{4,}', r'\.{4,}']:
        text_no_markers = re.sub(pattern, '', text_no_markers)
    
    fill_ratio = len(text_no_markers.strip()) / max(len(text), 1)
    word_count = len(re.findall(r'\b\w+\b', text))
    
    # HARD REJECTION for blank templates
    if (total_markers >= 10 and fill_ratio < 0.40) or \
       (total_markers >= 6 and word_count < 300):
        return {
            'valid': False,
            'reason': 'BLANK_TEMPLATE',
            'confidence': 15,
            'status': 'CRITICAL_GAP',
            'message': f'Blank template with {total_markers} unfilled sections.'
        }
    
    # SOFT PENALTY for partial templates
    if total_markers >= 4 and fill_ratio < 0.65:
        return {
            'valid': True,
            'reason': 'PARTIAL_TEMPLATE',
            'confidence_cap': 42,
            'penalty_multiplier': 0.50,
            'message': f'Partially incomplete ({total_markers} unfilled sections).'
        }
    
    # Gate 3: Invalid document type
    text_lower = text.lower()
    invalid_types = {
        'email': ['from:', 'to:', 'subject:', 'dear', 'regards,'],
        'resume': ['curriculum vitae', 'work experience', 'education:'],
        'invoice': ['invoice number', 'total due', 'payment terms'],
        'marketing': ['call us now', 'visit our website', 'book now'],
    }
    
    for doc_type, keywords in invalid_types.items():
        matches = sum(1 for kw in keywords if kw in text_lower)
        if matches >= 2:
            return {
                'valid': False,
                'reason': f'INVALID_TYPE_{doc_type.upper()}',
                'confidence': 18,
                'status': 'CRITICAL_GAP',
                'message': f'Document is a {doc_type}, not a compliance policy.'
            }
    
    # Gate 4: PDF quality check
    if file_path and file_path.endswith('.pdf'):
        try:
            file_size_kb = os.path.getsize(file_path) / 1024
            chars_per_kb = len(text) / max(file_size_kb, 0.1)
            
            if chars_per_kb < 150:  # Image-only PDF
                return {
                    'valid': False,
                    'reason': 'IMAGE_PDF',
                    'confidence': 14,
                    'status': 'CRITICAL_GAP',
                    'message': 'Scanned/image-only PDF. Upload text-based PDF.'
                }
            
            if chars_per_kb < 500:  # Low-quality scan
                return {
                    'valid': True,
                    'reason': 'LOW_QUALITY_SCAN',
                    'confidence_cap': 38,
                    'penalty_multiplier': 0.62,
                    'message': 'Low text extraction quality.'
                }
        except:
            pass
    
    return {'valid': True, 'reason': 'OK'}


# USE IT in analyze_document():
validation = validate_document_before_scoring(normalized_text, file_path)

if not validation['valid']:
    # Return rejection immediately
    return {
        'status': validation['status'],
        'confidence': validation['confidence'],
        'summary': validation['message'],
        'warning_items': [{
            'category': 'VALIDATION',
            'message': validation['message']
        }],
        'score_breakdown': None,
        'citations': []
    }

# Apply penalties if needed
penalty = validation.get('penalty_multiplier', 1.0)
confidence_cap = validation.get('confidence_cap', 100)
```

**Expected Results:**
- Blank templates: 15% (was 25%)
- Marketing docs: Rejected (was 40-50%)
- Scanned PDFs: Rejected or capped at 38%

**Time:** 2 hours

---

#### Task 1.2: Retrieve More Citations (1 hour)

**What:** Change from 3 citations to 15 → filter to 5-7

**Why:** Only 3 citations misses most relevant NDIS standards

**Changes:**
- Increase `top_k` from 3 to 15
- Add citation filtering function
- Return 5-7 high-quality citations

**Files Modified:**
- `document_analysis_service.py` (+50 lines)

**Code to Change:**

```python
# FIND THIS (around line 258):
citations = self.rag_service.retrieve(expanded_query, top_k=3)

# REPLACE WITH:
raw_citations = self.rag_service.retrieve(expanded_query, top_k=15)
citations = filter_quality_citations(raw_citations, normalized_text)


# ADD THIS FUNCTION:
def filter_quality_citations(citations, document_text, min_score=0.65):
    """
    Filter citations for quality and relevance
    """
    import re
    
    filtered = []
    
    for citation in citations:
        # Rule 1: Minimum score
        if citation.get('score', 0) < min_score:
            continue
        
        citation_text = citation.get('text', '').lower()
        
        # Rule 2: Must have action words
        has_action = any(word in citation_text for word in [
            'must', 'shall', 'will', 'ensure', 'required', 
            'responsible', 'documented'
        ])
        if not has_action:
            continue
        
        # Rule 3: Not too short
        if len(citation.get('text', '')) < 80:
            continue
        
        # Rule 4: Terminology overlap
        doc_words = set(re.findall(r'\b\w{5,}\b', document_text.lower()))
        citation_words = set(re.findall(r'\b\w{5,}\b', citation_text))
        
        if len(doc_words) > 0:
            overlap = len(doc_words & citation_words) / len(doc_words | citation_words)
        else:
            overlap = 0
        
        if overlap < 0.05:
            continue
        
        citation['adjusted_score'] = citation.get('score', 0) * (1 + overlap)
        filtered.append(citation)
    
    filtered.sort(key=lambda x: x.get('adjusted_score', 0), reverse=True)
    return filtered[:7]
```

**Expected Results:**
- More NDIS standards covered
- Better topic diversity
- Fewer generic citations

**Time:** 1 hour

---

#### Task 1.3: Clean Up Old Template Logic (30 min)

**What:** Remove duplicate template detection code

**Why:** Pre-validation now handles it; old code is redundant

**Changes:**
- Comment out template logic in `_derive_status()`
- Comment out template logic in `_calibrate_status()`

**Files Modified:**
- `document_analysis_service.py` (-50 lines)

**What to Remove:**

```python
# In _derive_status() - COMMENT OUT OR DELETE:
# if template_detected:
#     structure_score *= 0.3  # 70% penalty

# In _calibrate_status() - COMMENT OUT OR DELETE:
# if template_detected:
#     status = 'HIGH_RISK_GAP'
#     confidence = min(confidence, 52)
```

**Time:** 30 minutes

---

#### Task 1.4: Test Changes (2 hours)

**Test Documents:**

1. Blank template → Should get 15% rejection
2. Marketing brochure → Should be rejected
3. Good policy → Should score 60-80%
4. Scanned PDF → Should be rejected

**Create Test Log:**

```
Document Type          | Expected      | Actual | Pass/Fail
-----------------------|---------------|--------|----------
Blank template         | 15% rejected  | ???    | ???
Marketing brochure     | 18% rejected  | ???    | ???
Good policy            | 60-80%        | ???    | ???
Scanned PDF            | 14% rejected  | ???    | ???
```

**Time:** 2 hours

---

### Week 2: Embedding Model Upgrade (8-12 hours)

**Goal:** Upgrade to better search model, improve query construction

**NO TRAINING INVOLVED - Just swapping tools!**

---

#### Task 2.1: Download BGE Embedding Model (30 min)

**What:** Download better pre-trained model for RAG search

**NOT an LLM! This is for converting text to numbers for search**

**Installation:**

```bash
# Install sentence-transformers (if not already installed)
pip install sentence-transformers

# Download BGE model (one-time, ~1.3 GB)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-large-en-v1.5')"
```

**What happens:**
```
Downloading model files...
model.safetensors (1.3 GB) ████████████ 100%
config.json (700 bytes) ████████████ 100%
tokenizer_config.json (300 bytes) ████████████ 100%

Model downloaded to: /home/user/.cache/torch/sentence_transformers/
```

**Time:** 5-10 minutes (depending on internet speed)

---

#### Task 2.2: Update Code to Use BGE (10 min)

**Files Modified:**
- `rag_query_service.py` (1 line change!)

**Code Change:**

```python
# In rag_query_service.py - FIND THIS:
self.model = SentenceTransformer('all-MiniLM-L6-v2')

# REPLACE WITH:
self.model = SentenceTransformer('BAAI/bge-large-en-v1.5')

# Also update dimension constant:
# OLD: self.embedding_dimension = 384
# NEW: self.embedding_dimension = 1024
```

**IMPORTANT - Add BGE instruction prefix:**

```python
# ADD THIS METHOD to rag_query_service.py:

def encode_query(self, query_text):
    """
    Encode query with BGE instruction prefix
    
    BGE models work better with this prefix for queries
    """
    instruction = "Represent this sentence for searching relevant passages: "
    return self.model.encode(
        instruction + query_text,
        convert_to_tensor=False,
        normalize_embeddings=True
    )

def encode_document(self, doc_text):
    """
    Encode document (no instruction prefix)
    """
    return self.model.encode(
        doc_text,
        convert_to_tensor=False,
        normalize_embeddings=True
    )


# UPDATE YOUR EXISTING ENCODING CALLS:
# OLD: embeddings = self.model.encode(text)
# NEW: embeddings = self.encode_query(text)  # for queries
#      embeddings = self.encode_document(text)  # for documents
```

**Time:** 10 minutes

---

#### Task 2.3: Re-Embed NDIS Corpus (30-40 min ONE-TIME)

**What:** Convert all NDIS documents to vectors using new model

**This is NOT training! Just converting text to numbers for search**

**Backup First:**

```bash
# Backup old embeddings
cp embeddings.npy embeddings_old_minilm.backup.npy
```

**Run Re-Ingestion:**

```bash
# Run your existing ingestion script
python ingest_ndis_corpus.py --force-rebuild

# OR
python -m scripts.rag_ingestion --rebuild
```

**What You'll See:**

```
Loading NDIS Practice Standards...
✓ Section 1.1 - Rights and Respect
✓ Section 1.2 - Privacy and Dignity
✓ Section 2.1 - Governance
...
✓ Section 8.4 - High Intensity Supports

Chunking documents (1200 chars, 180 overlap)...
350 chunks created

Generating embeddings with BAAI/bge-large-en-v1.5...
Chunk 1/350 [0.12, 0.56, ..., 0.34] (1024 dims) ✓
Chunk 2/350 [0.15, -0.23, ..., 0.67] (1024 dims) ✓
...
Chunk 350/350 [-0.34, 0.89, ..., 0.12] (1024 dims) ✓

Saving to embeddings.npy...
Done! Total time: 28 minutes
```

**Verify Success:**

```python
# Quick test
import numpy as np
embeddings = np.load('embeddings.npy')
print(f"Shape: {embeddings.shape}")
# Should show: (350, 1024) not (350, 384)
```

**Time:** 30-40 minutes (automated, just wait)

**⚠️ This is a ONE-TIME operation!** After this, all searches use the new embeddings instantly.

---

#### Task 2.4: Improve Query Construction (3-4 hours)

**What:** Build better search queries focused on gaps

**Current Problem:**
```
Query: "participant rights privacy dignity consent governance risk NDIS-CM-1"
       ↑ Keyword spam, no structure
```

**New Approach:**
```
Query: "NDIS compliance requirements for policy documents addressing 
        Participant Rights, Governance. Requirements for participant 
        consent procedures, safeguarding, incident reporting."
       ↑ Natural language, gap-focused
```

**Files Modified:**
- `document_analysis_service.py` (+150 lines)

**Code to Add:**

```python
def _identify_present_topics(self, document_text):
    """
    Identify NDIS topics that ARE in document
    """
    topic_keywords = {
        'Participant Rights': ['rights', 'dignity', 'respect', 'choice'],
        'Consent': ['consent', 'informed consent', 'permission'],
        'Safeguarding': ['safeguard', 'protection', 'abuse', 'neglect'],
        'Incident Management': ['incident', 'reportable', 'notification'],
        'Complaints': ['complaint', 'grievance', 'resolution'],
        'Risk Management': ['risk', 'hazard', 'mitigation'],
        'Governance': ['governance', 'oversight', 'accountability'],
        'Privacy': ['privacy', 'confidential', 'personal information'],
        'Workforce': ['staff', 'training', 'qualification'],
    }
    
    doc_lower = document_text.lower()
    present = []
    
    for topic, keywords in topic_keywords.items():
        matches = sum(1 for kw in keywords if kw in doc_lower)
        if matches >= 2:  # 2+ keywords = topic present
            present.append(topic)
    
    return present


def _identify_missing_topics(self, document_text):
    """
    Identify CRITICAL topics that are MISSING
    """
    critical_topics = {
        'participant consent procedures': ['consent', 'informed consent'],
        'safeguarding procedures': ['safeguard', 'abuse prevention'],
        'incident reporting': ['incident', 'reportable'],
        'complaints handling': ['complaint', 'grievance'],
        'risk assessment': ['risk assessment', 'risk management'],
        'privacy procedures': ['privacy', 'confidential'],
        'restrictive practice': ['restrictive practice', 'restraint'],
    }
    
    doc_lower = document_text.lower()
    missing = []
    
    for topic, keywords in critical_topics.items():
        found = any(kw in doc_lower for kw in keywords)
        if not found:
            missing.append(topic)
    
    return missing


def _build_rag_query(self, document_text, assessment_question, matched_requirement=None):
    """
    Build structured, gap-focused query
    
    REPLACES your current _build_rag_query function
    """
    present = self._identify_present_topics(document_text)
    missing = self._identify_missing_topics(document_text)
    
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
    query_parts.append(f"NDIS compliance requirements for {doc_type} documents")
    
    if present:
        topics_str = ", ".join(present[:3])
        query_parts.append(f"addressing {topics_str}")
    
    if missing:
        missing_str = ", ".join(missing[:5])
        query_parts.append(f"Requirements for {missing_str}")
    
    if matched_requirement:
        req_name = matched_requirement.get('name', '')
        if req_name:
            query_parts.append(f"Standards for {req_name}")
    
    return ". ".join(query_parts) + "."
```

**Example Output:**

**Before:**
```
"Assess participant rights privacy consent governance NDIS-CM-1 Complaints"
```

**After:**
```
"NDIS compliance requirements for policy documents addressing Participant 
Rights, Governance, Privacy. Requirements for participant consent procedures, 
safeguarding procedures, incident reporting, complaints handling."
```

**Time:** 3-4 hours

---

#### Task 2.5: Test Improvements (2 hours)

**Compare Before/After:**

| Test | Citations Before (MiniLM) | Citations After (BGE) |
|------|---------------------------|----------------------|
| Consent policy | Generic governance (3) | Specific consent standards (5-7) |
| Missing incidents | Missed the gap | Retrieved incident standards |
| Blank template | 3 irrelevant citations | Rejected before retrieval |

**Time:** 2 hours

---

### Week 3: Polish & Final Testing (6-8 hours)

**Goal:** Add depth scoring, comprehensive testing

---

#### Task 3.1: Add Coverage Depth Weighting (3 hours)

**What:** Score based on how THOROUGHLY topics are covered, not just mentioned

**Current Problem:**
- "Consent" mentioned once = 100% credit
- 2-page consent section = same 100% credit

**New Approach:**
- Just mentioned = 30% credit
- With procedure = 60% credit
- Comprehensive = 100% credit

**Files Modified:**
- `document_analysis_service.py` (+80 lines)

**Code to Add:**

```python
def calculate_coverage_with_depth(self, document_text, required_terms):
    """
    Score coverage with depth weighting
    """
    import re
    
    term_scores = {}
    doc_lower = document_text.lower()
    
    for term in required_terms:
        count = doc_lower.count(term.lower())
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
        else:
            depth = 1.0  # Comprehensive
        
        term_scores[term] = depth
    
    # Breadth: how many covered
    covered = sum(1 for s in term_scores.values() if s > 0)
    breadth = covered / max(len(required_terms), 1)
    
    # Depth: average of covered terms
    avg_depth = sum(term_scores.values()) / len(required_terms) if required_terms else 0
    
    # Combined: 60% breadth, 40% depth
    score = ((breadth ** 0.6) * 0.6 + avg_depth * 0.4) * 25
    
    return {
        'score': score,
        'breadth': breadth,
        'depth': avg_depth
    }


def _check_procedural_context(self, text, term):
    """
    Check if term appears near action words
    """
    import re
    
    action_words = ['must', 'shall', 'will', 'ensure', 'procedure', 'process']
    pattern = re.compile(rf'\b{re.escape(term)}\b', re.IGNORECASE)
    
    for match in pattern.finditer(text):
        start = max(0, match.start() - 60)
        end = min(len(text), match.end() + 60)
        context = text[start:end].lower()
        
        if any(word in context for word in action_words):
            return True
    
    return False
```

**Usage:**

```python
# REPLACE your current coverage calculation:
# OLD: coverage_score = (coverage_ratio ** 0.6) * 25

# NEW:
result = self.calculate_coverage_with_depth(normalized_text, ndis_terms)
coverage_score = result['score']
```

**Time:** 3 hours

---

#### Task 3.2: Comprehensive Testing (3 hours)

**Create Test Suite:**

7 test documents covering all scenarios:

1. Perfect policy (target: 75-85%)
2. Good short policy (target: 60-70%)
3. Partial template (target: 35-45%)
4. Blank template (target: 15% rejection)
5. Marketing doc (target: rejection)
6. Scanned PDF (target: rejection)
7. Generic doc (target: 40-55%)

**Test Report Template:**

```markdown
# Week 3 Test Results

## Environment
- Embedding Model: BAAI/bge-large-en-v1.5
- Pre-validation: Enabled
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

| Document | Citations | Relevant |
|----------|-----------|----------|
| Perfect Policy | 7 | 6/7 (86%) |
| Good Short | 5 | 4/5 (80%) |

## Overall
- False Positives: ??% (target <5%)
- False Negatives: ??% (target <10%)
- Citation Relevance: ??% (target >80%)
```

**Time:** 3 hours

---

## 💰 Total Cost Breakdown

### One-Time Costs

| Item | Cost |
|------|------|
| BGE model download | $0 (free, open-source) |
| Re-embed corpus | $0 (local compute) |
| Development time | Your time only |
| **TOTAL ONE-TIME** | **$0** |

### Ongoing Costs

| Item | Monthly |
|------|---------|
| Embedding model (local) | $0 |
| LLM (GPT-4o-mini API) | ~$5-20 (unchanged) |
| Hosting (if cloud) | ~$20-50 |
| **TOTAL MONTHLY** | **$25-70** |

**No cost increase from improvements!**

---

## ⚙️ Hardware Requirements

### Minimum (You Probably Already Have This)

- **CPU:** Any modern processor (i5/Ryzen 5+)
- **RAM:** 8 GB (16 GB recommended)
- **Disk:** 20 GB free
- **GPU:** NOT required

### Performance Benchmarks

| Operation | Time (MiniLM) | Time (BGE) |
|-----------|---------------|------------|
| Text extraction | 0.05-0.2s | 0.05-0.2s (same) |
| Validation | N/A | 0.01-0.05s (new) |
| Query encoding | 0.01s | 0.03s |
| RAG search | 0.02s | 0.05s |
| Scoring | 0.005s | 0.005s (same) |
| LLM summary | 1-2s | 1-2s (same) |
| **TOTAL** | **~1.1-2.3s** | **~1.2-2.4s** |

Slightly slower, but still very fast!

---

## ✅ Success Checklist

After 3 weeks, verify:

- [ ] Blank templates score <20%
- [ ] Marketing docs rejected
- [ ] Good policies score 60-80%
- [ ] Citations are relevant (>80%)
- [ ] 5-7 citations returned per document
- [ ] Performance <0.5s (excluding LLM)
- [ ] No errors in logs
- [ ] User feedback positive

---

## 🚫 Common Mistakes to Avoid

### Mistake #1: Thinking You Need to Train a Model

**Wrong:** "I need to collect 10,000 documents and train a model"
**Right:** "I'm just downloading a better pre-trained model"

### Mistake #2: Confusing Embedding Model with LLM

**Wrong:** "Should I upgrade from GPT-4o-mini to GPT-4?"
**Right:** "I'm upgrading the embedding model (for search), not the LLM (for text generation)"

### Mistake #3: Thinking You Need GPU

**Wrong:** "I need to buy a $2,000 GPU"
**Right:** "Everything runs fine on CPU"

### Mistake #4: Thinking This Costs Money

**Wrong:** "Better models must be expensive"
**Right:** "BGE is free and open-source, just like MiniLM"

---

## 🎯 Quick Summary

### What You're Actually Doing

1. **Week 1:** Code improvements (validation, filtering)
2. **Week 2:** Swap search tool (MiniLM → BGE)
3. **Week 3:** Add depth scoring, test everything

### What You're NOT Doing

- ❌ Training any models
- ❌ Collecting training data
- ❌ Buying expensive hardware
- ❌ Changing your LLM (GPT-4o-mini)
- ❌ Spending money

### Expected Results

- Accuracy: 65% → 85%+
- False positives: 30% → <10%
- Citation quality: Much better
- Cost: $0
- Time: 20-30 hours

---

## 📞 Still Confused?

**Key Takeaway:**
- You have TWO models: one for search (embedding), one for writing (LLM)
- We're only upgrading the SEARCH model
- It's free, local, and doesn't require training
- Your LLM (GPT-4o-mini) stays the same

**Think of it like:**
- Upgrading from Google Chrome to Firefox (just swapping browsers)
- Not building your own browser from scratch (training)

---

**Ready to start?** Begin with Week 1, Task 1.1! 🚀
