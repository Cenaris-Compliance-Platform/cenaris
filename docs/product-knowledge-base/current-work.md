# Current Work: AI Review Scoring and Reasoning

## What We Are Improving Right Now
The main focus is making AI Review more accurate, more explainable, and less likely to hallucinate a high score when the document is weak or irrelevant.

## Problems We Are Fixing
- Non-compliance documents can look too good if they contain generic action words.
- Real compliance documents can be scored too low if text extraction is poor.
- The top-level status and the checklist can contradict each other.
- Users need to understand why a score is high, low, or capped.

## What Has Been Added

### 1. Better Document Extraction
- The service now tries multiple PDF text extraction methods.
- If a PDF is image-only or poorly parsed, the system records low extraction quality.
- Low extraction quality can reduce confidence so the app does not act too sure.

### 2. Requirement-Level Reasoning
- Each matched requirement is evaluated against actual text blocks from the document.
- The app looks for grounded evidence spans rather than only keyword overlap.
- A requirement can only be treated as strong if the text span is actually validated in the extracted document.

### 3. Consistency Guards
- If the checklist still has gaps, the overall result cannot stay unrealistically high.
- Mature results are blocked when mapped requirements still show important gaps.
- Lexical-only retrieval and low extraction quality also reduce confidence.

### 4. Better Explanations in the UI
- The result card now shows blocker reasons.
- Confidence is shown with a split between coverage confidence and evidence confidence.
- The goal is to make the output understandable to a reviewer in a few seconds.

## Why This Helps
- It reduces overconfident scoring.
- It makes weak results easier to challenge.
- It gives reviewers a concrete reason to trust or reject the score.
- It provides a foundation for better future tuning.

## Current Direction
The next step is to make the reasoning even more evidence-backed by linking every positive claim to:
- a document text span,
- a matching requirement,
- and a supporting citation when available.
