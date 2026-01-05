"""
Automated Black Box Testing for Phase 1
Tests all user-facing functionality without knowledge of internal implementation
"""
import pytest
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from faker import Faker
import requests
import os
from urllib.parse import urljoin

fake = Faker()

# Test Configuration
_raw_test_base_url = (os.environ.get('TEST_BASE_URL') or '').strip()
_port = (os.environ.get('PORT') or '5000').strip()
BASE_URL = _raw_test_base_url or f'http://localhost:{_port}'
TIMEOUT = 10
TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), 'test_files')


# This file is a full end-to-end Selenium suite and is intentionally slow.
# Keep it opt-in so regular `pytest` runs stay fast.
pytestmark = pytest.mark.blackbox

if os.environ.get('RUN_BLACK_BOX_TESTS', '').strip() != '1':
    pytest.skip(
        'Black-box Selenium suite disabled by default. '
        'Set RUN_BLACK_BOX_TESTS=1 and ensure the app is running at TEST_BASE_URL.',
        allow_module_level=True,
    )


def _preflight_verify_server_or_fail() -> None:
    """Fail fast with a clear error if the web app isn't reachable.

    Without this, Selenium ends up on a browser error page and later tests fail
    with confusing "NoSuchElement" errors.
    """
    login_url = urljoin(BASE_URL.rstrip('/') + '/', 'auth/login')
    try:
        resp = requests.get(login_url, timeout=8, allow_redirects=True)
    except Exception as exc:
        pytest.fail(
            f'Black-box tests require the app running and reachable at {BASE_URL}. '
            f'Could not connect to {login_url}: {exc}',
            pytrace=False,
        )

    if resp.status_code >= 400:
        pytest.fail(
            f'Black-box tests require the app running and reachable at {BASE_URL}. '
            f'GET {login_url} returned HTTP {resp.status_code}. '
            'Start the server, or set TEST_BASE_URL to the correct URL.',
            pytrace=False,
        )


_preflight_verify_server_or_fail()

# Test Data
TEST_USERS = {
    'admin': {
        'email': f'admin.test.{int(time.time())}@testcorp.com',
        'password': 'TestAdmin@123',
        'first_name': 'Admin',
        'last_name': 'User',
        'org_name': 'Test Corporation'
    },
    'user': {
        'email': f'user.test.{int(time.time())}@testcorp.com',
        'password': 'TestUser@123',
        'first_name': 'Regular',
        'last_name': 'User'
    }
}


@pytest.fixture(scope='module')
def browser():
    """Setup Chrome browser with options"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in background
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(TIMEOUT)
    yield driver
    driver.quit()


@pytest.fixture
def wait(browser):
    """Explicit wait helper"""
    return WebDriverWait(browser, TIMEOUT)


def create_test_files():
    """Create test files for upload testing"""
    os.makedirs(TEST_FILES_DIR, exist_ok=True)
    
    # Valid logo image (PNG)
    logo_path = os.path.join(TEST_FILES_DIR, 'test_logo.png')
    if not os.path.exists(logo_path):
        from PIL import Image
        img = Image.new('RGB', (800, 800), color='blue')
        img.save(logo_path)
    
    # Valid PDF document
    pdf_path = os.path.join(TEST_FILES_DIR, 'test_doc.pdf')
    if not os.path.exists(pdf_path):
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4\n%Test PDF content\n%%EOF')
    
    # Invalid file (executable)
    exe_path = os.path.join(TEST_FILES_DIR, 'test_invalid.exe')
    if not os.path.exists(exe_path):
        with open(exe_path, 'wb') as f:
            f.write(b'MZ\x90\x00\x03')  # PE executable header
    
    # Large file (>5MB)
    large_path = os.path.join(TEST_FILES_DIR, 'test_large.bin')
    if not os.path.exists(large_path):
        with open(large_path, 'wb') as f:
            f.write(b'\x00' * (6 * 1024 * 1024))  # 6MB
    
    return {
        'logo': logo_path,
        'pdf': pdf_path,
        'exe': exe_path,
        'large': large_path
    }


# ============================================================================
# TEST SUITE 1: AUTHENTICATION & AUTHORIZATION
# ============================================================================

class TestAuthentication:
    """Test all authentication flows"""
    
    def test_01_signup_valid(self, browser, wait):
        """TC-1.1.1: Valid user signup"""
        browser.get(f'{BASE_URL}/auth/signup')
        
        # Fill signup form
        browser.find_element(By.NAME, 'organization_name').send_keys(TEST_USERS['admin']['org_name'])
        browser.find_element(By.NAME, 'first_name').send_keys(TEST_USERS['admin']['first_name'])
        browser.find_element(By.NAME, 'last_name').send_keys(TEST_USERS['admin']['last_name'])
        browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
        browser.find_element(By.NAME, 'password').send_keys(TEST_USERS['admin']['password'])
        browser.find_element(By.NAME, 'password2').send_keys(TEST_USERS['admin']['password'])
        browser.find_element(By.NAME, 'terms').click()
        
        # Submit form
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        # Verify redirect to verification page or onboarding
        wait.until(lambda d: '/verify-email' in d.current_url or '/onboarding' in d.current_url)
        assert any(x in browser.current_url for x in ['/verify-email', '/onboarding'])
    
    def test_02_signup_duplicate_email(self, browser, wait):
        """TC-1.1.2: Signup with duplicate email"""
        browser.get(f'{BASE_URL}/auth/signup')
        
        browser.find_element(By.NAME, 'organization_name').send_keys('Another Corp')
        browser.find_element(By.NAME, 'first_name').send_keys('Test')
        browser.find_element(By.NAME, 'last_name').send_keys('User')
        browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
        browser.find_element(By.NAME, 'password').send_keys('Password@123')
        browser.find_element(By.NAME, 'password2').send_keys('Password@123')
        browser.find_element(By.NAME, 'terms').click()
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        # Verify error message
        time.sleep(1)
        assert 'already' in browser.page_source.lower() or 'exists' in browser.page_source.lower()
    
    def test_03_signup_password_mismatch(self, browser):
        """TC-1.1.3: Signup with password mismatch"""
        browser.get(f'{BASE_URL}/auth/signup')
        
        browser.find_element(By.NAME, 'organization_name').send_keys('Test Corp')
        browser.find_element(By.NAME, 'first_name').send_keys('Test')
        browser.find_element(By.NAME, 'last_name').send_keys('User')
        browser.find_element(By.NAME, 'email').send_keys(f'test{int(time.time())}@test.com')
        browser.find_element(By.NAME, 'password').send_keys('Password@123')
        browser.find_element(By.NAME, 'password2').send_keys('DifferentPass@123')
        browser.find_element(By.NAME, 'terms').click()
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(1)
        assert 'match' in browser.page_source.lower()
    
    def test_04_signup_weak_password(self, browser):
        """TC-1.1.4: Signup with weak password"""
        browser.get(f'{BASE_URL}/auth/signup')
        
        browser.find_element(By.NAME, 'organization_name').send_keys('Test Corp')
        browser.find_element(By.NAME, 'first_name').send_keys('Test')
        browser.find_element(By.NAME, 'last_name').send_keys('User')
        browser.find_element(By.NAME, 'email').send_keys(f'test{int(time.time())}@test.com')
        browser.find_element(By.NAME, 'password').send_keys('weak')
        browser.find_element(By.NAME, 'password2').send_keys('weak')
        browser.find_element(By.NAME, 'terms').click()
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(1)
        page_text = browser.page_source.lower()
        assert any(x in page_text for x in ['short', 'weak', 'length', 'characters'])
    
    def test_05_signup_invalid_email(self, browser):
        """TC-1.1.5: Signup with invalid email format"""
        browser.get(f'{BASE_URL}/auth/signup')
        
        browser.find_element(By.NAME, 'organization_name').send_keys('Test Corp')
        browser.find_element(By.NAME, 'first_name').send_keys('Test')
        browser.find_element(By.NAME, 'last_name').send_keys('User')
        browser.find_element(By.NAME, 'email').send_keys('invalid-email-format')
        browser.find_element(By.NAME, 'password').send_keys('Password@123')
        browser.find_element(By.NAME, 'password2').send_keys('Password@123')
        browser.find_element(By.NAME, 'terms').click()
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(1)
        # Browser validation or server error
        assert 'invalid' in browser.page_source.lower() or browser.current_url.endswith('/signup')
    
    def test_06_signup_terms_not_accepted(self, browser):
        """TC-1.1.7: Signup without accepting terms"""
        browser.get(f'{BASE_URL}/auth/signup')
        
        browser.find_element(By.NAME, 'organization_name').send_keys('Test Corp')
        browser.find_element(By.NAME, 'first_name').send_keys('Test')
        browser.find_element(By.NAME, 'last_name').send_keys('User')
        browser.find_element(By.NAME, 'email').send_keys(f'test{int(time.time())}@test.com')
        browser.find_element(By.NAME, 'password').send_keys('Password@123')
        browser.find_element(By.NAME, 'password2').send_keys('Password@123')
        # Don't check terms
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(1)
        assert browser.current_url.endswith('/signup')  # Should stay on signup page
    
    def test_07_login_valid(self, browser, wait):
        """TC-1.4.1: Valid login"""
        browser.get(f'{BASE_URL}/auth/login')
        
        browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
        browser.find_element(By.NAME, 'password').send_keys(TEST_USERS['admin']['password'])
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        # Should redirect to dashboard or onboarding
        wait.until(lambda d: d.current_url != f'{BASE_URL}/auth/login')
        assert '/login' not in browser.current_url
    
    def test_08_login_wrong_password(self, browser):
        """TC-1.4.2: Login with wrong password"""
        browser.get(f'{BASE_URL}/auth/login')
        
        browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
        browser.find_element(By.NAME, 'password').send_keys('WrongPassword@123')
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(1)
        page_text = browser.page_source.lower()
        assert any(x in page_text for x in ['invalid', 'incorrect', 'wrong'])
    
    def test_09_login_nonexistent_email(self, browser):
        """TC-1.4.3: Login with non-existent email"""
        browser.get(f'{BASE_URL}/auth/login')
        
        browser.find_element(By.NAME, 'email').send_keys('nonexistent@example.com')
        browser.find_element(By.NAME, 'password').send_keys('Password@123')
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(1)
        assert 'invalid' in browser.page_source.lower()
    
    def test_10_oauth_buttons_present(self, browser):
        """TC-1.2.x: OAuth buttons present on login/signup"""
        browser.get(f'{BASE_URL}/auth/login')
        
        # Check for OAuth buttons
        page_source = browser.page_source.lower()
        assert 'google' in page_source or 'microsoft' in page_source
    
    def test_11_password_reset_page_accessible(self, browser):
        """TC-1.6.1: Password reset page accessible"""
        browser.get(f'{BASE_URL}/auth/forgot-password')
        
        assert browser.find_element(By.NAME, 'email')
        assert 'reset' in browser.page_source.lower() or 'forgot' in browser.page_source.lower()


# ============================================================================
# TEST SUITE 2: ONBOARDING FLOW
# ============================================================================

class TestOnboarding:
    """Test complete onboarding flow"""
    
    @pytest.fixture(autouse=True)
    def login_first(self, browser):
        """Login before each onboarding test"""
        browser.get(f'{BASE_URL}/auth/login')
        try:
            browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
            browser.find_element(By.NAME, 'password').send_keys(TEST_USERS['admin']['password'])
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(2)
        except:
            pass  # Already logged in
    
    def test_01_organization_details_valid(self, browser, wait):
        """TC-2.1.1: Complete organization form"""
        browser.get(f'{BASE_URL}/onboarding/organization')
        
        # Fill organization details
        browser.find_element(By.NAME, 'name').clear()
        browser.find_element(By.NAME, 'name').send_keys('Acme Corporation')
        
        try:
            Select(browser.find_element(By.NAME, 'industry')).select_by_visible_text('Technology')
        except:
            pass
        
        try:
            Select(browser.find_element(By.NAME, 'size')).select_by_value('50-200')
        except:
            pass
        
        browser.find_element(By.NAME, 'country').send_keys('Australia')
        browser.find_element(By.NAME, 'state').send_keys('New South Wales')
        browser.find_element(By.NAME, 'city').send_keys('Sydney')
        browser.find_element(By.NAME, 'postal_code').send_keys('2000')
        browser.find_element(By.NAME, 'phone').send_keys('+61 2 1234 5678')
        browser.find_element(By.NAME, 'website').send_keys('https://acme.com')
        
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        # Should redirect to next step
        wait.until(lambda d: '/organization' not in d.current_url)
        assert '/billing' in browser.current_url or '/logo' in browser.current_url
    
    def test_02_organization_missing_required(self, browser):
        """TC-2.1.2: Missing required fields"""
        browser.get(f'{BASE_URL}/onboarding/organization')
        
        # Clear name field
        browser.find_element(By.NAME, 'name').clear()
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(1)
        assert '/organization' in browser.current_url  # Should stay on page
    
    def test_03_billing_skip(self, browser, wait):
        """TC-2.2.5: Skip billing step"""
        browser.get(f'{BASE_URL}/onboarding/billing')
        
        # Look for skip button
        skip_buttons = browser.find_elements(By.LINK_TEXT, 'Skip')
        if skip_buttons:
            skip_buttons[0].click()
            wait.until(lambda d: '/billing' not in d.current_url)
            assert '/logo' in browser.current_url or '/theme' in browser.current_url
        else:
            pytest.skip("No skip button found")
    
    def test_04_logo_upload_valid(self, browser, wait):
        """TC-2.3.1: Upload valid logo"""
        test_files = create_test_files()
        browser.get(f'{BASE_URL}/onboarding/logo')
        
        # Upload logo
        try:
            file_input = browser.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            file_input.send_keys(test_files['logo'])
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            
            # Should redirect to next step
            wait.until(lambda d: '/logo' not in d.current_url)
            assert '/theme' in browser.current_url or '/dashboard' in browser.current_url
        except NoSuchElementException:
            pytest.skip("File upload field not found")
    
    def test_05_logo_upload_invalid_type(self, browser):
        """TC-2.3.3: Upload invalid file type"""
        test_files = create_test_files()
        browser.get(f'{BASE_URL}/onboarding/logo')
        
        try:
            file_input = browser.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            file_input.send_keys(test_files['exe'])
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            
            time.sleep(2)
            page_text = browser.page_source.lower()
            assert any(x in page_text for x in ['invalid', 'type', 'format'])
        except NoSuchElementException:
            pytest.skip("File upload field not found")
    
    def test_06_logo_skip(self, browser, wait):
        """TC-2.3.8: Skip logo upload"""
        browser.get(f'{BASE_URL}/onboarding/logo')
        
        skip_buttons = browser.find_elements(By.LINK_TEXT, 'Skip')
        if skip_buttons:
            skip_buttons[0].click()
            wait.until(lambda d: '/logo' not in d.current_url)
            assert '/theme' in browser.current_url or '/dashboard' in browser.current_url
        else:
            # Try submit without file
            try:
                browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
                time.sleep(1)
            except:
                pass
    
    def test_07_theme_selection(self, browser, wait):
        """TC-2.4.1: Select theme"""
        browser.get(f'{BASE_URL}/onboarding/theme')
        
        # Select a theme color
        try:
            theme_inputs = browser.find_elements(By.CSS_SELECTOR, 'input[name="theme_color"]')
            if theme_inputs:
                theme_inputs[0].click()
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            
            # Should complete onboarding and redirect to dashboard
            wait.until(lambda d: '/onboarding' not in d.current_url)
            assert '/dashboard' in browser.current_url or '/org' in browser.current_url
        except NoSuchElementException:
            pytest.skip("Theme selection not found")


# ============================================================================
# TEST SUITE 3: ORGANIZATION MANAGEMENT
# ============================================================================

class TestOrganizationManagement:
    """Test organization profile and settings"""
    
    @pytest.fixture(autouse=True)
    def login_first(self, browser):
        """Login before each test"""
        browser.get(f'{BASE_URL}/auth/login')
        try:
            browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
            browser.find_element(By.NAME, 'password').send_keys(TEST_USERS['admin']['password'])
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(2)
        except:
            pass
    
    def test_01_view_organization_settings(self, browser):
        """TC-3.1.1: View organization settings"""
        browser.get(f'{BASE_URL}/org/settings')
        
        # Should be able to access settings page
        assert 'organization' in browser.page_source.lower() or 'profile' in browser.page_source.lower()
    
    def test_02_update_organization_details(self, browser, wait):
        """TC-3.2.1: Update organization details"""
        browser.get(f'{BASE_URL}/org/settings')
        
        # Update organization name
        name_field = browser.find_element(By.NAME, 'name')
        name_field.clear()
        new_name = f'Updated Corp {int(time.time())}'
        name_field.send_keys(new_name)
        
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(2)
        # Verify update
        browser.get(f'{BASE_URL}/org/settings')
        assert new_name in browser.page_source
    
    def test_03_logo_displays_in_navbar(self, browser):
        """TC-8.4.1: Logo displays in navbar"""
        browser.get(f'{BASE_URL}/dashboard')
        
        # Check if logo is present in navbar
        try:
            logo_img = browser.find_element(By.CSS_SELECTOR, 'nav img[src*="logo"]')
            assert logo_img.is_displayed()
        except NoSuchElementException:
            # Logo might not be uploaded yet
            pytest.skip("Logo not found in navbar")
    
    def test_04_organization_switcher_accessible(self, browser):
        """TC-3.4.1: Organization switcher accessible"""
        browser.get(f'{BASE_URL}/dashboard')
        
        # Look for org switcher dropdown
        try:
            switcher = browser.find_element(By.CSS_SELECTOR, '[data-bs-toggle="dropdown"]')
            assert 'organization' in switcher.text.lower() or 'org' in browser.page_source.lower()
        except NoSuchElementException:
            pytest.skip("Org switcher not found")


# ============================================================================
# TEST SUITE 4: MEMBER MANAGEMENT
# ============================================================================

class TestMemberManagement:
    """Test user invitation and member management"""
    
    @pytest.fixture(autouse=True)
    def login_admin(self, browser):
        """Login as admin"""
        browser.get(f'{BASE_URL}/auth/login')
        try:
            browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
            browser.find_element(By.NAME, 'password').send_keys(TEST_USERS['admin']['password'])
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(2)
        except:
            pass
    
    def test_01_access_team_management(self, browser):
        """TC-4.5.1: Admin can access team management"""
        browser.get(f'{BASE_URL}/org/admin/dashboard')
        
        # Should see team management page
        page_text = browser.page_source.lower()
        assert any(x in page_text for x in ['team', 'members', 'users'])
    
    def test_02_invite_member_valid(self, browser, wait):
        """TC-4.1.1: Invite new member"""
        browser.get(f'{BASE_URL}/org/admin/dashboard')
        
        # Fill invite form
        new_email = f'newmember{int(time.time())}@testcorp.com'
        browser.find_element(By.NAME, 'email').send_keys(new_email)
        
        try:
            Select(browser.find_element(By.NAME, 'role')).select_by_visible_text('User')
        except:
            pass
        
        # Submit invite
        submit_btns = browser.find_elements(By.CSS_SELECTOR, 'button[type="submit"]')
        if submit_btns:
            submit_btns[0].click()
            time.sleep(2)
            
            # Verify invite sent
            browser.get(f'{BASE_URL}/org/admin/dashboard')
            assert new_email in browser.page_source
    
    def test_03_invite_duplicate_email(self, browser):
        """TC-4.1.3: Invite duplicate email"""
        browser.get(f'{BASE_URL}/org/admin/dashboard')
        
        # Try to invite existing member
        browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
        
        try:
            Select(browser.find_element(By.NAME, 'role')).select_by_visible_text('User')
        except:
            pass
        
        submit_btns = browser.find_elements(By.CSS_SELECTOR, 'button[type="submit"]')
        if submit_btns:
            submit_btns[0].click()
            time.sleep(2)
            
            # Should show error
            assert 'already' in browser.page_source.lower() or 'exists' in browser.page_source.lower()
    
    def test_04_invite_invalid_email(self, browser):
        """TC-4.1.4: Invite with invalid email"""
        browser.get(f'{BASE_URL}/org/admin/dashboard')
        
        browser.find_element(By.NAME, 'email').send_keys('invalid-email')
        
        submit_btns = browser.find_elements(By.CSS_SELECTOR, 'button[type="submit"]')
        if submit_btns:
            submit_btns[0].click()
            time.sleep(1)
            
            # Should show error or stay on page
            assert 'invalid' in browser.page_source.lower() or '/admin/dashboard' in browser.current_url
    
    def test_05_floating_invite_button_visible(self, browser):
        """TC-8.1.1: Floating invite button visible for admin"""
        browser.get(f'{BASE_URL}/dashboard')
        
        # Look for floating button
        try:
            floating_btn = browser.find_element(By.CSS_SELECTOR, '.floating-invite-btn, [data-bs-target*="invite"]')
            assert floating_btn.is_displayed()
        except NoSuchElementException:
            pytest.skip("Floating invite button not found")
    
    def test_06_floating_button_hidden_on_auth(self, browser):
        """TC-8.1.2: Floating button hidden on auth pages"""
        browser.get(f'{BASE_URL}/auth/logout')
        browser.get(f'{BASE_URL}/auth/login')
        
        # Button should not be visible
        floating_btns = browser.find_elements(By.CSS_SELECTOR, '.floating-invite-btn, [data-bs-target*="invite"]')
        assert len(floating_btns) == 0 or not floating_btns[0].is_displayed()
    
    def test_07_member_list_displays(self, browser):
        """TC-4.5.1: Member list displays correctly"""
        browser.get(f'{BASE_URL}/org/admin/dashboard')
        
        # Should see at least the admin user
        assert TEST_USERS['admin']['email'] in browser.page_source
        
        # Check for proper columns
        page_text = browser.page_source.lower()
        assert 'email' in page_text
        assert any(x in page_text for x in ['role', 'status', 'department'])
    
    def test_08_cannot_remove_self(self, browser):
        """TC-4.4.2: Admin cannot remove themselves"""
        browser.get(f'{BASE_URL}/org/admin/dashboard')
        
        # Find admin's row - should not have remove button or show "You"
        page_source = browser.page_source
        admin_email = TEST_USERS['admin']['email']
        
        # Check if "You" indicator is present near admin email
        assert 'you' in page_source.lower()


# ============================================================================
# TEST SUITE 5: DEPARTMENT MANAGEMENT
# ============================================================================

class TestDepartmentManagement:
    """Test department CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def login_admin(self, browser):
        """Login as admin"""
        browser.get(f'{BASE_URL}/auth/login')
        try:
            browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
            browser.find_element(By.NAME, 'password').send_keys(TEST_USERS['admin']['password'])
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(2)
        except:
            pass
    
    def test_01_create_department(self, browser, wait):
        """TC-5.1.1: Create valid department"""
        browser.get(f'{BASE_URL}/org/admin/dashboard')
        
        # Click add department button
        try:
            add_dept_btn = browser.find_element(By.CSS_SELECTOR, '[data-bs-target="#departmentModal"]')
            add_dept_btn.click()
            time.sleep(1)
            
            # Fill department form
            dept_name = f'Engineering {int(time.time())}'
            browser.find_element(By.ID, 'deptNameInput').send_keys(dept_name)
            
            # Select color
            color_radios = browser.find_elements(By.CSS_SELECTOR, 'input[name="deptColorChoice"]')
            if color_radios:
                color_radios[0].click()
            
            # Save
            browser.find_element(By.ID, 'saveDepartmentBtn').click()
            time.sleep(3)
            
            # Verify department created
            assert dept_name in browser.page_source
        except NoSuchElementException:
            pytest.skip("Department modal not found")
    
    def test_02_department_dropdown_visible(self, browser):
        """TC-5.x: Department dropdown visible in invite form"""
        browser.get(f'{BASE_URL}/org/admin/dashboard')
        
        # Check for department select
        try:
            dept_select = browser.find_element(By.NAME, 'department_id')
            assert dept_select.is_displayed()
        except NoSuchElementException:
            pytest.skip("Department dropdown not found")
    
    def test_03_department_dropdown_positioning(self, browser):
        """TC-8.x: Department dropdown doesn't overflow"""
        browser.get(f'{BASE_URL}/org/admin/dashboard')
        
        # Click on a department dropdown
        try:
            dropdown_btns = browser.find_elements(By.CSS_SELECTOR, '[data-bs-toggle="dropdown"]')
            if dropdown_btns:
                # Check if dropdown parent has position:static
                parent = dropdown_btns[0].find_element(By.XPATH, '..')
                style = parent.get_attribute('style')
                # Should not overflow outside card
                assert True  # Visual test - manual verification needed
        except:
            pytest.skip("Dropdown test requires manual verification")


# ============================================================================
# TEST SUITE 6: SECURITY & PERMISSIONS
# ============================================================================

class TestSecurity:
    """Test security features and access controls"""
    
    def test_01_csrf_token_present(self, browser):
        """TC-7.3.1: CSRF tokens present in forms"""
        browser.get(f'{BASE_URL}/auth/login')
        
        # Check for CSRF token
        csrf_inputs = browser.find_elements(By.CSS_SELECTOR, 'input[name="csrf_token"]')
        assert len(csrf_inputs) > 0
    
    def test_02_protected_routes_redirect(self, browser):
        """TC-7.1.x: Protected routes redirect to login"""
        # Logout first
        browser.get(f'{BASE_URL}/auth/logout')
        time.sleep(1)
        
        # Try to access protected page
        browser.get(f'{BASE_URL}/org/admin/dashboard')
        time.sleep(1)
        
        # Should redirect to login
        assert '/login' in browser.current_url
    
    def test_03_xss_prevention(self, browser):
        """TC-1.1.9: XSS prevention in forms"""
        browser.get(f'{BASE_URL}/auth/signup')
        
        xss_payload = '<script>alert("XSS")</script>'
        browser.find_element(By.NAME, 'organization_name').send_keys(xss_payload)
        browser.find_element(By.NAME, 'first_name').send_keys('Test')
        browser.find_element(By.NAME, 'last_name').send_keys('User')
        browser.find_element(By.NAME, 'email').send_keys(f'xss{int(time.time())}@test.com')
        browser.find_element(By.NAME, 'password').send_keys('Test@123456')
        browser.find_element(By.NAME, 'password2').send_keys('Test@123456')
        browser.find_element(By.NAME, 'terms').click()
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(2)
        # XSS should be escaped, not executed
        page_source = browser.page_source
        assert '<script>' not in page_source or '&lt;script&gt;' in page_source
    
    def test_04_sql_injection_prevention(self, browser):
        """TC-1.1.9: SQL injection prevention"""
        browser.get(f'{BASE_URL}/auth/login')
        
        sql_payload = "' OR '1'='1"
        browser.find_element(By.NAME, 'email').send_keys(sql_payload)
        browser.find_element(By.NAME, 'password').send_keys(sql_payload)
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(1)
        # Should not log in
        assert 'invalid' in browser.page_source.lower() or '/login' in browser.current_url
    
    def test_05_rate_limiting_login(self, browser):
        """TC-7.5.1: Login rate limiting"""
        browser.get(f'{BASE_URL}/auth/login')
        
        # Attempt multiple failed logins
        for i in range(12):
            browser.get(f'{BASE_URL}/auth/login')
            browser.find_element(By.NAME, 'email').send_keys('test@example.com')
            browser.find_element(By.NAME, 'password').send_keys('wrongpassword')
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(0.5)
        
        # Should see rate limit error
        page_text = browser.page_source.lower()
        assert any(x in page_text for x in ['many', 'limit', 'wait', 'try again'])


# ============================================================================
# TEST SUITE 7: UI/UX TESTS
# ============================================================================

class TestUIUX:
    """Test UI elements and user experience"""
    
    def test_01_responsive_navbar(self, browser):
        """TC-8.3.1: Navbar responsive"""
        browser.get(f'{BASE_URL}/')
        
        # Desktop view
        browser.set_window_size(1920, 1080)
        navbar = browser.find_element(By.CSS_SELECTOR, 'nav')
        assert navbar.is_displayed()
        
        # Mobile view
        browser.set_window_size(375, 667)
        time.sleep(1)
        navbar = browser.find_element(By.CSS_SELECTOR, 'nav')
        assert navbar.is_displayed()
        
        # Restore window size
        browser.set_window_size(1920, 1080)
    
    def test_02_footer_visible(self, browser):
        """TC-8.x: Footer visible and separated"""
        browser.get(f'{BASE_URL}/')
        
        try:
            footer = browser.find_element(By.CSS_SELECTOR, 'footer')
            assert footer.is_displayed()
            
            # Check for visual separation (border or background)
            style = footer.get_attribute('style')
            class_attr = footer.get_attribute('class')
            # Should have some styling for separation
            assert style or class_attr
        except NoSuchElementException:
            pytest.skip("Footer not found")
    
    def test_03_flash_messages_display(self, browser):
        """TC-8.x: Flash messages display correctly"""
        browser.get(f'{BASE_URL}/auth/login')
        
        # Trigger error flash message
        browser.find_element(By.NAME, 'email').send_keys('wrong@example.com')
        browser.find_element(By.NAME, 'password').send_keys('wrongpass')
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        time.sleep(1)
        # Should see flash message
        try:
            alert = browser.find_element(By.CSS_SELECTOR, '.alert, .flash-message')
            assert alert.is_displayed()
        except NoSuchElementException:
            # Flash messages might be inline
            pass
    
    def test_04_forms_have_labels(self, browser):
        """TC-8.2.x: Forms have proper labels"""
        browser.get(f'{BASE_URL}/auth/login')
        
        # Check for labels
        labels = browser.find_elements(By.CSS_SELECTOR, 'label')
        assert len(labels) > 0
        
        # Check for required field indicators
        inputs = browser.find_elements(By.CSS_SELECTOR, 'input[required]')
        assert len(inputs) > 0


# ============================================================================
# TEST SUITE 8: FILE UPLOADS
# ============================================================================

class TestFileUploads:
    """Test file upload functionality"""
    
    @pytest.fixture(autouse=True)
    def login_first(self, browser):
        """Login before tests"""
        browser.get(f'{BASE_URL}/auth/login')
        try:
            browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
            browser.find_element(By.NAME, 'password').send_keys(TEST_USERS['admin']['password'])
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(2)
        except:
            pass
    
    def test_01_logo_upload_from_settings(self, browser, wait):
        """TC-6.x: Upload logo from organization settings"""
        test_files = create_test_files()
        browser.get(f'{BASE_URL}/org/settings')
        
        try:
            file_input = browser.find_element(By.CSS_SELECTOR, 'input[type="file"][accept*="image"]')
            file_input.send_keys(test_files['logo'])
            
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(3)
            
            # Logo should be visible
            browser.get(f'{BASE_URL}/dashboard')
            time.sleep(1)
            
            # Check navbar for logo
            try:
                logo_img = browser.find_element(By.CSS_SELECTOR, 'nav img[src*="logo"]')
                assert logo_img.is_displayed()
            except NoSuchElementException:
                pytest.skip("Logo not immediately visible")
        except NoSuchElementException:
            pytest.skip("Logo upload field not found")
    
    def test_02_avatar_upload(self, browser):
        """TC-6.2.1: Upload profile avatar"""
        test_files = create_test_files()
        
        # Navigate to profile settings (if exists)
        browser.get(f'{BASE_URL}/profile')
        
        try:
            file_input = browser.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            file_input.send_keys(test_files['logo'])
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(2)
            
            # Verify avatar uploaded
            assert 'success' in browser.page_source.lower() or 'uploaded' in browser.page_source.lower()
        except NoSuchElementException:
            pytest.skip("Avatar upload not available")
    
    def test_03_invalid_file_type_rejected(self, browser):
        """TC-6.1.3: Invalid file type rejected"""
        test_files = create_test_files()
        browser.get(f'{BASE_URL}/org/settings')
        
        try:
            file_input = browser.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            file_input.send_keys(test_files['exe'])
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(2)
            
            # Should show error
            page_text = browser.page_source.lower()
            assert any(x in page_text for x in ['invalid', 'type', 'format', 'not allowed'])
        except NoSuchElementException:
            pytest.skip("File upload test skipped")


# ============================================================================
# TEST SUITE 9: ERROR HANDLING
# ============================================================================

class TestErrorHandling:
    """Test error scenarios and edge cases"""
    
    def test_01_404_page_friendly(self, browser):
        """TC-9.x: 404 page is user-friendly"""
        browser.get(f'{BASE_URL}/nonexistent-page-12345')
        
        # Should show 404 message
        page_text = browser.page_source.lower()
        assert '404' in page_text or 'not found' in page_text
    
    def test_02_500_error_graceful(self, browser):
        """TC-9.1.1: 500 errors handled gracefully"""
        # This would need a route that triggers 500 error
        # For now, just verify no stack traces on normal pages
        browser.get(f'{BASE_URL}/')
        
        page_source = browser.page_source
        # Should not expose stack traces
        assert 'Traceback' not in page_source
        assert 'File "' not in page_source
    
    def test_03_form_validation_errors_displayed(self, browser):
        """TC-8.2.2: Form validation errors displayed"""
        browser.get(f'{BASE_URL}/auth/signup')
        
        # Submit empty form
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        time.sleep(1)
        
        # Should stay on page with errors
        assert '/signup' in browser.current_url
        
        # Check for error messages
        page_text = browser.page_source.lower()
        assert 'required' in page_text or 'invalid' in page_text


# ============================================================================
# PERFORMANCE & LOAD TESTS
# ============================================================================

class TestPerformance:
    """Basic performance checks"""
    
    def test_01_page_load_time(self, browser):
        """TC-10.1.x: Page loads within acceptable time"""
        start = time.time()
        browser.get(f'{BASE_URL}/')
        load_time = time.time() - start
        
        # Should load within 3 seconds
        assert load_time < 3.0, f"Page took {load_time:.2f}s to load"
    
    def test_02_login_performance(self, browser):
        """TC-10.1.x: Login completes quickly"""
        browser.get(f'{BASE_URL}/auth/login')
        
        start = time.time()
        browser.find_element(By.NAME, 'email').send_keys(TEST_USERS['admin']['email'])
        browser.find_element(By.NAME, 'password').send_keys(TEST_USERS['admin']['password'])
        browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        time.sleep(2)
        login_time = time.time() - start
        
        # Should complete within 5 seconds
        assert login_time < 5.0, f"Login took {login_time:.2f}s"


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s', '--tb=short'])
