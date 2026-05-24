from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('SECRET_KEY', 'local-dev-secret')

from app import create_app
from app.services.document_analysis_service import document_analysis_service


def analyze_file(file_path: Path) -> dict:
    raw_bytes = file_path.read_bytes()
    result = document_analysis_service.analyze_document_bytes(
        filename=file_path.name,
        raw_bytes=raw_bytes,
        organization_id=None,
    )
    return {
        'file': str(file_path),
        'status': result.get('status'),
        'confidence': result.get('confidence'),
        'summary': result.get('summary'),
        'warning_items': result.get('warning_items', []),
        'retrieval_mode': result.get('retrieval_mode'),
        'citations': len(result.get('citations') or []),
    }


def main() -> None:
    base = Path('testingdocs')
    files = {
        'good_policy': base / 'Good_doc_Incident-Management-Policy-and-Procedure-V3.pdf',
        'perfect_policy': base / 'MISSING_PERFECT_POLICY.pdf',
        'generic_doc': base / 'assingment_doc_generic.pdf',
        'template': base / 'template.pdf',
        'scanned_pdf': base / 'scanned pdf.pdf',
        'marketing': base / 'marketing.pdf',
    }

    app = create_app('default')
    with app.app_context():
        results = {}
        for key, path in files.items():
            if not path.exists():
                results[key] = {'file': str(path), 'error': 'missing'}
                continue
            results[key] = analyze_file(path)

    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
