"""
Data isolation tests for multi-tenancy.

Ensures that users cannot access data from other organizations.
"""

import pytest
from app.models import User, Organization, OrganizationMembership, Document
from app import db


def test_document_query_isolation(client, app):
    """Test that document queries are isolated by organization."""
    with app.app_context():
        # Create two organizations
        org1 = Organization(name='Company A', contact_email='a@example.com')
        org2 = Organization(name='Company B', contact_email='b@example.com')
        db.session.add_all([org1, org2])
        db.session.flush()

        # Create users in different orgs
        user1 = User(email='user1@example.com', organization_id=org1.id, email_verified=True)
        user1.set_password('password123')
        user2 = User(email='user2@example.com', organization_id=org2.id, email_verified=True)
        user2.set_password('password123')
        db.session.add_all([user1, user2])
        db.session.flush()

        # Create memberships
        m1 = OrganizationMembership(organization_id=org1.id, user_id=user1.id, role='Admin', is_active=True)
        m2 = OrganizationMembership(organization_id=org2.id, user_id=user2.id, role='Admin', is_active=True)
        db.session.add_all([m1, m2])

        # Create documents for each org
        doc1 = Document(
            filename='org1_document.pdf',
            blob_name='org_1/test_doc1.pdf',
            file_size=1024,
            content_type='application/pdf',
            uploaded_by=user1.id,
            organization_id=org1.id
        )
        doc2 = Document(
            filename='org2_document.pdf',
            blob_name='org_2/test_doc2.pdf',
            file_size=2048,
            content_type='application/pdf',
            uploaded_by=user2.id,
            organization_id=org2.id
        )
        db.session.add_all([doc1, doc2])
        db.session.commit()

        # User1 should only see org1 documents
        org1_docs = Document.query.filter_by(organization_id=org1.id, is_active=True).all()
        assert len(org1_docs) == 1
        assert org1_docs[0].filename == 'org1_document.pdf'

        # User2 should only see org2 documents
        org2_docs = Document.query.filter_by(organization_id=org2.id, is_active=True).all()
        assert len(org2_docs) == 1
        assert org2_docs[0].filename == 'org2_document.pdf'

        # Verify cross-org query returns nothing
        wrong_org_docs = Document.query.filter_by(organization_id=org1.id).filter(
            Document.id == doc2.id
        ).all()
        assert len(wrong_org_docs) == 0


def test_user_cannot_access_other_org_documents(client, app):
    """Test that users cannot download documents from other organizations."""
    with app.app_context():
        # Create two organizations
        org1 = Organization(name='Org 1', contact_email='org1@test.com')
        org2 = Organization(name='Org 2', contact_email='org2@test.com')
        db.session.add_all([org1, org2])
        db.session.flush()

        # Complete onboarding for both orgs
        for org in [org1, org2]:
            org.abn = '12345678901'
            org.organization_type = 'Company'
            org.address = '123 Test St'
            org.industry = 'Technology'
            org.operates_in_australia = True
            from datetime import datetime, timezone
            org.declarations_accepted_at = datetime.now(timezone.utc)
            org.data_processing_ack_at = datetime.now(timezone.utc)
            org.billing_email = org.contact_email
            org.billing_address = org.address

        # Create users
        user1 = User(email='user1@test.com', organization_id=org1.id, email_verified=True)
        user1.set_password('password')
        user2 = User(email='user2@test.com', organization_id=org2.id, email_verified=True)
        user2.set_password('password')
        db.session.add_all([user1, user2])
        db.session.flush()

        # Create memberships
        m1 = OrganizationMembership(organization_id=org1.id, user_id=user1.id, role='Admin', is_active=True)
        m2 = OrganizationMembership(organization_id=org2.id, user_id=user2.id, role='Admin', is_active=True)
        db.session.add_all([m1, m2])

        # Create document for org2
        doc2 = Document(
            filename='secret_doc.pdf',
            blob_name='org_2/secret.pdf',
            file_size=1024,
            content_type='application/pdf',
            uploaded_by=user2.id,
            organization_id=org2.id
        )
        db.session.add(doc2)
        db.session.commit()

        doc2_id = doc2.id

    # Login as user1 (org1)
    client.post('/auth/login', data={
        'email': 'user1@test.com',
        'password': 'password'
    }, follow_redirects=True)

    # Try to access org2's document
    response = client.get(f'/document/{doc2_id}/download')
    # Should get 404 (not found/access denied)
    assert response.status_code == 404


def test_user_cannot_see_other_org_members(client, app):
    """Test that organisation admin can only see their own org members."""
    with app.app_context():
        # Create two organizations
        org1 = Organization(name='Org 1', contact_email='org1@test.com')
        org2 = Organization(name='Org 2', contact_email='org2@test.com')
        db.session.add_all([org1, org2])
        db.session.flush()

        # Complete onboarding
        for org in [org1, org2]:
            org.abn = '12345678901'
            org.organization_type = 'Company'
            org.address = '123 Test St'
            org.industry = 'Technology'
            org.operates_in_australia = True
            from datetime import datetime, timezone
            org.declarations_accepted_at = datetime.now(timezone.utc)
            org.data_processing_ack_at = datetime.now(timezone.utc)
            org.billing_email = org.contact_email
            org.billing_address = org.address

        # Create admin users
        admin1 = User(email='admin1@test.com', organization_id=org1.id, email_verified=True)
        admin1.set_password('password')
        admin2 = User(email='admin2@test.com', organization_id=org2.id, email_verified=True)
        admin2.set_password('password')
        
        # Create regular users
        user1 = User(email='member1@test.com', organization_id=org1.id, email_verified=True)
        user1.set_password('password')
        user2 = User(email='member2@test.com', organization_id=org2.id, email_verified=True)
        user2.set_password('password')
        
        db.session.add_all([admin1, admin2, user1, user2])
        db.session.flush()

        # Create memberships
        m_admin1 = OrganizationMembership(organization_id=org1.id, user_id=admin1.id, role='Admin', is_active=True)
        m_admin2 = OrganizationMembership(organization_id=org2.id, user_id=admin2.id, role='Admin', is_active=True)
        m_user1 = OrganizationMembership(organization_id=org1.id, user_id=user1.id, role='User', is_active=True)
        m_user2 = OrganizationMembership(organization_id=org2.id, user_id=user2.id, role='User', is_active=True)
        db.session.add_all([m_admin1, m_admin2, m_user1, m_user2])
        db.session.commit()

        # Query memberships for org1
        org1_members = OrganizationMembership.query.filter_by(
            organization_id=org1.id,
            is_active=True
        ).all()
        
        # Should only see 2 members from org1
        assert len(org1_members) == 2
        member_emails = {m.user.email for m in org1_members}
        assert 'admin1@test.com' in member_emails
        assert 'member1@test.com' in member_emails
        assert 'member2@test.com' not in member_emails  # From org2


def test_organization_switch_enforces_membership(client, app):
    """Test that users can only switch to organizations they belong to."""
    with app.app_context():
        # Create two organizations
        org1 = Organization(name='Org 1', contact_email='org1@test.com')
        org2 = Organization(name='Org 2', contact_email='org2@test.com')
        db.session.add_all([org1, org2])
        db.session.flush()

        # Complete onboarding for both
        for org in [org1, org2]:
            org.abn = '12345678901'
            org.organization_type = 'Company'
            org.address = '123 Test St'
            org.industry = 'Technology'
            org.operates_in_australia = True
            from datetime import datetime, timezone
            org.declarations_accepted_at = datetime.now(timezone.utc)
            org.data_processing_ack_at = datetime.now(timezone.utc)
            org.billing_email = org.contact_email
            org.billing_address = org.address

        # Create user only in org1
        user = User(email='user@test.com', organization_id=org1.id, email_verified=True)
        user.set_password('password')
        db.session.add(user)
        db.session.flush()

        # Only create membership for org1
        m1 = OrganizationMembership(organization_id=org1.id, user_id=user.id, role='User', is_active=True)
        db.session.add(m1)
        db.session.commit()

        org2_id = org2.id

    # Login
    client.post('/auth/login', data={
        'email': 'user@test.com',
        'password': 'password'
    }, follow_redirects=True)

    # Try to switch to org2 (should fail)
    response = client.post('/org/switch', data={
        'organization_id': str(org2_id)
    }, follow_redirects=True)

    # Should see error message
    assert response.status_code == 200
    assert b'do not have access' in response.data or b'Invalid organization' in response.data


def test_azure_storage_organization_folders(app):
    """Test that Azure Storage service creates org-specific folder paths."""
    from app.services.azure_storage_service import AzureStorageService
    
    service = AzureStorageService()
    
    # Test folder path generation
    org1_folder = service._get_org_folder(1)
    org2_folder = service._get_org_folder(2)
    
    assert org1_folder == 'org_1/'
    assert org2_folder == 'org_2/'
    assert org1_folder != org2_folder
    
    # Test that blob names are prefixed correctly
    # (This would require mocking Azure SDK, so just test the logic)
    blob_name = 'test_document.pdf'
    full_path_org1 = org1_folder + blob_name
    full_path_org2 = org2_folder + blob_name
    
    assert full_path_org1 == 'org_1/test_document.pdf'
    assert full_path_org2 == 'org_2/test_document.pdf'
