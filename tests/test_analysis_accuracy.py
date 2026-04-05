from __future__ import annotations

import json
from datetime import datetime, timezone


def test_rag_query_uses_exact_token_matching_for_lexical_ranking(tmp_path, monkeypatch):
    from app.services.rag_query_service import RagQueryService

    corpus_path = tmp_path / 'rag.jsonl'
    rows = [
        {
            'chunk_id': 'chunk-planning',
            'source_id': 'ndis',
            'page_number': 1,
            'text': 'Planning planning planning guidance only.',
        },
        {
            'chunk_id': 'chunk-plan',
            'source_id': 'ndis',
            'page_number': 2,
            'text': 'The support plan includes review steps and participant sign-off.',
        },
    ]
    corpus_path.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')

    service = RagQueryService()
    monkeypatch.setattr(service, '_get_model', lambda: None)

    result = service.query(corpus_path=str(corpus_path), query_text='support plan review', top_k=1)

    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == 'chunk-plan'


def test_document_analysis_passes_primary_requirement_id_to_rag(app, monkeypatch):
    from app.services.rag_query_service import RagCitation, RagQueryResult
    import app.services.document_analysis_service as analysis_module

    service = analysis_module.DocumentAnalysisService()
    captured: dict[str, str] = {}

    monkeypatch.setattr(service, 'extract_text_from_bytes', lambda filename, raw_bytes: ('complaints handling process review', None))
    monkeypatch.setattr(
        service,
        '_match_requirements',
        lambda **kwargs: [
            {
                'requirement_id': 'NDIS-CM-1',
                'label': 'Complaints Management',
                'module_name': 'Complaints Management',
                'standard_name': 'Complaints',
                'outcome_code': 'CM1',
                'quality_indicator_code': 'QI1',
            }
        ],
    )
    monkeypatch.setattr(service, '_rank_snippets', lambda *args, **kwargs: [{'score': 3, 'text': 'Documented complaints escalation path.'}])
    monkeypatch.setattr(service, '_derive_status', lambda *args, **kwargs: ('OK', 0.55))
    monkeypatch.setattr(
        service,
        '_openrouter_summary',
        lambda **kwargs: (
            '1) Why this status\nEvidence was found.\n\n2) Missing evidence\nReview cadence is not explicit.\n\n3) Recommended next action\nAdd periodic review evidence.',
            None,
            'test-model',
        ),
    )

    def fake_query(*, corpus_path, query_text, requirement_id=None, top_k=3):
        captured['requirement_id'] = requirement_id or ''
        return RagQueryResult(
            answer='ok',
            citations=[
                RagCitation(
                    chunk_id='chunk-1',
                    source_id='ndis',
                    page_number=1,
                    score=1.0,
                    text='Complaint handling guidance.',
                )
            ],
            retrieval_mode='hybrid',
        )

    monkeypatch.setattr(analysis_module.rag_query_service, 'query', fake_query)

    with app.app_context():
        result = service.analyze_document_bytes(filename='complaints.pdf', raw_bytes=b'pdf-bytes', organization_id=1)

    assert result['success'] is True
    assert captured['requirement_id'] == 'NDIS-CM-1'


def test_calibrate_status_downgrades_ok_without_requirement_and_citation_support():
    from app.services.document_analysis_service import DocumentAnalysisService

    service = DocumentAnalysisService()

    status, confidence = service._calibrate_status(
        status='OK',
        confidence=0.67,
        document_text='This policy mentions complaints handling, review, participant communication, and escalation.',
        query_text='complaints handling participant review escalation',
        snippets=[
            {'score': 3, 'text': 'Complaint handling and escalation are described.'},
            {'score': 2, 'text': 'Participant communication is mentioned.'},
        ],
        matched_requirements=[],
        citations=[],
        retrieval_mode='hybrid',
    )

    assert status == 'High risk gap'
    assert confidence <= 0.54


def test_calibrate_status_downgrades_mature_when_support_is_too_thin():
    from app.services.document_analysis_service import DocumentAnalysisService

    service = DocumentAnalysisService()

    status, confidence = service._calibrate_status(
        status='Mature',
        confidence=0.83,
        document_text='This policy covers complaints intake, review, participant communication, escalation, and monitoring controls.',
        query_text='complaints intake review participant communication escalation monitoring',
        snippets=[
            {'score': 4, 'text': 'Complaint intake and review are documented.'},
            {'score': 4, 'text': 'Escalation and monitoring controls are documented.'},
            {'score': 3, 'text': 'Participant communication expectations are documented.'},
        ],
        matched_requirements=[{'requirement_id': 'NDIS-CM-1'}],
        citations=[{'chunk_id': 'chunk-1', 'source_id': 'ndis', 'page_number': 1, 'score': 1.0, 'text': 'Complaint handling guidance.'}],
        retrieval_mode='hybrid',
    )

    assert status == 'OK'
    assert confidence <= 0.74


def test_document_details_uses_simplified_review_language(client, app, db_session, seed_org_user):
    from app.models import Document
    from tests.conftest import login

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        document = Document(
            filename='service_agreement.pdf',
            blob_name='org_1/service_agreement.pdf',
            file_size=4096,
            content_type='application/pdf',
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            ai_status='OK',
            ai_confidence=0.63,
            ai_focus_area='Service Agreements',
            ai_question='Does this document clearly set out service agreements and participant responsibilities?',
            ai_summary='1) Why this status\nCore agreement terms were found.\n\n2) Missing evidence\nReview timing is not clear.\n\n3) Recommended next action\nAdd a review schedule.',
            ai_analysis_at=datetime.now(timezone.utc),
            is_active=True,
        )
        db_session.session.add(document)
        db_session.session.commit()
        doc_id = int(document.id)

    resp = login(client)
    assert resp.status_code in {302, 303}

    detail_resp = client.get(f'/document/{doc_id}/details', follow_redirects=True)

    assert detail_resp.status_code == 200
    assert b'Review Summary' in detail_resp.data
    assert b'Review Focus' in detail_resp.data
    assert b'Assessment Prompt' not in detail_resp.data
    assert b'Mapped NDIS Requirements' in detail_resp.data
    assert b'Matched Controls' not in detail_resp.data
    assert b'Copy Document ID' not in detail_resp.data