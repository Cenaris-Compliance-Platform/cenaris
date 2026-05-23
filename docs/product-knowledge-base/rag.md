# RAG and Evidence Retrieval

## What RAG Means Here
RAG stands for retrieval-augmented generation. In Cenaris, it means the AI Review flow does not rely on the model alone. It also pulls supporting evidence from the NDIS corpus and from the uploaded document itself.

## How It Works
1. The uploaded document is converted into text.
2. The question and document text are used to build a retrieval query.
3. The app searches the local NDIS corpus for related passages.
4. The returned citations are attached to the analysis response.
5. The scoring layer uses those citations as a signal of support.

## Why RAG Is Important
- It reduces unsupported answers.
- It gives the reviewer visible evidence.
- It helps the system stay closer to the NDIS domain rather than general business language.

## Current Implementation Notes
- Retrieval can run in lexical mode when semantic embeddings are not ready.
- The analysis flow records the retrieval mode so the UI can warn the user.
- If no citations are found, confidence is reduced.
- If retrieval is only lexical, the result is treated more cautiously.

## Evidence Sources Used in the Product
- Uploaded repository document text.
- Requirement matching terms.
- NDIS corpus citations.
- Diagnostic snippet extraction from the uploaded file.

## Limitations Today
- RAG still depends on how well the PDF or DOC file was extracted.
- Keyword-driven retrieval can miss a better semantic match.
- If the source document is poor quality, the citations will also be weaker.

## Where This Is Used
- AI Review document scoring.
- Evidence explanations shown to the reviewer.
- Requirement mapping support.

## Improvement Direction
The next improvement is to make each requirement row show a direct evidence span and a citation reference so the reasoning is auditable from the UI.
