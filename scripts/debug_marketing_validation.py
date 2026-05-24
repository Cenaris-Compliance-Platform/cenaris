from pathlib import Path

from app.services.document_analysis_service import DocumentAnalysisService


def main() -> None:
    svc = DocumentAnalysisService()
    path = Path('testingdocs/marketing.pdf')
    raw_bytes = path.read_bytes()
    text, error = svc.extract_text_from_bytes(path.name, raw_bytes)
    if error:
        print('extract_error:', error)
        return
    text_lower = text.lower()
    ndis_markers = any(
        marker in text_lower
        for marker in (
            'ndis',
            'practice standard',
            'quality indicator',
            'ndis commission',
            'quality and safeguards commission',
        )
    )
    policy_markers = any(
        term in text_lower
        for term in ('policy', 'procedure', 'governance', 'incident', 'complaint', 'consent')
    )
    print('ndis_markers:', ndis_markers)
    print('policy_markers:', policy_markers)
    print('ndis_hits:', text_lower.count('ndis'))
    print('snippet:', ' '.join(text.split())[:500])


if __name__ == '__main__':
    main()
