from tests.conftest import login


def test_compliance_journey_redirects_to_requirements(client, app, seed_org_user):
    _org_id, _user_id, _membership_id = seed_org_user

    resp = login(client)
    assert resp.status_code in {302, 303}

    page = client.get('/compliance-journey', follow_redirects=False)
    assert page.status_code in {302, 303}
    assert '/compliance-requirements' in (page.headers.get('Location') or '')


def test_compliance_journey_query_param_redirects_to_requirements(client, app, seed_org_user):
    _org_id, _user_id, _membership_id = seed_org_user

    resp = login(client)
    assert resp.status_code in {302, 303}

    page = client.get('/compliance-journey?persona=sole_trader', follow_redirects=False)
    assert page.status_code in {302, 303}
    assert '/compliance-requirements' in (page.headers.get('Location') or '')


def test_compliance_journey_persona_post_redirects_to_requirements(client, app, seed_org_user):
    _org_id, _user_id, _membership_id = seed_org_user

    resp = login(client)
    assert resp.status_code in {302, 303}

    set_resp = client.post('/compliance-journey/persona', data={'persona': 'auditor'}, follow_redirects=False)
    assert set_resp.status_code in {302, 303}
    assert '/compliance-requirements' in (set_resp.headers.get('Location') or '')


def test_compliance_journey_requires_login(client):
    page = client.get('/compliance-journey', follow_redirects=False)
    assert page.status_code in {302, 401}
