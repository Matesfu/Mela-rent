from django.test import TestCase
from django.db import connection
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


# ---------------------------------------------------------------------------
# 1. Database Connection Tests (from previous task — kept for regression)
# ---------------------------------------------------------------------------

class DatabaseConnectionTest(TestCase):
    """Verify that Django can connect to the PostgreSQL database."""

    def test_database_engine_is_postgresql(self):
        engine = connection.settings_dict['ENGINE']
        self.assertIn('postgresql', engine)

    def test_database_connection_is_usable(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
        self.assertEqual(result[0], 1)

    def test_database_name(self):
        db_name = connection.settings_dict['NAME']
        self.assertTrue(db_name.endswith('mela_rent_db'))


# ---------------------------------------------------------------------------
# 2. User Registration Tests
# ---------------------------------------------------------------------------

class UserRegistrationTest(TestCase):
    """Test the POST /api/auth/register/ endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.register_url = '/api/auth/register/'
        self.valid_data = {
            'username': 'testowner',
            'email': 'owner@example.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'role': 'OWNER',
        }

    # --- Success Cases ---

    def test_register_ignores_submitted_role(self):
        """Register submitting OWNER role - expect TENANT (auto-default, read-only)."""
        response = self.client.post(self.register_url, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['username'], 'testowner')
        self.assertEqual(response.data['email'], 'owner@example.com')
        self.assertEqual(response.data['role'], 'TENANT')
        self.assertIn('id', response.data)
        self.assertIn('message', response.data)

    def test_register_tenant_success(self):
        """Register a new TENANT user — expect 201."""
        data = self.valid_data.copy()
        data.update({
            'username': 'testtenant',
            'email': 'tenant@example.com',
            'role': 'TENANT',
        })
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'TENANT')

    def test_register_default_role_is_tenant(self):
        """When role is omitted, it should default to TENANT."""
        data = self.valid_data.copy()
        data.pop('role')
        data['username'] = 'defaultrole'
        data['email'] = 'default@example.com'
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'TENANT')

    def test_password_is_hashed(self):
        """The stored password must not be plain text."""
        self.client.post(self.register_url, self.valid_data)
        user = User.objects.get(username='testowner')
        self.assertNotEqual(user.password, 'StrongPass123!')
        self.assertTrue(user.check_password('StrongPass123!'))

    # --- Failure Cases ---

    def test_register_duplicate_username(self):
        """Duplicate username should return 400."""
        self.client.post(self.register_url, self.valid_data)
        dup_data = self.valid_data.copy()
        dup_data['email'] = 'other@example.com'
        response = self.client.post(self.register_url, dup_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email(self):
        """Duplicate email should return 400."""
        self.client.post(self.register_url, self.valid_data)
        dup_data = self.valid_data.copy()
        dup_data['username'] = 'anotheruser'
        response = self.client.post(self.register_url, dup_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_mismatch(self):
        """Mismatched passwords should return 400."""
        data = self.valid_data.copy()
        data['password2'] = 'WrongPassword!'
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password(self):
        """A weak password (too short / too common) should return 400."""
        data = self.valid_data.copy()
        data['password'] = '123'
        data['password2'] = '123'
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_email(self):
        """Missing email should return 400."""
        data = self.valid_data.copy()
        data.pop('email')
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_username(self):
        """Missing username should return 400."""
        data = self.valid_data.copy()
        data.pop('username')
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 3. Login / Token Generation Tests
# ---------------------------------------------------------------------------

class TokenAuthenticationTest(TestCase):
    """Test the POST /api/auth/token/ endpoint (SimpleJWT)."""

    def setUp(self):
        self.client = APIClient()
        self.token_url = '/api/auth/token/'
        self.refresh_url = '/api/auth/token/refresh/'
        self.user = User.objects.create_user(
            username='loginuser',
            email='login@example.com',
            password='SecurePass456!',
            role='TENANT',
        )

    # --- Success Cases ---

    def test_obtain_token_with_valid_credentials(self):
        """Valid username+password should return access and refresh tokens."""
        response = self.client.post(self.token_url, {
            'username': 'loginuser',
            'password': 'SecurePass456!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_refresh_token(self):
        """A valid refresh token should return a new access token."""
        token_response = self.client.post(self.token_url, {
            'username': 'loginuser',
            'password': 'SecurePass456!',
        })
        refresh = token_response.data['refresh']
        response = self.client.post(self.refresh_url, {'refresh': refresh})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    # --- Failure Cases ---

    def test_obtain_token_with_wrong_password(self):
        """Wrong password should return 401."""
        response = self.client.post(self.token_url, {
            'username': 'loginuser',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_obtain_token_with_nonexistent_user(self):
        """Non-existent username should return 401."""
        response = self.client.post(self.token_url, {
            'username': 'nouser',
            'password': 'AnyPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_obtain_token_with_missing_fields(self):
        """Missing username or password should return 400."""
        response = self.client.post(self.token_url, {
            'username': 'loginuser',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_with_invalid_token(self):
        """An invalid refresh token should return 401."""
        response = self.client.post(self.refresh_url, {
            'refresh': 'invalid-token-string',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# 4. User Profile Tests
# ---------------------------------------------------------------------------

class UserProfileTest(TestCase):
    """Test the GET /api/users/profile/ endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.profile_url = '/api/users/profile/'
        self.token_url = '/api/auth/token/'
        self.user = User.objects.create_user(
            username='profileuser',
            email='profile@example.com',
            password='ProfilePass789!',
            role='OWNER',
        )

    def _get_access_token(self):
        """Helper to obtain an access token for the test user."""
        response = self.client.post(self.token_url, {
            'username': 'profileuser',
            'password': 'ProfilePass789!',
        })
        return response.data['access']

    # --- Success Cases ---

    def test_profile_authenticated(self):
        """Authenticated user should receive their own profile — 200."""
        token = self._get_access_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'profileuser')
        self.assertEqual(response.data['email'], 'profile@example.com')
        self.assertEqual(response.data['role'], 'OWNER')
        self.assertNotIn('password', response.data)

    def test_profile_contains_expected_fields(self):
        """Profile response should contain id, username, email, role, date_joined, last_login."""
        token = self._get_access_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(self.profile_url)
        expected_fields = {'id', 'username', 'email', 'role', 'date_joined', 'last_login'}
        self.assertEqual(set(response.data.keys()), expected_fields)

    # --- Failure Cases ---

    def test_profile_unauthenticated(self):
        """Unauthenticated request should return 401."""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_with_invalid_token(self):
        """Invalid token should return 401."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# 5. End-to-End Integration Test
# ---------------------------------------------------------------------------

class AuthIntegrationTest(TestCase):
    """Full flow: Register → Login → Access Profile."""

    def test_register_then_login_then_profile(self):
        client = APIClient()

        # Step 1: Register
        reg_response = client.post('/api/auth/register/', {
            'username': 'integrationuser',
            'email': 'integration@example.com',
            'password': 'IntegrationPass1!',
            'password2': 'IntegrationPass1!',
            'role': 'TENANT',
        })
        self.assertEqual(reg_response.status_code, status.HTTP_201_CREATED)

        # Step 2: Login
        token_response = client.post('/api/auth/token/', {
            'username': 'integrationuser',
            'password': 'IntegrationPass1!',
        })
        self.assertEqual(token_response.status_code, status.HTTP_200_OK)
        access_token = token_response.data['access']

        # Step 3: Access Profile
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_response = client.get('/api/users/profile/')
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data['username'], 'integrationuser')
        self.assertEqual(profile_response.data['role'], 'TENANT')
