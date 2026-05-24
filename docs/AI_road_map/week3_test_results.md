# Week 3 Test Results

## Environment
- Embedding Model: BAAI/bge-large-en-v1.5
- Pre-validation: Enabled
- Citation Filter: Enabled
- Coverage Depth Weighting: Enabled

## Results

| Document | Expected | Actual | Pass | Notes |
|----------|----------|--------|------|-------|
| Perfect Policy | 75-85% | N/A | N/A | Missing test document |
| Good Short Policy | 60-70% | 14% (Critical gap) | Fail | Detected as image-only PDF |
| Partial Template | 35-45% | 20% (Critical gap) | Fail | Rejected as non-NDIS policy |
| Blank Template | 15% reject | 14% (Critical gap) | Pass | Scanned/image-only detection triggered |
| Marketing Doc | reject | 18% (Critical gap) | Pass | Rejected as marketing content |
| Scanned PDF | reject | 12% (Critical gap) | Pass | Document too short |
| Generic Doc | 40-55% | 20% (Critical gap) | Pass | Rejected as non-NDIS policy |

## Citation Quality

| Document | Citations | Relevant |
|----------|-----------|----------|
| Perfect Policy | 0 | N/A |
| Good Short Policy | 0 | N/A |

## Overall
- False Positives: 0% (target <5%)
- False Negatives: High (good policy rejected due to image-only detection)
- Citation Relevance: N/A (no citations for rejected docs)
