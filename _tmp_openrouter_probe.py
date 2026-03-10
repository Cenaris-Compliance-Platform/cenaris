from app import create_app
from app.main.routes import _openrouter_demo_summary

app = create_app()
with app.app_context():
    text, warn, model = _openrouter_demo_summary(
        status='OK',
        question='Does this policy define incident reporting and participant communication?',
        snippets=[{'text': 'Incident reporting timeline is defined with owner responsibilities.'}],
        citations=[{'source_id': 'ndis-practice-standards', 'page_number': 5, 'text': 'Providers should ensure quality and safe supports.'}],
    )
    print('HAS_TEXT', bool((text or '').strip()))
    print('WARNING', warn or '')
    print('MODEL', model or '')
