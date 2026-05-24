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

    _SUPPORTED_SUFFIXES = ('.txt', '.pdf', '.docx', '.doc')

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

    _DOMAIN_ANCHOR_TERMS = {
        'ndis', 'participant', 'consent', 'privacy', 'dignity', 'confidentiality',
        'complaint', 'complaints', 'incident', 'risk', 'governance', 'safeguard',
        'service agreement', 'support plan', 'care plan', 'restrictive practice',
        'audit', 'review', 'evidence', 'compliance', 'policy', 'procedure',
    }

    _IRRELEVANT_RESUME_MARKERS = {
        'curriculum vitae', 'resume', 'professional summary', 'work experience',
        'employment history', 'skills', 'references available', 'linkedin.com/in',
        'career objective', 'career summary', 'education', 'hobbies',
    }

    _IRRELEVANT_FINANCE_MARKERS = {
        'tax invoice', 'invoice number', 'purchase order', 'unit price', 'subtotal',
        'amount due', 'payment terms', 'bank statement', 'statement period',
    }

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
                extracted = self._extract_pdf_text(raw_bytes)
                if extracted:
                    return extracted, None
                return '', 'Unable to parse readable text from this PDF. It may be image-only or corrupted.'

            if filename_value.endswith('.docx'):
                from docx import Document as DocxDocument

                doc = DocxDocument(io.BytesIO(raw_bytes))
                paragraphs = [(p.text or '').strip() for p in doc.paragraphs]
                return '\n\n'.join([paragraph for paragraph in paragraphs if paragraph]).strip(), None
                
            if filename_value.endswith('.doc'):
                import string
                chars = string.ascii_letters + string.digits + string.punctuation + ' \t\r\n'
                result = []
                current = []
                for byte in raw_bytes:
                    char = chr(byte)
                    if char in chars:
                        current.append(char)
                    elif current:
                        if len(current) >= 4:
                            result.append(''.join(current))
                        current = []
                if len(current) >= 4:
                    result.append(''.join(current))
                # Additional cleanup for binary junk that resembles strings
                extracted = ' '.join(result)
                extracted = re.sub(r'[ \t]+', ' ', extracted)
                extracted = re.sub(r'[\r\n]{3,}', '\n\n', extracted)
                return extracted.strip(), None
        except Exception:
            logger.exception('Failed to extract text from uploaded document %s', filename)
            return '', 'Unable to parse file. Use TXT, PDF, DOCX, or DOC for document analysis.'

        return '', 'Unsupported file type. Use TXT, PDF, DOCX, or DOC.'

    def _extract_pdf_text(self, raw_bytes: bytes) -> str:
        candidates: list[str] = []

        # Strategy 1: pypdf (fast, native text PDFs)
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw_bytes))
            pages = [(page.extract_text() or '').strip() for page in reader.pages]
            text = self._normalize_extracted_text('\n\n'.join([page for page in pages if page]).strip())
            if text:
                candidates.append(text)
        except Exception:
            logger.debug('pypdf extraction failed', exc_info=True)

        # Strategy 2: PyMuPDF/fitz fallback (better with some complex layouts)
        try:
            import fitz

            with fitz.open(stream=raw_bytes, filetype='pdf') as doc:
                chunks = []
                for page in doc:
                    chunks.append((page.get_text('text') or '').strip())
                text = self._normalize_extracted_text('\n\n'.join([chunk for chunk in chunks if chunk]).strip())
                if text:
                    candidates.append(text)
        except Exception:
            logger.debug('fitz extraction failed', exc_info=True)

        # Strategy 3: pdfplumber fallback (can recover tabular text better)
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                chunks = []
                for page in pdf.pages:
                    chunks.append((page.extract_text() or '').strip())
                text = self._normalize_extracted_text('\n\n'.join([chunk for chunk in chunks if chunk]).strip())
                if text:
                    candidates.append(text)
        except Exception:
            logger.debug('pdfplumber extraction failed', exc_info=True)

        if not candidates:
            return ''

        # Choose the richest extraction by useful character count.
        best = max(candidates, key=lambda value: len(value or ''))
        return best

    @staticmethod
    def _normalize_extracted_text(text: str) -> str:
        value = (text or '').replace('\r\n', '\n')
        value = re.sub(r'\u00a0', ' ', value)
        value = re.sub(r'[ \t]+', ' ', value)
        value = re.sub(r'\n{3,}', '\n\n', value)
        return value.strip()

    def build_extraction_diagnostics(self, *, filename: str, raw_bytes: bytes, extracted_text: str) -> dict:
        name = (filename or '').strip().lower()
        text = (extracted_text or '').strip()
        raw_size = int(len(raw_bytes or b''))
        raw_kb = max(1.0, float(raw_size) / 1024.0)
        text_len = len(text)
        chars_per_kb = float(text_len) / raw_kb

        quality = 'high'
        reasons: list[str] = []

        if name.endswith('.pdf'):
            # Image-only or poorly extracted PDFs often have very low text density.
            if text_len < 400 or chars_per_kb < 10.0:
                quality = 'low'
                reasons.append('Low extracted text density for PDF; possible scanned/image-only content.')
            elif text_len < 1200 or chars_per_kb < 20.0:
                quality = 'medium'
                reasons.append('Moderate text extraction quality; review source PDF clarity.')
        else:
            if text_len < 200:
                quality = 'low'
                reasons.append('Extracted text is very short for reliable assessment.')

        return {
            'quality': quality,
            'filename': filename,
            'raw_size_bytes': raw_size,
            'extracted_chars': text_len,
            'chars_per_kb': round(chars_per_kb, 2),
            'warnings': reasons,
        }

    def validate_document_before_scoring(self, *, text: str, filename: str, raw_bytes: bytes) -> dict:
        value = (text or '').strip()
        if len(value) < 100:
            return {
                'valid': False,
                'reason': 'DOCUMENT_TOO_SHORT',
                'confidence': 0.12,
                'status': 'Critical gap',
                'message': 'Document contains fewer than 100 characters.',
            }

        bracket_placeholders = len(re.findall(r'\[[^\]]{0,30}\]', value))
        underscores = len(re.findall(r'_{4,}', value))
        dots = len(re.findall(r'\.{4,}', value))
        form_labels = len(re.findall(r'(?:name|date|signature|signed):\s*[_\.]{2,}', value, re.IGNORECASE))
        total_markers = bracket_placeholders + underscores + dots + form_labels

        text_no_markers = value
        for pattern in [r'\[[^\]]{0,30}\]', r'_{4,}', r'\.{4,}']:
            text_no_markers = re.sub(pattern, '', text_no_markers)

        fill_ratio = len(text_no_markers.strip()) / max(len(value), 1)
        word_count = len(re.findall(r'\b\w+\b', value))

        if (total_markers >= 10 and fill_ratio < 0.40) or (total_markers >= 6 and word_count < 300):
            return {
                'valid': False,
                'reason': 'BLANK_TEMPLATE',
                'confidence': 0.15,
                'status': 'Critical gap',
                'message': f'Blank template with {total_markers} unfilled sections.',
            }

        if total_markers >= 4 and fill_ratio < 0.65:
            return {
                'valid': True,
                'reason': 'PARTIAL_TEMPLATE',
                'confidence_cap': 0.42,
                'penalty_multiplier': 0.50,
                'message': f'Partially incomplete document ({total_markers} unfilled sections).',
            }

        text_lower = value.lower()
        marketing_keywords = [
            'call us now',
            'visit our website',
            'book now',
            'limited time',
            'free consultation',
            'marketing',
            'marketing management',
            'promotion',
            'advertising',
            'pricing',
            'distribution',
            'market research',
            'branding',
        ]
        marketing_hits = sum(1 for keyword in marketing_keywords if keyword in text_lower)
        if marketing_hits >= 2:
            return {
                'valid': False,
                'reason': 'INVALID_TYPE_MARKETING',
                'confidence': 0.18,
                'status': 'Critical gap',
                'message': 'Document appears to be marketing content, not a compliance policy.',
            }

        has_ndis = 'ndis' in text_lower
        has_ndis_context = any(
            marker in text_lower
            for marker in (
                'practice standard',
                'quality indicator',
                'ndis commission',
                'quality and safeguards commission',
            )
        )
        ndis_markers = has_ndis and has_ndis_context
        policy_markers = any(
            term in text_lower
            for term in ('policy', 'procedure', 'governance', 'incident', 'complaint', 'consent')
        )
        if not ndis_markers or not policy_markers:
            invalid_types = {
                'email': ['from:', 'to:', 'subject:', 'sent:', 'dear', 'regards,'],
                'resume': ['curriculum vitae', 'work experience', 'education:'],
                'invoice': ['invoice number', 'total due', 'payment terms'],
                'marketing': ['call us now', 'visit our website', 'book now'],
            }
            email_hits = sum(1 for keyword in invalid_types['email'] if keyword in text_lower)
            if ('from:' in text_lower and 'to:' in text_lower) or ('subject:' in text_lower and email_hits >= 2):
                return {
                    'valid': False,
                    'reason': 'INVALID_TYPE_EMAIL',
                    'confidence': 0.18,
                    'status': 'Critical gap',
                    'message': 'Document appears to be a email, not a compliance policy.',
                }

            for doc_type, keywords in invalid_types.items():
                if doc_type == 'email':
                    continue
                matches = sum(1 for keyword in keywords if keyword in text_lower)
                if matches >= 2:
                    return {
                        'valid': False,
                        'reason': f'INVALID_TYPE_{doc_type.upper()}',
                        'confidence': 0.18,
                        'status': 'Critical gap',
                        'message': f'Document appears to be a {doc_type}, not a compliance policy.',
                    }

            return {
                'valid': False,
                'reason': 'NON_NDIS_POLICY',
                'confidence': 0.2,
                'status': 'Critical gap',
                'message': 'Document does not appear to be an NDIS-related policy or procedure.',
            }

        if (filename or '').lower().endswith('.pdf') and raw_bytes:
            file_size_kb = len(raw_bytes) / 1024.0
            chars_per_kb = len(value) / max(file_size_kb, 0.1)
            if chars_per_kb < 150:
                return {
                    'valid': False,
                    'reason': 'IMAGE_PDF',
                    'confidence': 0.14,
                    'status': 'Critical gap',
                    'message': 'Scanned or image-only PDF with minimal text extraction.',
                }
            if chars_per_kb < 500:
                return {
                    'valid': True,
                    'reason': 'LOW_QUALITY_SCAN',
                    'confidence_cap': 0.38,
                    'penalty_multiplier': 0.62,
                    'message': 'Low text extraction quality detected for this PDF.',
                }

        return {'valid': True, 'reason': 'OK'}

    def analyze_document_bytes(self, *, filename: str, raw_bytes: bytes, organization_id: int | None = None) -> dict:
        text, extraction_error = self.extract_text_from_bytes(filename, raw_bytes)
        if extraction_error:
            return {
                'success': False,
                'error': extraction_error,
                'extracted_text': '',
            }
        extraction_diagnostics = self.build_extraction_diagnostics(
            filename=filename,
            raw_bytes=raw_bytes,
            extracted_text=text,
        )

        validation = self.validate_document_before_scoring(
            text=text,
            filename=filename,
            raw_bytes=raw_bytes,
        )
        if not validation.get('valid'):
            message = validation.get('message') or 'Document failed validation.'
            warning_items = [{'source': 'validation', 'message': message}]
            return {
                'success': True,
                'focus_area': 'Document Validation',
                'question': 'Is the uploaded document valid for compliance analysis?',
                'matched_requirements': [],
                'status': validation.get('status', 'Critical gap'),
                'confidence': float(validation.get('confidence', 0.2)),
                'summary': message,
                'snippets': [],
                'citations': [],
                'provider': 'deterministic',
                'model_used': 'deterministic',
                'retrieval_mode': 'validation',
                'extracted_text': text,
                'warning_items': warning_items,
                'scoring_diagnostics': {
                    'validation_reason': validation.get('reason', 'UNKNOWN'),
                    'warnings': [message],
                },
                'extraction_diagnostics': extraction_diagnostics,
            }

        validation_penalty = float(validation.get('penalty_multiplier', 1.0))
        confidence_cap = float(validation.get('confidence_cap', 1.0))
        validation_warning = validation.get('message')

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
            rag_result = rag_query_service.query(
                corpus_path=corpus_abs,
                query_text=rag_query_text,
                requirement_id=primary_requirement_id,
                top_k=15,
            )
            retrieval_mode = getattr(rag_result, 'retrieval_mode', 'lexical')
            raw_citations = [
                {
                    'chunk_id': item.chunk_id,
                    'source_id': item.source_id,
                    'page_number': item.page_number,
                    'score': item.score,
                    'text': item.text,
                }
                for item in rag_result.citations
            ]
            citations = self._filter_quality_citations(raw_citations, text)
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

        if extraction_diagnostics.get('quality') == 'low' and status in {'Mature', 'OK'}:
            status = self._downgrade_status(status)
            confidence = round(min(float(confidence), 0.58), 3)
            warning_items.append(
                {
                    'source': 'extraction',
                    'message': 'Low extraction quality detected; status was conservatively reduced to avoid overconfidence.',
                }
            )

        if validation_penalty < 1.0:
            if status in {'Mature', 'OK'} and validation_penalty <= 0.60:
                status = self._downgrade_status(status)
            confidence = round(float(confidence) * validation_penalty, 3)
        if confidence_cap < 1.0:
            confidence = round(min(float(confidence), confidence_cap), 3)
        if validation_warning:
            warning_items.append({'source': 'validation', 'message': validation_warning})

        scoring_diagnostics = self._build_scoring_diagnostics(
            document_text=text,
            query_text=snippet_query or question,
            snippets=snippets,
            matched_requirements=matched_requirements,
            citations=citations,
            retrieval_mode=retrieval_mode,
            status=status,
            confidence=confidence,
        )
        scoring_diagnostics['extraction'] = extraction_diagnostics
        for message in scoring_diagnostics.get('warnings', []):
            warning_items.append({'source': 'scoring', 'message': message})
        for message in extraction_diagnostics.get('warnings', []):
            warning_items.append({'source': 'extraction', 'message': message})

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
            'scoring_diagnostics': scoring_diagnostics,
            'extraction_diagnostics': extraction_diagnostics,
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
        import re
        lower = (document_text or '').lower()
        if 'template' in lower[:1000] or 'blank form' in lower[:1000]:
            return True
            
        placeholders = re.findall(r'\[[^\]]{2,40}\]|<[^>]{2,40}>|\{([^\}]{2,40})\}', document_text or '')
        blank_lines = re.findall(r'_{4,}|\.{4,}', document_text or '')
        unfilled_fields = re.findall(r'(?i)(?:\bname:|\bdate:|\bsigned:|\bsignature:|\bstart:|\breview:)\s*(?:[_\.\s]*)(?=\n|$)|(?:\b[A-Z]=)', document_text or '')
        
        marker_count = len(placeholders) + len(blank_lines) + len(unfilled_fields)
        words = [w for w in re.findall(r'\w{3,}', lower) if w not in {'the', 'and', 'for', 'with'}]
        word_count = len(words)
        
        if marker_count >= 12:
            return True
        if marker_count > 0:
            words_per_marker = word_count / marker_count
            if words_per_marker < 40:
                return True
        if word_count < 300 and marker_count >= 4:
            return True
        return False

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
        """
        Rubric-based scoring across 5 independent signals — NOT keyword-overlap percentage.

        Signal 1 — Substance (40 pts): Does the document contain real implemented procedures?
        Signal 2 — Coverage (25 pts): Does it address the specific NDIS requirement?
        Signal 3 — Depth (20 pts): Is it detailed enough?
        Signal 4 — Structure (10 pts): Is it an implemented doc, not just a template?
        Signal 5 — Snippet quality (5 pts): How many strong evidence blocks were found?
        """
        lower_text = (document_text or '').lower()
        doc_len = len((document_text or '').strip())
        snippet_count = len(snippets or [])

        # ── Signal 1: Substance (40 pts) ────────────────────────────────────────
        # Real implemented documents use action language, responsibilities, and procedures.
        # Generic buzzword docs score low here regardless of length.
        action_indicators = [
            'must', 'will', 'shall', 'is responsible', 'are responsible', 'ensures', 'ensure',
            'maintained', 'reviewed', 'documented', 'recorded', 'provided', 'conducted',
            'reported', 'investigated', 'resolved', 'trained', 'assessed', 'monitored',
        ]
        responsibility_indicators = [
            'manager', 'coordinator', 'worker', 'staff', 'team', 'ceo', 'board', 'committee',
            'director', 'supervisor', 'employee', 'provider', 'organisation',
        ]
        process_indicators = [
            'procedure', 'process', 'policy', 'step', 'steps', 'form', 'register',
            'checklist', 'protocol', 'guideline', 'framework', 'schedule',
            'plan', 'review', 'audit', 'report', 'log', 'record',
        ]
        timeframe_indicators = [
            'within', 'days', 'hours', 'weeks', 'monthly', 'annually', 'annually',
            'quarterly', 'immediately', 'timeframe', 'deadline', 'due date',
        ]

        action_hits = sum(1 for w in action_indicators if w in lower_text)
        responsibility_hits = sum(1 for w in responsibility_indicators if w in lower_text)
        process_hits = sum(1 for w in process_indicators if w in lower_text)
        timeframe_hits = sum(1 for w in timeframe_indicators if w in lower_text)

        # Normalise each sub-signal to [0, 1]
        action_score = min(action_hits / 6.0, 1.0)          # 6+ hits = full score
        responsibility_score = min(responsibility_hits / 3.0, 1.0)
        process_score = min(process_hits / 5.0, 1.0)
        timeframe_score = min(timeframe_hits / 2.0, 1.0)

        substance_raw = (action_score * 0.40 + responsibility_score * 0.25 +
                         process_score * 0.25 + timeframe_score * 0.10)
        substance_pts = substance_raw * 40.0

        # ── Signal 2: Coverage (25 pts) ─────────────────────────────────────────
        # Does the document address the specific NDIS requirement area being asked?
        query_terms = self._tokenize(query_text)
        if not query_terms:
            query_terms = self._tokenize('compliance evidence policy process review monitoring')
        coverage_result = self._calculate_coverage_with_depth(document_text, query_terms)
        coverage_pts = coverage_result['score']
        coverage_ratio = coverage_result['breadth']

        domain_anchor_hits = self._domain_anchor_hit_count(lower_text)
        is_likely_irrelevant = self._looks_like_irrelevant_document(lower_text)

        # ── Signal 3: Depth (20 pts) ────────────────────────────────────────────
        # A real compliance document needs sufficient detail.
        # Rewards docs ≥ 800 chars; penalises stubs < 200 chars.
        depth_from_length = min(doc_len / 2500.0, 1.0)
        depth_from_snippets = min(snippet_count / 4.0, 1.0)
        depth_pts = (depth_from_length * 0.6 + depth_from_snippets * 0.4) * 20.0

        # ── Signal 4: Structure (10 pts) ────────────────────────────────────────
        # Is this an implemented document or just a blank template?
        structure_pts = 10.0
        # Bonus: clear section headings or numbered lists suggest real structure
        has_headings = bool(re.search(r'\n\s*\d+\.\s+[A-Z]|\n[A-Z][^\n]{5,50}\n', document_text or ''))
        if has_headings:
            structure_pts = min(structure_pts * 1.3, 10.0)

        # ── Signal 5: Snippet quality bonus (5 pts) ──────────────────────────────
        snippet_pts = min(snippet_count / 4.0, 1.0) * 5.0

        # ── Combine ─────────────────────────────────────────────────────────────
        total_pts = substance_pts + coverage_pts + depth_pts + structure_pts + snippet_pts
        max_pts = 100.0
        raw_score = total_pts / max_pts  # [0, 1]

        # Guardrail: non-domain docs can match generic policy language by accident.
        relevance_gate = 1.0
        if domain_anchor_hits <= 1:
            relevance_gate *= 0.55
        elif domain_anchor_hits <= 3:
            relevance_gate *= 0.78
        if coverage_ratio < 0.20:
            relevance_gate *= 0.80
        raw_score *= relevance_gate

        if is_likely_irrelevant:
            raw_score = min(raw_score, 0.22)

        # Confidence mirrors the score but stays honest about uncertainty
        confidence = min(raw_score * 1.05, 0.97)

        # ── Map to status ────────────────────────────────────────────────────────
        if doc_len < 100:
            return 'Critical gap', round(min(confidence, 0.30), 3)
        if raw_score >= 0.75 and domain_anchor_hits >= 4 and snippet_count >= 2 and not is_likely_irrelevant:
            return 'Mature', round(confidence, 3)
        if raw_score >= 0.55:
            return 'OK', round(confidence, 3)
        if raw_score >= 0.30:
            return 'High risk gap', round(confidence, 3)
        return 'Critical gap', round(confidence, 3)

    def _calculate_coverage_with_depth(self, document_text: str, required_terms: list[str]) -> dict:
        term_scores = {}
        lower = (document_text or '').lower()
        for term in required_terms:
            count = lower.count(term.lower())
            has_procedure = self._check_procedural_context(document_text, term)

            if count == 0:
                depth = 0.0
            elif count == 1 and not has_procedure:
                depth = 0.3
            elif count <= 2 and has_procedure:
                depth = 0.6
            elif count <= 4 and has_procedure:
                depth = 0.8
            else:
                depth = 1.0

            term_scores[term] = depth

        covered = sum(1 for score in term_scores.values() if score > 0)
        breadth = covered / max(len(required_terms), 1)
        avg_depth = sum(term_scores.values()) / max(len(required_terms), 1)
        score = ((breadth ** 0.6) * 0.6 + avg_depth * 0.4) * 25.0

        return {
            'score': score,
            'breadth': breadth,
            'depth': avg_depth,
        }

    def _check_procedural_context(self, text: str, term: str) -> bool:
        action_words = ['must', 'shall', 'will', 'ensure', 'procedure', 'process']
        pattern = re.compile(rf'\b{re.escape(term)}\b', re.IGNORECASE)
        for match in pattern.finditer(text or ''):
            start = max(0, match.start() - 60)
            end = min(len(text or ''), match.end() + 60)
            context = (text or '')[start:end].lower()
            if any(word in context for word in action_words):
                return True
        return False

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
        """
        Apply light trust adjustments AFTER the rubric scoring.
        This no longer aggressively caps scores — it only applies targeted penalties
        and bonuses based on system-level signals.
        """
        calibrated_status = status
        calibrated_confidence = float(confidence)

        # RAG alignment bonus: each retrieved citation means the doc aligns with the NDIS standard
        citation_count = len(citations or [])
        if citation_count >= 2:
            calibrated_confidence = min(calibrated_confidence + 0.04, 0.97)
        elif citation_count == 0 and calibrated_status in ('Mature', 'OK'):
            # Zero RAG citations on a positive result → mild confidence penalty
            calibrated_confidence = min(calibrated_confidence, 0.72)

        # Positive status without requirement mapping and citations is usually overconfident.
        if citation_count == 0 and not matched_requirements and calibrated_status in ('Mature', 'OK'):
            calibrated_status = self._downgrade_status(calibrated_status)
            calibrated_confidence = min(calibrated_confidence, 0.54)

        # Mature requires stronger support than a single weak citation.
        if calibrated_status == 'Mature' and citation_count < 2:
            calibrated_status = 'OK'
            calibrated_confidence = min(calibrated_confidence, 0.74)

        # Lexical-only retrieval uncertainty (embeddings not loaded)
        if retrieval_mode == 'lexical' and calibrated_status == 'Mature':
            calibrated_confidence = min(calibrated_confidence, 0.80)

        if retrieval_mode == 'lexical' and citation_count == 0 and calibrated_status in ('Mature', 'OK'):
            calibrated_status = self._downgrade_status(calibrated_status)
            calibrated_confidence = min(calibrated_confidence, 0.52)

        if self._looks_like_irrelevant_document(document_text):
            calibrated_status = 'Critical gap'
            calibrated_confidence = min(calibrated_confidence, 0.24)

        return calibrated_status, round(max(0.0, min(calibrated_confidence, 1.0)), 3)

    @staticmethod
    def _downgrade_status(status: str) -> str:
        if status == 'Mature':
            return 'OK'
        if status == 'OK':
            return 'High risk gap'
        if status == 'High risk gap':
            return 'Critical gap'
        return status

    def _domain_anchor_hit_count(self, lower_text: str) -> int:
        return sum(1 for term in self._DOMAIN_ANCHOR_TERMS if term in (lower_text or ''))

    def _looks_like_irrelevant_document(self, document_text: str) -> bool:
        lower = (document_text or '').lower()
        if not lower:
            return False

        resume_hits = sum(1 for marker in self._IRRELEVANT_RESUME_MARKERS if marker in lower)
        finance_hits = sum(1 for marker in self._IRRELEVANT_FINANCE_MARKERS if marker in lower)
        domain_hits = self._domain_anchor_hit_count(lower)

        if resume_hits >= 3 and domain_hits <= 2:
            return True
        if finance_hits >= 3 and domain_hits <= 2:
            return True
        return False

    def _build_scoring_diagnostics(
        self,
        *,
        document_text: str,
        query_text: str,
        snippets: list[dict],
        matched_requirements: list[dict],
        citations: list[dict],
        retrieval_mode: str,
        status: str,
        confidence: float,
    ) -> dict:
        lower_text = (document_text or '').lower()
        warnings: list[str] = []
        domain_anchor_hits = self._domain_anchor_hit_count(lower_text)
        is_irrelevant = self._looks_like_irrelevant_document(lower_text)
        if is_irrelevant:
            warnings.append('Document appears non-compliance (for example resume/invoice style), so confidence and status were capped.')
        if not matched_requirements:
            warnings.append('No requirement mapping found; positive statuses are down-weighted.')
        if not citations:
            warnings.append('No NDIS citations retrieved; confidence was reduced.')
        if retrieval_mode == 'lexical':
            warnings.append('Lexical retrieval mode active; semantic similarity evidence is unavailable for this run.')

        return {
            'document_length': len((document_text or '').strip()),
            'query_term_count': len(self._tokenize(query_text)),
            'snippet_count': len(snippets or []),
            'matched_requirement_count': len(matched_requirements or []),
            'citation_count': len(citations or []),
            'domain_anchor_hits': domain_anchor_hits,
            'looks_like_template': self._looks_like_template(document_text),
            'looks_like_irrelevant': is_irrelevant,
            'retrieval_mode': retrieval_mode,
            'final_status': status,
            'final_confidence': float(confidence),
            'warnings': warnings,
        }

    def _identify_present_topics(self, document_text: str) -> list[str]:
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

        lower = (document_text or '').lower()
        present = []
        for topic, keywords in topic_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in lower)
            if matches >= 2:
                present.append(topic)
        return present

    def _identify_missing_topics(self, document_text: str) -> list[str]:
        critical_topics = {
            'participant consent procedures': ['consent', 'informed consent'],
            'safeguarding procedures': ['safeguard', 'abuse prevention'],
            'incident reporting': ['incident', 'reportable'],
            'complaints handling': ['complaint', 'grievance'],
            'risk assessment': ['risk assessment', 'risk management'],
            'privacy procedures': ['privacy', 'confidential'],
            'restrictive practice': ['restrictive practice', 'restraint'],
        }

        lower = (document_text or '').lower()
        missing = []
        for topic, keywords in critical_topics.items():
            found = any(keyword in lower for keyword in keywords)
            if not found:
                missing.append(topic)
        return missing

    def _build_rag_query(self, question_text: str, document_text: str, matched_requirements: list[dict] | None = None) -> str:
        present = self._identify_present_topics(document_text)
        missing = self._identify_missing_topics(document_text)

        doc_header = (document_text or '').lower()[:500]
        if 'policy' in doc_header:
            doc_type = 'policy'
        elif 'procedure' in doc_header:
            doc_type = 'procedure'
        else:
            doc_type = 'document'

        parts = [f'NDIS compliance requirements for {doc_type} documents']
        if present:
            parts.append(f"addressing {', '.join(present[:3])}")
        if missing:
            parts.append(f"Requirements for {', '.join(missing[:5])}")

        if matched_requirements:
            lead = matched_requirements[0]
            req_name = (lead.get('label') or lead.get('requirement_id') or '').strip()
            if req_name:
                parts.append(f'Standards for {req_name}')

        return '. '.join(part.strip() for part in parts if part).strip() + '.'

    def _filter_quality_citations(self, citations: list[dict], document_text: str, min_score: float = 0.65) -> list[dict]:
        action_words = {
            'must', 'shall', 'will', 'ensure', 'required',
            'responsible', 'documented', 'procedure', 'process',
        }
        doc_words = set(re.findall(r'\b\w{5,}\b', (document_text or '').lower()))

        ranked: list[tuple[float, dict]] = []
        for citation in citations:
            score = float(citation.get('score', 0) or 0)
            if score < min_score:
                continue

            citation_text = (citation.get('text') or '').strip()
            if len(citation_text) < 80:
                continue

            citation_lower = citation_text.lower()
            if not any(word in citation_lower for word in action_words):
                continue

            citation_words = set(re.findall(r'\b\w{5,}\b', citation_lower))
            if doc_words and citation_words:
                overlap = len(doc_words & citation_words) / len(doc_words | citation_words)
            else:
                overlap = 0.0
            if overlap < 0.05:
                continue

            adjusted_score = score * (1.0 + overlap)
            ranked.append((adjusted_score, citation))

        if not ranked:
            return citations[:5]

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in ranked[:7]]

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