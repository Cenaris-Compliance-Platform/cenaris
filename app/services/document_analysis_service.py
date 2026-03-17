from __future__ import annotations

import io
import logging
import os
import re

from flask import current_app

from app import db
from app.models import ComplianceFrameworkVersion, ComplianceRequirement
from app.services.rag_query_service import rag_query_service
from sqlalchemy import or_

logger = logging.getLogger(__name__)


class DocumentAnalysisService:
    """Analyze uploaded evidence documents for the standard user workflow."""

    _STOP_WORDS = {
        'the', 'and', 'for', 'with', 'that', 'this', 'from', 'have', 'your', 'what', 'when', 'where',
        'which', 'into', 'about', 'they', 'them', 'their', 'will', 'would', 'should', 'there', 'here',
        'been', 'also', 'only', 'than', 'then', 'each', 'very', 'more', 'most', 'such', 'some', 'using',
        'does', 'did', 'not', 'are', 'was', 'were', 'is', 'it', 'to', 'of', 'in', 'on', 'by', 'as',
    }

    _SUPPORTED_SUFFIXES = ('.txt', '.pdf', '.docx')

    _TOPIC_RULES = [
        {
            'label': 'Complaints Management',
            'keywords': ('complaint', 'complaints', 'feedback', 'grievance', 'resolve', 'resolution'),
            'question': 'Does this document show a usable complaints and feedback management process, including intake, investigation, resolution, participant communication, and review?',
        },
        {
            'label': 'Consent and Privacy',
            'keywords': ('consent', 'privacy', 'dignity', 'confidential', 'confidentiality', 'information management'),
            'question': 'Does this document evidence consent, privacy, dignity, confidentiality, and participant rights in service delivery?',
        },
        {
            'label': 'Service Agreements',
            'keywords': ('service agreement', 'agreement', 'service terms', 'supports', 'fees', 'service booking'),
            'question': 'Does this document clearly set out service agreements, support responsibilities, participant choice, and review expectations?',
        },
        {
            'label': 'Support Planning',
            'keywords': ('care plan', 'support plan', 'planning', 'goals', 'assessment', 'review', 'participant plan'),
            'question': 'Does this document evidence person-centred support planning, communication, implementation, participant involvement, and review?',
        },
        {
            'label': 'Cultural Inclusion',
            'keywords': ('culture', 'cultural', 'diversity', 'inclusive', 'inclusion', 'cald', 'lgbtiq', 'beliefs', 'values'),
            'question': 'Does this document evidence inclusive practice, cultural safety, privacy, dignity, and participant rights for diverse service users?',
        },
        {
            'label': 'Incident and Risk Management',
            'keywords': ('incident', 'risk', 'governance', 'quality', 'monitoring', 'safeguard'),
            'question': 'Does this document evidence incident management, risk controls, escalation, governance review, and corrective actions?',
        },
    ]

    def extract_text_from_bytes(self, filename: str, raw_bytes: bytes) -> tuple[str, str | None]:
        filename_value = (filename or '').strip().lower()
        if not filename_value:
            return '', 'A file is required.'
        if not raw_bytes:
            return '', 'Uploaded file is empty.'

        try:
            if filename_value.endswith('.txt'):
                return raw_bytes.decode('utf-8', errors='ignore').strip(), None

            if filename_value.endswith('.pdf'):
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(raw_bytes))
                pages = [(page.extract_text() or '').strip() for page in reader.pages]
                return '\n\n'.join([page for page in pages if page]).strip(), None

            if filename_value.endswith('.docx'):
                from docx import Document as DocxDocument

                doc = DocxDocument(io.BytesIO(raw_bytes))
                paragraphs = [(p.text or '').strip() for p in doc.paragraphs]
                return '\n\n'.join([paragraph for paragraph in paragraphs if paragraph]).strip(), None
        except Exception:
            logger.exception('Failed to extract text from uploaded document %s', filename)
            return '', 'Unable to parse file. Use TXT, PDF, or DOCX for document analysis.'

        return '', 'Unsupported file type. Use TXT, PDF, or DOCX.'

    def analyze_document_bytes(self, *, filename: str, raw_bytes: bytes, organization_id: int | None = None) -> dict:
        text, extraction_error = self.extract_text_from_bytes(filename, raw_bytes)
        if extraction_error:
            return {
                'success': False,
                'error': extraction_error,
                'extracted_text': '',
            }

        matched_requirements = self._match_requirements(text=text, filename=filename, organization_id=organization_id)
        if matched_requirements:
            top_requirement = matched_requirements[0]
            focus_area = top_requirement.get('label') or top_requirement.get('requirement_id') or 'Mapped Requirement'
            question = self._build_requirement_question(matched_requirements)
        else:
            focus_area, question = self._infer_focus_area_and_question(filename, text)

        snippet_query = ' '.join(
            [question] + [item.get('requirement_id', '') + ' ' + item.get('label', '') for item in matched_requirements[:3]]
        ).strip()
        snippets = self._rank_snippets(text, snippet_query or question, top_k=4)
        status, confidence = self._derive_status(text, snippet_query or question, snippets)
        primary_requirement_id = (matched_requirements[0].get('requirement_id') or '').strip() if matched_requirements else ''

        citations = []
        warning_items: list[dict] = []
        retrieval_mode = 'lexical'
        rag_query_text = self._build_rag_query(snippet_query or question, text, matched_requirements=matched_requirements)
        corpus_path = current_app.config.get('NDIS_RAG_CORPUS_PATH') or 'data/rag/ndis/ndis_chunks.jsonl'
        corpus_abs = os.path.abspath(os.path.join(current_app.root_path, os.pardir, corpus_path))
        try:
            rag_result = rag_query_service.query(corpus_path=corpus_abs, query_text=rag_query_text, requirement_id=primary_requirement_id, top_k=3)
            retrieval_mode = getattr(rag_result, 'retrieval_mode', 'lexical')
            citations = [
                {
                    'chunk_id': item.chunk_id,
                    'source_id': item.source_id,
                    'page_number': item.page_number,
                    'score': item.score,
                    'text': item.text,
                }
                for item in rag_result.citations
            ]
            if retrieval_mode == 'lexical' and citations:
                warning_items.append({'source': 'rag', 'message': 'Semantic embeddings are still warming up, so this result used keyword-heavy retrieval.'})
        except FileNotFoundError:
            warning_items.append({'source': 'rag', 'message': 'NDIS citation corpus is not available yet, so this result used document-only analysis.'})
        except Exception:
            logger.exception('Failed to retrieve RAG citations for uploaded document %s', filename)
            warning_items.append({'source': 'rag', 'message': 'Could not retrieve NDIS citations for this document.'})

        status, confidence = self._calibrate_status(
            status=status,
            confidence=confidence,
            document_text=text,
            query_text=snippet_query or question,
            snippets=snippets,
            matched_requirements=matched_requirements,
            citations=citations,
            retrieval_mode=retrieval_mode,
        )

        summary, llm_warning, used_model = self._openrouter_summary(
            status=status,
            question=question,
            focus_area=focus_area,
            snippets=snippets,
            citations=citations,
        )
        if llm_warning:
            warning_items.append({'source': 'llm', 'message': llm_warning})

        provider = 'openrouter' if not llm_warning else 'deterministic'
        model_used = used_model or current_app.config.get('OPENROUTER_MODEL') or 'mistralai/mistral-7b-instruct:free'

        return {
            'success': True,
            'focus_area': focus_area,
            'question': question,
            'matched_requirements': matched_requirements,
            'status': status,
            'confidence': confidence,
            'summary': self._ensure_summary(
                summary,
                status=status,
                focus_area=focus_area,
                snippets=snippets,
                citations=citations,
            ),
            'snippets': snippets,
            'citations': citations,
            'provider': provider,
            'model_used': model_used,
            'retrieval_mode': retrieval_mode,
            'extracted_text': text,
            'warning_items': warning_items,
        }

    def _build_requirement_question(self, matched_requirements: list[dict]) -> str:
        lead = matched_requirements[:3]
        refs = ', '.join([
            f"{item.get('requirement_id')}: {item.get('label')}".strip(': ')
            for item in lead
            if (item.get('requirement_id') or item.get('label'))
        ])
        if not refs:
            return 'Does this document provide usable compliance evidence against the mapped NDIS requirements?'
        return f'Does this document provide usable evidence against these mapped NDIS requirements: {refs}?'

    def _match_requirements(self, *, text: str, filename: str, organization_id: int | None = None, top_k: int = 3) -> list[dict]:
        document_terms = self._tokenize(f'{filename or ""} {(text or "")[:8000]}')
        if not document_terms:
            return []

        requirements = (
            db.session.query(ComplianceRequirement, ComplianceFrameworkVersion)
            .join(ComplianceFrameworkVersion, ComplianceFrameworkVersion.id == ComplianceRequirement.framework_version_id)
            .filter(
                ComplianceFrameworkVersion.is_active.is_(True),
                ComplianceFrameworkVersion.scheme == 'NDIS',
                or_(
                    ComplianceFrameworkVersion.organization_id.is_(None),
                    ComplianceFrameworkVersion.organization_id == (int(organization_id) if organization_id is not None else None),
                ),
            )
            .all()
        )

        # Fallback for normal request context where org_id is not attached to current_app.
        if not requirements:
            requirements = (
                db.session.query(ComplianceRequirement, ComplianceFrameworkVersion)
                .join(ComplianceFrameworkVersion, ComplianceFrameworkVersion.id == ComplianceRequirement.framework_version_id)
                .filter(
                    ComplianceFrameworkVersion.is_active.is_(True),
                    ComplianceFrameworkVersion.scheme == 'NDIS',
                )
                .all()
            )

        scored: list[tuple[float, ComplianceRequirement, ComplianceFrameworkVersion]] = []
        for requirement, framework in requirements:
            requirement_text = ' '.join([
                requirement.requirement_id or '',
                requirement.module_name or '',
                requirement.standard_name or '',
                requirement.outcome_code or '',
                requirement.outcome_text or '',
                requirement.quality_indicator_code or '',
                requirement.quality_indicator_text or '',
                requirement.system_evidence_required or '',
                requirement.implementation_evidence_required or '',
                requirement.workforce_evidence_required or '',
                requirement.participant_evidence_required or '',
                requirement.common_nonconformity_patterns or '',
            ]).lower()
            req_terms = set(self._tokenize(requirement_text))
            if not req_terms:
                continue

            overlap = req_terms.intersection(document_terms)
            if not overlap:
                continue

            score = (len(overlap) / max(4.0, min(float(len(req_terms)), 22.0)))
            if (requirement.module_name or '').lower() and (requirement.module_name or '').lower() in (text or '').lower():
                score += 0.18
            if (requirement.standard_name or '').lower() and (requirement.standard_name or '').lower() in (text or '').lower():
                score += 0.12
            if any(token in (text or '').lower() for token in [(requirement.outcome_code or '').lower(), (requirement.quality_indicator_code or '').lower()] if token):
                score += 0.14
            scored.append((score, requirement, framework))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = []
        seen_requirement_ids = set()
        for score, requirement, framework in scored:
            if score < 0.12:
                continue
            requirement_key = int(requirement.id)
            if requirement_key in seen_requirement_ids:
                continue
            seen_requirement_ids.add(requirement_key)
            selected.append(
                {
                    'requirement_db_id': int(requirement.id),
                    'requirement_id': requirement.requirement_id,
                    'framework_version_id': int(framework.id),
                    'framework_label': f"{framework.scheme} {framework.version_label}",
                    'label': requirement.module_name or requirement.standard_name or requirement.outcome_text or requirement.quality_indicator_text or requirement.requirement_id,
                    'module_name': requirement.module_name,
                    'standard_name': requirement.standard_name,
                    'outcome_code': requirement.outcome_code,
                    'quality_indicator_code': requirement.quality_indicator_code,
                    'evidence_bucket': self._choose_evidence_bucket(filename=filename, text=text, requirement=requirement),
                    'rationale_note': self._build_requirement_rationale(requirement=requirement),
                    'score': round(float(score), 3),
                    'missing_evidence': self._build_missing_evidence(requirement=requirement),
                    'next_action': self._build_next_action(requirement=requirement),
                }
            )
            if len(selected) >= max(1, min(int(top_k or 3), 5)):
                break
        return selected

    def _choose_evidence_bucket(self, *, filename: str, text: str, requirement: ComplianceRequirement) -> str:
        haystack = f'{filename or ""} {(text or "")[:2000]}'.lower()
        if any(term in haystack for term in ('training', 'worker', 'staff', 'competency')) and self._has_text(requirement.workforce_evidence_required):
            return 'workforce'
        if any(term in haystack for term in ('participant', 'client', 'consumer', 'service agreement', 'care plan', 'support plan', 'feedback', 'consent')) and self._has_text(requirement.participant_evidence_required):
            return 'participant'
        if any(term in haystack for term in ('record', 'log', 'review', 'incident', 'form', 'template', 'care plan', 'support plan', 'meeting')):
            return 'implementation'
        return 'system'

    @staticmethod
    def _has_text(value: str | None) -> bool:
        return bool((value or '').strip())

    def _build_missing_evidence(self, *, requirement: ComplianceRequirement) -> str:
        parts = []
        if self._has_text(requirement.system_evidence_required):
            parts.append((requirement.system_evidence_required or '').strip())
        if self._has_text(requirement.implementation_evidence_required):
            parts.append((requirement.implementation_evidence_required or '').strip())
        if self._has_text(requirement.workforce_evidence_required):
            parts.append((requirement.workforce_evidence_required or '').strip())
        if self._has_text(requirement.participant_evidence_required):
            parts.append((requirement.participant_evidence_required or '').strip())
        return ' '.join(parts[:2]).strip()[:600]

    def _build_next_action(self, *, requirement: ComplianceRequirement) -> str:
        action_parts = []
        if (requirement.evidence_owner_role or '').strip():
            action_parts.append(f"Confirm evidence ownership with {requirement.evidence_owner_role.strip()}.")
        if (requirement.review_frequency or '').strip():
            action_parts.append(f"Set or verify a {requirement.review_frequency.strip()} review cadence.")
        if (requirement.system_of_record or '').strip():
            action_parts.append(f"Ensure the final evidence sits in {requirement.system_of_record.strip()}.")
        if not action_parts:
            action_parts.append('Link the document to the matched requirement and fill the missing evidence areas called out in the requirement guidance.')
        return ' '.join(action_parts)[:400]

    def _build_requirement_rationale(self, *, requirement: ComplianceRequirement) -> str:
        parts = [
            requirement.module_name or requirement.standard_name or requirement.requirement_id,
            requirement.outcome_text or requirement.quality_indicator_text or '',
        ]
        return ' '.join([part.strip() for part in parts if (part or '').strip()])[:500]

    def should_auto_analyze(self, filename: str, raw_bytes: bytes) -> bool:
        suffix = (os.path.splitext(filename or '')[1] or '').lower()
        return bool(raw_bytes) and len(raw_bytes) <= 8 * 1024 * 1024 and suffix in self._SUPPORTED_SUFFIXES

    def _infer_focus_area_and_question(self, filename: str, text: str) -> tuple[str, str]:
        haystack = f'{filename or ""} {(text or "")[:4000]}'.lower()
        for rule in self._TOPIC_RULES:
            if any(keyword in haystack for keyword in rule['keywords']):
                return rule['label'], rule['question']
        return (
            'General Compliance Evidence',
            'Does this document provide usable compliance evidence with clear controls, responsibilities, participant protections, and review steps?',
        )

    def _tokenize(self, text: str) -> list[str]:
        tokens = [t for t in re.findall(r'[a-z0-9]+', (text or '').lower()) if len(t) >= 3 and t not in self._STOP_WORDS]
        unique = []
        seen = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            unique.append(token)
        return unique[:80]

    def _phrase_candidates(self, text: str) -> list[str]:
        phrases = []
        seen = set()
        for raw_part in re.split(r'[\n,;:()]+', (text or '').lower()):
            part = re.sub(r'\s+', ' ', raw_part).strip()
            if not part or len(self._tokenize(part)) < 2 or part in seen:
                continue
            seen.add(part)
            phrases.append(part)
        return phrases[:6]

    def _is_noise_block(self, text: str) -> bool:
        value = (text or '').strip()
        if not value:
            return True

        lower = value.lower()
        noise_phrases = {
            'uncontrolled document',
            'document control',
            'sharepoint',
            'file path',
            'all rights reserved',
            'printed copies',
            'this document is uncontrolled',
            'authorised by',
            'approved by',
            'reviewed by',
            'controlled copy',
            'version history',
        }
        if any(phrase in lower for phrase in noise_phrases):
            return True
        if re.match(r'^(page\s+\d+|version\b|review date\b|effective date\b|document owner\b)', lower):
            return True
        if re.search(r'[a-z]:\\|/sites/|https?://|\.pdf\b|\.docx\b|\.xlsx\b', lower):
            return True

        alpha_chars = sum(1 for char in value if char.isalpha())
        separator_chars = sum(1 for char in value if char in '._/\\|')
        if alpha_chars < 20:
            return True
        if separator_chars >= 8 and separator_chars > max(6, alpha_chars // 3):
            return True
        return False

    def _candidate_blocks(self, document_text: str) -> list[str]:
        value = (document_text or '').replace('\r\n', '\n').strip()
        if not value:
            return []

        paragraphs = [part.strip() for part in re.split(r'\n\s*\n+', value) if (part or '').strip()]
        lines = [part.strip() for part in value.split('\n') if (part or '').strip()]

        candidates = []
        seen = set()
        for part in paragraphs + lines:
            cleaned = re.sub(r'\s+', ' ', (part or '').strip())
            lowered = cleaned.lower()
            if len(cleaned) < 30 or lowered in seen or self._is_noise_block(cleaned):
                continue
            seen.add(lowered)
            candidates.append(cleaned)
        return candidates

    def _looks_like_template(self, document_text: str) -> bool:
        lower = (document_text or '').lower()
        if 'template' in lower:
            return True
        placeholder_count = len(re.findall(r'\[[^\]]{2,40}\]|<[^>]{2,40}>', document_text or ''))
        return placeholder_count >= 3

    def _rank_snippets(self, document_text: str, query_text: str, top_k: int = 4) -> list[dict]:
        blocks = self._candidate_blocks(document_text)
        if not blocks:
            return []

        query_terms = self._tokenize(query_text)
        query_term_set = set(query_terms)
        query_phrases = self._phrase_candidates(query_text)
        substantive_terms = {
            'participant', 'consent', 'complaint', 'complaints', 'feedback', 'privacy', 'dignity', 'rights',
            'agreement', 'support', 'supports', 'planning', 'assessment', 'culture', 'diversity', 'risk',
            'review', 'incident', 'governance', 'monitoring', 'confidentiality',
        }

        scored = []
        for block in blocks:
            lower = block.lower()
            block_terms = set(self._tokenize(block))
            score = 0.0
            matched_terms = 0
            for term in query_term_set:
                if term in block_terms:
                    score += 1.0
                    matched_terms += 1
            if matched_terms <= 0:
                continue
            if query_terms:
                score += float(matched_terms) / float(len(query_terms))
            phrase_hits = sum(1 for phrase in query_phrases if phrase and phrase in lower)
            if phrase_hits:
                score += 1.25 * float(phrase_hits)
            if any(term in lower for term in substantive_terms):
                score += 0.5
            if len(block) >= 140:
                score += 0.25
            if score > 0:
                scored.append((score, block))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[:max(1, min(int(top_k or 4), 6))]
        return [
            {
                'score': max(1, int(round(score))),
                'text': (text[:420].rstrip() + '...') if len(text) > 420 else text,
            }
            for score, text in selected
        ]

    def _derive_status(self, document_text: str, query_text: str, snippets: list[dict]) -> tuple[str, float]:
        query_terms = self._tokenize(query_text)
        if not query_terms:
            query_terms = self._tokenize('compliance evidence policy process review audit monitoring')

        lower_text = (document_text or '').lower()
        doc_len = len((document_text or '').strip())
        snippet_count = len(snippets or [])
        hits = sum(1 for term in query_terms if term in lower_text)
        coverage = (float(hits) / float(len(query_terms))) if query_terms else 0.0
        score = (coverage * 0.65) + (min(float(snippet_count) / 4.0, 1.0) * 0.2) + (min(float(doc_len) / 1800.0, 1.0) * 0.15)
        confidence = max(0.0, min(score * 1.05, 1.0))
        if snippet_count >= 4:
            confidence = min(confidence, 0.88)
        elif snippet_count == 3:
            confidence = min(confidence, 0.78)
        elif snippet_count == 2:
            confidence = min(confidence, 0.68)
        else:
            confidence = min(confidence, 0.52)

        if doc_len < 120 and coverage < 0.20:
            return 'Critical gap', round(confidence, 3)
        if score >= 0.78 and coverage >= 0.62 and snippet_count >= 3 and doc_len >= 450:
            return 'Mature', round(confidence, 3)
        if score >= 0.56 and coverage >= 0.42 and snippet_count >= 2 and doc_len >= 220:
            return 'OK', round(confidence, 3)
        if self._looks_like_template(document_text) and coverage >= 0.18 and snippet_count >= 3:
            return 'High risk gap', round(min(confidence, 0.56), 3)
        if score >= 0.22:
            return 'High risk gap', round(confidence, 3)
        return 'Critical gap', round(confidence, 3)

    def _calibrate_status(
        self,
        *,
        status: str,
        confidence: float,
        document_text: str,
        query_text: str,
        snippets: list[dict],
        matched_requirements: list[dict],
        citations: list[dict],
        retrieval_mode: str,
    ) -> tuple[str, float]:
        query_terms = self._tokenize(query_text)
        lower_text = (document_text or '').lower()
        coverage = (float(sum(1 for term in query_terms if term in lower_text)) / float(len(query_terms))) if query_terms else 0.0
        snippet_count = len(snippets or [])
        requirement_count = len(matched_requirements or [])
        citation_count = len(citations or [])
        looks_like_template = self._looks_like_template(document_text)

        calibrated_status = status
        calibrated_confidence = float(confidence)

        if calibrated_status == 'Mature':
            if requirement_count < 2 or citation_count < 2 or snippet_count < 3 or coverage < 0.60:
                calibrated_status = 'OK'
                calibrated_confidence = min(calibrated_confidence, 0.74)

        if calibrated_status == 'OK':
            if requirement_count < 1 or citation_count < 1 or snippet_count < 2 or coverage < 0.42:
                calibrated_status = 'High risk gap'
                calibrated_confidence = min(calibrated_confidence, 0.54)
            elif looks_like_template and citation_count < 2:
                calibrated_status = 'High risk gap'
                calibrated_confidence = min(calibrated_confidence, 0.52)
            elif retrieval_mode == 'lexical':
                calibrated_confidence = min(calibrated_confidence, 0.61)

        if calibrated_status == 'High risk gap' and citation_count == 0 and requirement_count == 0:
            calibrated_confidence = min(calibrated_confidence, 0.46)

        return calibrated_status, round(max(0.0, min(calibrated_confidence, 1.0)), 3)

    def _build_rag_query(self, question_text: str, document_text: str, matched_requirements: list[dict] | None = None) -> str:
        lower = f'{question_text or ""} {(document_text or "")[:2500]}'.lower()
        expansions = []
        topic_bundles = [
            ({'complaint', 'complaints', 'feedback', 'grievance'}, 'complaints management resolution participant feedback'),
            ({'consent', 'privacy', 'dignity', 'confidential', 'confidentiality'}, 'participant rights privacy dignity information management consent'),
            ({'service agreement', 'agreement', 'service terms', 'supports'}, 'service agreements with participants provision of supports responsive support provision'),
            ({'support plan', 'care plan', 'assessment', 'planning', 'goals'}, 'support planning participant needs preferences goals risk assessments'),
            ({'culture', 'cultural', 'diversity', 'inclusive', 'inclusion', 'beliefs', 'values'}, 'person centred supports individual values beliefs participant rights cultural inclusion'),
            ({'risk', 'governance', 'quality', 'incident', 'information management'}, 'governance operational management risk management quality management information management'),
        ]

        for keywords, expansion in topic_bundles:
            if any(keyword in lower for keyword in keywords):
                expansions.append(expansion)

        if matched_requirements:
            lead = matched_requirements[0]
            requirement_expansion = ' '.join(
                part for part in [
                    str(lead.get('requirement_id') or '').strip(),
                    str(lead.get('label') or '').strip(),
                    str(lead.get('module_name') or '').strip(),
                    str(lead.get('standard_name') or '').strip(),
                    str(lead.get('outcome_code') or '').strip(),
                    str(lead.get('quality_indicator_code') or '').strip(),
                ]
                if part
            ).strip()
            if requirement_expansion:
                expansions.append(requirement_expansion)

        if not expansions:
            return question_text
        return ' '.join([question_text.strip()] + expansions).strip()

    def _openrouter_summary(self, *, status: str, question: str, focus_area: str, snippets: list[dict], citations: list[dict]) -> tuple[str | None, str | None, str | None]:
        api_key = (current_app.config.get('OPENROUTER_API_KEY') or '').strip()
        configured_model = (current_app.config.get('OPENROUTER_MODEL') or '').strip() or 'mistralai/mistral-7b-instruct:free'
        fallback_models = [configured_model, 'openrouter/auto']
        token_budgets = [700, 350, 180]
        model_candidates = []
        seen = set()
        for model_name in fallback_models:
            key = (model_name or '').strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            model_candidates.append(model_name)
        if not api_key:
            return None, 'OPENROUTER_API_KEY is not set. Using deterministic explanation.', None

        evidence_points = '\n'.join([f"- {item.get('text', '')}" for item in snippets[:4]]) or '- No strong document snippets found.'
        citation_points = '\n'.join([
            f"- {item.get('source_id', 'ndis')} p.{item.get('page_number') or '?'}: {item.get('text', '')}"
            for item in citations[:3]
        ]) or '- No NDIS citations retrieved.'

        prompt = (
            'You are writing a short evidence review summary for a normal Cenaris user. '
            'Return plain text only, with this exact structure and no markdown:\n'
            '1) Why this status\n'
            '2) Missing evidence\n'
            '3) Recommended next action\n'
            'End with END_SUMMARY\n\n'
            f'Focus area: {focus_area}\n'
            f'Proposed status: {status}\n'
            f'Assessment question: {question}\n\n'
            f'Document evidence:\n{evidence_points}\n\n'
            f'NDIS citations:\n{citation_points}'
        )

        try:
            import requests

            retriable_statuses = {400, 402, 404, 408, 409, 425, 429, 500, 502, 503, 504}
            last_warning = None
            attempt_messages = []
            for model in model_candidates:
                for max_tokens in token_budgets:
                    response = requests.post(
                        'https://openrouter.ai/api/v1/chat/completions',
                        headers={
                            'Authorization': f'Bearer {api_key}',
                            'Content-Type': 'application/json',
                            'HTTP-Referer': 'https://cenaris.local',
                            'X-Title': 'Cenaris Evidence Review',
                        },
                        json={
                            'model': model,
                            'messages': [
                                {'role': 'system', 'content': 'Be practical, precise, and avoid legal conclusions.'},
                                {'role': 'user', 'content': prompt},
                            ],
                            'temperature': 0.1,
                            'max_tokens': max_tokens,
                        },
                        timeout=20,
                    )
                    if response.status_code >= 400:
                        snippet = ((response.text or '').strip()[:140])
                        last_warning = f'OpenRouter summary unavailable ({response.status_code}){": " + snippet if snippet else ""}.'
                        attempt_messages.append(f'{model}:{max_tokens} -> {response.status_code}')
                        if response.status_code in retriable_statuses:
                            continue
                        return None, f'{last_warning} Using deterministic explanation.', None

                    payload = response.json() if response.content else {}
                    choices = payload.get('choices') or []
                    if not choices:
                        last_warning = 'OpenRouter returned no choices.'
                        attempt_messages.append(f'{model}:{max_tokens} -> no choices')
                        continue
                    message = ((choices[0] or {}).get('message') or {}).get('content') or ''
                    if not (message or '').strip():
                        last_warning = 'OpenRouter returned empty content.'
                        attempt_messages.append(f'{model}:{max_tokens} -> empty content')
                        continue
                    return self._normalize_summary(message), None, model

            if last_warning:
                attempts = '; '.join(attempt_messages[-3:]) if attempt_messages else 'unknown'
                return None, f'{last_warning} Attempts: {attempts}. Using deterministic explanation.', None
            return None, 'OpenRouter summary unavailable. Using deterministic explanation.', None
        except Exception:
            logger.exception('OpenRouter summary request failed')
            return None, 'OpenRouter request failed. Using deterministic explanation.', None

    def _normalize_summary(self, text: str | None) -> str:
        value = (text or '').replace('\r\n', '\n').strip()
        if value.startswith('```') and value.endswith('```'):
            lines = value.split('\n')
            if len(lines) >= 3:
                value = '\n'.join(lines[1:-1]).strip()
        if 'END_SUMMARY' in value:
            value = value.split('END_SUMMARY', 1)[0].strip()
        return value

    def _ensure_summary(self, summary_text: str | None, *, status: str, focus_area: str, snippets: list[dict], citations: list[dict]) -> str:
        value = self._normalize_summary(summary_text)
        if self._is_complete_summary(value):
            return value

        first_snippet = ((snippets or [{}])[0] or {}).get('text') if snippets else ''
        first_citation = ((citations or [{}])[0] or {}) if citations else {}
        citation_ref = ''
        if first_citation:
            citation_ref = f"{first_citation.get('source_id', 'ndis')} p.{first_citation.get('page_number') or '?'}"

        why = f'This document was assessed as {status} for {focus_area} based on the strongest matching evidence extracted from the upload.'
        if first_snippet:
            why += f' Top evidence: {first_snippet}'
        missing = 'Some operational detail may still be missing, especially around clear responsibilities, review cadence, participant communication, or evidence of implementation.'
        if citation_ref:
            missing += f' The strongest NDIS reference retrieved was {citation_ref}.'
        action = 'Review the highlighted evidence, confirm the document type, and add clearer process detail or linked supporting records where the summary identifies gaps.'
        return (
            '1) Why this status\n'
            f'{why}\n\n'
            '2) Missing evidence\n'
            f'{missing}\n\n'
            '3) Recommended next action\n'
            f'{action}'
        )

    def _is_complete_summary(self, text: str | None) -> bool:
        value = (text or '').lower()
        return bool(value and 'why this status' in value and 'missing evidence' in value and 'recommended next action' in value)


document_analysis_service = DocumentAnalysisService()