from tests.conftest import login


def test_compliance_journey_page_loads(client, app, seed_org_user):
    _org_id, _user_id, _membership_id = seed_org_user

    resp = login(client)
    assert resp.status_code in {302, 303}

    page = client.get('/compliance-journey')
    assert page.status_code == 200

    body = page.get_data(as_text=True)
    assert 'Compliance Journey' in body
    assert 'Start To Finish Workflow' in body
    assert 'The 4 Evidence Types Auditors Ask For' in body
    assert 'Choose Your Workflow Type' in body
    assert 'Quick-Start Checklist' in body


def test_compliance_journey_persona_query_renders_sole_trader_playbook(client, app, seed_org_user):
    _org_id, _user_id, _membership_id = seed_org_user

    resp = login(client)
    assert resp.status_code in {302, 303}

    page = client.get('/compliance-journey?persona=sole_trader')
    assert page.status_code == 200

    body = page.get_data(as_text=True)
    assert 'Sole Trader Quick-Start Checklist' in body
    assert 'Generate the audit pack before assessment date' in body


def test_compliance_journey_persona_post_persists_selection(client, app, seed_org_user):
    _org_id, _user_id, _membership_id = seed_org_user

    resp = login(client)
    assert resp.status_code in {302, 303}

    set_resp = client.post('/compliance-journey/persona', data={'persona': 'auditor'}, follow_redirects=False)
    assert set_resp.status_code in {302, 303}

    page = client.get('/compliance-journey')
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'Auditor Quick-Start Checklist' in body
    assert 'Sample linked documents and AI review notes' in body


def test_compliance_journey_requires_login(client):
    page = client.get('/compliance-journey', follow_redirects=False)
    assert page.status_code in {302, 401}
