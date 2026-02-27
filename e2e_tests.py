"""
Mela Rent – Comprehensive End-to-End Test Suite
================================================
This file tests the ENTIRE platform end-to-end across all three modules:
Users, Properties, and Interactions.

Coverage Map:
  1. User Registration & Authentication (8 tests)
  2. Role Auto-Upgrade Mechanics (3 tests)
  3. Property CRUD & Permissions (7 tests)
  4. Property Validation Rules (4 tests)
  5. Payment Gating & Expiry Lifecycle (5 tests)
  6. Soft Deletion Behavior (4 tests)
  7. Advanced Search, Filtering & Ordering (6 tests)
  8. Favorites / Wishlist System (7 tests)
  9. Mock Payment Processing (5 tests)
  10. Full User Journey E2E Flow (2 tests)
"""

from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test import override_settings
from datetime import timedelta

from properties.models import Property
from interactions.models import Favorite, PaymentLog

User = get_user_model()


# ===========================================================================
# 1. USER REGISTRATION & AUTHENTICATION
# ===========================================================================

class UserRegistrationE2ETest(APITestCase):
    """E2E tests for the registration and authentication endpoints."""

    def setUp(self):
        self.register_url = '/api/auth/register/'
        self.token_url = '/api/auth/token/'
        self.refresh_url = '/api/auth/token/refresh/'
        self.profile_url = '/api/users/profile/'

    def test_register_new_user_defaults_to_tenant(self):
        """All new registrations must default to TENANT role."""
        response = self.client.post(self.register_url, {
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'TENANT')

    def test_register_ignores_submitted_owner_role(self):
        """Even if 'OWNER' is submitted, the user should still get TENANT."""
        response = self.client.post(self.register_url, {
            'username': 'trickster',
            'email': 'trick@test.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'role': 'OWNER',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role'], 'TENANT')

    def test_register_duplicate_email_fails(self):
        """Duplicate email should return 400."""
        self.client.post(self.register_url, {
            'username': 'user1', 'email': 'dup@test.com',
            'password': 'StrongPass123!', 'password2': 'StrongPass123!',
        })
        response = self.client.post(self.register_url, {
            'username': 'user2', 'email': 'dup@test.com',
            'password': 'StrongPass123!', 'password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_mismatch_fails(self):
        """Mismatched passwords should return 400."""
        response = self.client.post(self.register_url, {
            'username': 'user3', 'email': 'u3@test.com',
            'password': 'StrongPass123!', 'password2': 'WrongPass456!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_valid_credentials(self):
        """Valid credentials should return access and refresh tokens."""
        User.objects.create_user(username='logintest', password='SecurePass456!')
        response = self.client.post(self.token_url, {
            'username': 'logintest', 'password': 'SecurePass456!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_with_wrong_password_fails(self):
        """Wrong password should return 401."""
        User.objects.create_user(username='wrongpw', password='RealPass!')
        response = self.client.post(self.token_url, {
            'username': 'wrongpw', 'password': 'FakePass!',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_returns_new_access(self):
        """A valid refresh token should return a new access token."""
        User.objects.create_user(username='refreshuser', password='SecurePass456!')
        token_resp = self.client.post(self.token_url, {
            'username': 'refreshuser', 'password': 'SecurePass456!',
        })
        refresh = token_resp.data['refresh']
        response = self.client.post(self.refresh_url, {'refresh': refresh})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_profile_requires_authentication(self):
        """Unauthenticated access to profile should return 401."""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ===========================================================================
# 2. ROLE AUTO-UPGRADE MECHANICS
# ===========================================================================

class RoleAutoUpgradeE2ETest(APITestCase):
    """E2E tests for the frictionless TENANT -> OWNER auto-upgrade."""

    def setUp(self):
        self.tenant = User.objects.create_user(
            username='tenant_upgrader', password='Pass123!', role='TENANT'
        )
        self.property_url = '/api/properties/'
        self.property_data = {
            'title': 'My First Listing', 'description': 'Nice place',
            'house_type': 'Apartment', 'location': 'Bole',
            'price': '3000.00', 'bedrooms': 2, 'bathrooms': 1.0,
            'max_guests': 4, 'amenities': 'WiFi',
        }

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_tenant_upgraded_to_owner_on_first_property(self):
        """A TENANT creating their first property should be auto-upgraded to OWNER."""
        self.assertEqual(self.tenant.role, 'TENANT')
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self.property_url, self.property_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.role, 'OWNER')

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_owner_stays_owner_on_subsequent_property(self):
        """An existing OWNER creating another property stays OWNER."""
        owner = User.objects.create_user(username='existing_owner', password='P!', role='OWNER')
        self.client.force_authenticate(user=owner)
        response = self.client.post(self.property_url, self.property_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        owner.refresh_from_db()
        self.assertEqual(owner.role, 'OWNER')

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_profile_reflects_upgraded_role(self):
        """After upgrade, the profile endpoint should show OWNER."""
        self.client.force_authenticate(user=self.tenant)
        self.client.post(self.property_url, self.property_data)
        response = self.client.get('/api/users/profile/')
        self.assertEqual(response.data['role'], 'OWNER')


# ===========================================================================
# 3. PROPERTY CRUD & PERMISSIONS
# ===========================================================================

class PropertyCRUDE2ETest(APITestCase):
    """E2E tests for property CRUD operations and permission enforcement."""

    def setUp(self):
        self.owner = User.objects.create_user(username='propowner', password='P!', role='OWNER')
        self.other_owner = User.objects.create_user(username='otherowner', password='P!', role='OWNER')
        self.tenant = User.objects.create_user(username='proptenant', password='P!', role='TENANT')
        self.url = '/api/properties/'
        self.valid_data = {
            'title': 'Test Prop', 'description': 'Desc',
            'house_type': 'Villa', 'location': 'Addis',
            'price': '5000.00', 'bedrooms': 3, 'bathrooms': 2.0,
            'max_guests': 6, 'amenities': 'WiFi, Pool',
        }

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_owner_can_create_property(self):
        """Authenticated OWNER can create a property."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['owner'], self.owner.id)

    def test_unauthenticated_cannot_create_property(self):
        """Unauthenticated user receives 401."""
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_public_can_list_properties(self):
        """Anonymous users can list properties."""
        Property.objects.create(owner=self.owner, **self.valid_data)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_public_can_retrieve_single_property(self):
        """Anonymous users can retrieve a single property by ID."""
        prop = Property.objects.create(owner=self.owner, **self.valid_data)
        response = self.client.get(f'{self.url}{prop.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Prop')

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_owner_can_update_own_property(self):
        """Owner can PATCH their own property."""
        prop = Property.objects.create(owner=self.owner, **self.valid_data)
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(f'{self.url}{prop.id}/', {'price': '6000.00'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prop.refresh_from_db()
        self.assertEqual(prop.price, 6000.00)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_other_owner_cannot_update_property(self):
        """Another owner should get 403 when trying to PATCH someone else's property."""
        prop = Property.objects.create(owner=self.owner, **self.valid_data)
        self.client.force_authenticate(user=self.other_owner)
        response = self.client.patch(f'{self.url}{prop.id}/', {'price': '1.00'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_tenant_cannot_update_property(self):
        """Tenant should get 403 when trying to PATCH any property."""
        prop = Property.objects.create(owner=self.owner, **self.valid_data)
        self.client.force_authenticate(user=self.tenant)
        response = self.client.patch(f'{self.url}{prop.id}/', {'price': '1.00'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ===========================================================================
# 4. PROPERTY VALIDATION RULES
# ===========================================================================

class PropertyValidationE2ETest(APITestCase):
    """E2E tests for serializer-level validation rules on Property fields."""

    def setUp(self):
        self.owner = User.objects.create_user(username='valowner', password='P!', role='OWNER')
        self.url = '/api/properties/'
        self.client.force_authenticate(user=self.owner)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_price_must_be_positive(self):
        """Price <= 0 should return 400."""
        data = {
            'title': 'Bad', 'description': 'D', 'house_type': 'Villa',
            'location': 'X', 'price': '-100', 'bedrooms': 1,
            'bathrooms': 1.0, 'max_guests': 1, 'amenities': 'None',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_bedrooms_cannot_be_negative(self):
        """Negative bedrooms should return 400."""
        data = {
            'title': 'Bad', 'description': 'D', 'house_type': 'Villa',
            'location': 'X', 'price': '100', 'bedrooms': -1,
            'bathrooms': 1.0, 'max_guests': 1, 'amenities': 'None',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_max_guests_must_be_at_least_one(self):
        """max_guests <= 0 should return 400."""
        data = {
            'title': 'Bad', 'description': 'D', 'house_type': 'Villa',
            'location': 'X', 'price': '100', 'bedrooms': 1,
            'bathrooms': 1.0, 'max_guests': 0, 'amenities': 'None',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_is_paid_and_paid_until_are_read_only(self):
        """Users cannot manually set is_paid or paid_until via POST."""
        data = {
            'title': 'Hack', 'description': 'D', 'house_type': 'Villa',
            'location': 'X', 'price': '100', 'bedrooms': 1,
            'bathrooms': 1.0, 'max_guests': 1, 'amenities': 'None',
            'is_paid': True, 'paid_until': '2030-01-01T00:00:00Z',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Even though is_paid=True was submitted, it should be False
        self.assertFalse(response.data['is_paid'])


# ===========================================================================
# 5. PAYMENT GATING & EXPIRY LIFECYCLE
# ===========================================================================

class PaymentGatingE2ETest(APITestCase):
    """E2E tests for the REQUIRE_LISTING_PAYMENT environment variable logic."""

    def setUp(self):
        self.owner = User.objects.create_user(username='payowner', password='P!', role='OWNER')
        self.url = '/api/properties/'
        self.base_data = {
            'title': 'Gated Prop', 'description': 'D', 'house_type': 'Condo',
            'location': 'Center', 'price': '8000.00', 'bedrooms': 2,
            'bathrooms': 1.0, 'max_guests': 3, 'amenities': 'Gym',
        }

    @override_settings(REQUIRE_LISTING_PAYMENT=True)
    def test_unpaid_property_hidden_from_public(self):
        """When payment gating is ON, unpaid properties are invisible to anonymous users."""
        Property.objects.create(owner=self.owner, is_paid=False, **self.base_data)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    @override_settings(REQUIRE_LISTING_PAYMENT=True)
    def test_paid_property_visible_to_public(self):
        """When payment gating is ON, paid+valid properties are visible."""
        Property.objects.create(
            owner=self.owner, is_paid=True,
            paid_until=timezone.now() + timedelta(days=30),
            **self.base_data
        )
        response = self.client.get(self.url)
        self.assertEqual(len(response.data['results']), 1)

    @override_settings(REQUIRE_LISTING_PAYMENT=True)
    def test_expired_property_hidden_from_public(self):
        """A property whose paid_until is in the past should be hidden."""
        Property.objects.create(
            owner=self.owner, is_paid=True,
            paid_until=timezone.now() - timedelta(days=1),
            **self.base_data
        )
        response = self.client.get(self.url)
        self.assertEqual(len(response.data['results']), 0)

    @override_settings(REQUIRE_LISTING_PAYMENT=True)
    def test_owner_sees_own_unpaid_property(self):
        """Owner should still see their own unpaid property when logged in."""
        Property.objects.create(owner=self.owner, is_paid=False, **self.base_data)
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url)
        self.assertEqual(len(response.data['results']), 1)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_all_properties_visible_when_gating_off(self):
        """When payment gating is OFF, all properties are visible."""
        Property.objects.create(owner=self.owner, is_paid=False, **self.base_data)
        Property.objects.create(
            owner=self.owner, title='2nd', description='D', house_type='Villa',
            location='Far', price=1000, bedrooms=1, bathrooms=1, max_guests=1,
            amenities='N', is_paid=True, paid_until=timezone.now() + timedelta(days=30)
        )
        response = self.client.get(self.url)
        self.assertEqual(len(response.data['results']), 2)


# ===========================================================================
# 6. SOFT DELETION BEHAVIOR
# ===========================================================================

class SoftDeletionE2ETest(APITestCase):
    """E2E tests for the soft deletion architecture."""

    def setUp(self):
        self.owner = User.objects.create_user(username='delowner', password='P!', role='OWNER')
        self.tenant = User.objects.create_user(username='deltenant', password='P!', role='TENANT')
        self.base_data = {
            'title': 'Delete Me', 'description': 'D', 'house_type': 'Villa',
            'location': 'Here', 'price': 1000, 'bedrooms': 1,
            'bathrooms': 1, 'max_guests': 1, 'amenities': 'N',
        }
        self.url = '/api/properties/'

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_soft_delete_sets_flags(self):
        """DELETE should set is_deleted=True and deleted_at, NOT remove from DB."""
        prop = Property.objects.create(owner=self.owner, **self.base_data)
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(f'{self.url}{prop.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        prop.refresh_from_db()
        self.assertTrue(prop.is_deleted)
        self.assertIsNotNone(prop.deleted_at)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_soft_deleted_property_hidden_from_list(self):
        """Soft-deleted properties should not appear in the list endpoint."""
        prop = Property.objects.create(owner=self.owner, **self.base_data)
        prop.delete()
        response = self.client.get(self.url)
        self.assertEqual(len(response.data['results']), 0)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_soft_deleted_property_hidden_from_detail(self):
        """Soft-deleted properties should return 404 on detail endpoint."""
        prop = Property.objects.create(owner=self.owner, **self.base_data)
        prop.delete()
        response = self.client.get(f'{self.url}{prop.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_tenant_cannot_delete_property(self):
        """A tenant should get 403 when trying to DELETE a property."""
        prop = Property.objects.create(owner=self.owner, **self.base_data)
        self.client.force_authenticate(user=self.tenant)
        response = self.client.delete(f'{self.url}{prop.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ===========================================================================
# 7. ADVANCED SEARCH, FILTERING & ORDERING
# ===========================================================================

class SearchFilterOrderE2ETest(APITestCase):
    """E2E tests for django-filter, SearchFilter, and OrderingFilter."""

    def setUp(self):
        self.owner = User.objects.create_user(username='filterowner', password='P!', role='OWNER')
        self.url = '/api/properties/'
        Property.objects.create(
            owner=self.owner, title='Cheap Studio', description='Small room near campus',
            house_type='Apartment', location='Piassa', price=2000,
            bedrooms=1, bathrooms=1, max_guests=2, amenities='WiFi',
        )
        Property.objects.create(
            owner=self.owner, title='Luxury Villa Bole', description='Premium 5-star',
            house_type='Villa', location='Bole', price=25000,
            bedrooms=5, bathrooms=3, max_guests=10, amenities='WiFi, Pool, Gym',
        )
        Property.objects.create(
            owner=self.owner, title='Mid-Range Condo', description='Family condo',
            house_type='Condo', location='Sarbet', price=8000,
            bedrooms=3, bathrooms=2, max_guests=6, amenities='Parking',
        )

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_filter_by_house_type(self):
        """Filtering by house_type=Villa should return exactly 1 result."""
        response = self.client.get(f'{self.url}?house_type=Villa')
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['house_type'], 'Villa')

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_filter_by_price_range(self):
        """Filter by min_price=5000&max_price=10000 should return mid-range condo."""
        response = self.client.get(f'{self.url}?min_price=5000&max_price=10000')
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Mid-Range Condo')

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_filter_by_bedrooms_gte(self):
        """Filter bedrooms >= 3 should return 2 properties (Villa + Condo)."""
        response = self.client.get(f'{self.url}?bedrooms__gte=3')
        self.assertEqual(len(response.data['results']), 2)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_search_by_keyword(self):
        """Searching 'campus' should find the Cheap Studio."""
        response = self.client.get(f'{self.url}?search=campus')
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('campus', response.data['results'][0]['description'])

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_search_by_location(self):
        """Searching 'Bole' should find the Luxury Villa."""
        response = self.client.get(f'{self.url}?search=Bole')
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('Bole', response.data['results'][0]['location'])

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_ordering_by_price_descending(self):
        """Ordering by -price should return highest price first."""
        response = self.client.get(f'{self.url}?ordering=-price')
        results = response.data['results']
        self.assertEqual(len(results), 3)
        prices = [float(r['price']) for r in results]
        self.assertEqual(prices, sorted(prices, reverse=True))


# ===========================================================================
# 8. FAVORITES / WISHLIST SYSTEM
# ===========================================================================

class FavoritesE2ETest(APITestCase):
    """E2E tests for the Favorites (Wishlist) system."""

    def setUp(self):
        self.owner1 = User.objects.create_user(username='favowner1', password='P!', role='OWNER')
        self.owner2 = User.objects.create_user(username='favowner2', password='P!', role='OWNER')
        self.tenant = User.objects.create_user(username='favtenant', password='P!', role='TENANT')

        self.prop_owner1 = Property.objects.create(
            owner=self.owner1, title='Owner1 Place', house_type='Villa',
            price=5000, description='D', location='X', bedrooms=1,
            bathrooms=1, max_guests=1, amenities='N',
        )
        self.prop_owner2 = Property.objects.create(
            owner=self.owner2, title='Owner2 Place', house_type='Condo',
            price=8000, description='D', location='Y', bedrooms=2,
            bathrooms=1, max_guests=2, amenities='N',
        )
        self.fav_url = '/api/interactions/favorites/'

    def test_tenant_can_favorite_property(self):
        """Tenant should successfully favorite a property."""
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self.fav_url, {'property': self.prop_owner1.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_can_favorite_others_property(self):
        """Owner can favorite another owner's property."""
        self.client.force_authenticate(user=self.owner1)
        response = self.client.post(self.fav_url, {'property': self.prop_owner2.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_cannot_favorite_own_property(self):
        """Owner cannot favorite their own property. Should get 400."""
        self.client.force_authenticate(user=self.owner1)
        response = self.client.post(self.fav_url, {'property': self.prop_owner1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_favorite_returns_400(self):
        """Favoriting the same property twice should return 400, not 500."""
        self.client.force_authenticate(user=self.tenant)
        self.client.post(self.fav_url, {'property': self.prop_owner1.id})
        response = self.client.post(self.fav_url, {'property': self.prop_owner1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_favorites_returns_nested_property_data(self):
        """GET /favorites/ should return nested property details."""
        self.client.force_authenticate(user=self.tenant)
        self.client.post(self.fav_url, {'property': self.prop_owner1.id})
        response = self.client.get(self.fav_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        # Nested property data should include 'title'
        self.assertIn('title', response.data['results'][0]['property'])

    def test_delete_favorite(self):
        """User should be able to remove a favorite."""
        self.client.force_authenticate(user=self.tenant)
        create_resp = self.client.post(self.fav_url, {'property': self.prop_owner1.id})
        fav_id = create_resp.data['id']
        response = self.client.delete(f'{self.fav_url}{fav_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_unauthenticated_cannot_favorite(self):
        """Anonymous user should get 401 when trying to favorite."""
        response = self.client.post(self.fav_url, {'property': self.prop_owner1.id})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ===========================================================================
# 9. MOCK PAYMENT PROCESSING
# ===========================================================================

class MockPaymentE2ETest(APITestCase):
    """E2E tests for the mock payment endpoint."""

    def setUp(self):
        self.owner = User.objects.create_user(username='paymentowner', password='P!', role='OWNER')
        self.other_owner = User.objects.create_user(username='payother', password='P!', role='OWNER')
        self.tenant = User.objects.create_user(username='paytenant', password='P!', role='TENANT')

        self.prop = Property.objects.create(
            owner=self.owner, title='Unpaid Listing', house_type='Apartment',
            price=5000, description='D', location='X', bedrooms=1,
            bathrooms=1, max_guests=1, amenities='N', is_paid=False,
        )
        self.pay_url = '/api/interactions/payments/pay/'

    @override_settings(PROPERTY_LISTING_PRICE=15.00, LISTING_EXPIRATION_DAYS=30)
    def test_owner_can_pay_for_own_property(self):
        """Owner should successfully pay for their property via mock payment."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.pay_url, {'property_id': self.prop.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_paid)
        self.assertIsNotNone(self.prop.paid_until)

    @override_settings(PROPERTY_LISTING_PRICE=15.00, LISTING_EXPIRATION_DAYS=30)
    def test_payment_creates_log_entry(self):
        """A successful payment should create a PaymentLog record."""
        self.client.force_authenticate(user=self.owner)
        self.client.post(self.pay_url, {'property_id': self.prop.id})
        log = PaymentLog.objects.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.amount_paid, 15.00)
        self.assertEqual(log.owner, self.owner)
        self.assertEqual(log.status, 'SUCCESS')

    def test_tenant_cannot_access_payment_endpoint(self):
        """Tenant should get 403 on the payment endpoint."""
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self.pay_url, {'property_id': self.prop.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_cannot_pay_for_others_property(self):
        """Owner should get 400 when trying to pay for another owner's property."""
        self.client.force_authenticate(user=self.other_owner)
        response = self.client.post(self.pay_url, {'property_id': self.prop.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_payment_for_nonexistent_property_fails(self):
        """Payment for a non-existent property should return 400."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.pay_url, {'property_id': 99999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# 10. FULL USER JOURNEY E2E FLOWS
# ===========================================================================

class FullUserJourneyE2ETest(APITestCase):
    """
    Complete end-to-end user flows simulating real-world scenarios
    to verify cross-module integration.
    """

    @override_settings(REQUIRE_LISTING_PAYMENT=True, PROPERTY_LISTING_PRICE=15.00, LISTING_EXPIRATION_DAYS=30)
    def test_full_owner_journey_register_create_pay_list(self):
        """
        Full Owner Journey:
        1. Register (gets TENANT)
        2. Create a property (auto-upgraded to OWNER, property is unpaid)
        3. Public cannot see it (payment gating ON)
        4. Owner pays for the property (mock payment)
        5. Public can now see it
        """
        # Step 1: Register
        reg_resp = self.client.post('/api/auth/register/', {
            'username': 'journeyowner',
            'email': 'journey@test.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(reg_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reg_resp.data['role'], 'TENANT')

        # Step 2: Login
        token_resp = self.client.post('/api/auth/token/', {
            'username': 'journeyowner', 'password': 'StrongPass123!',
        })
        access = token_resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        # Step 3: Create a property (should auto-upgrade to OWNER)
        prop_resp = self.client.post('/api/properties/', {
            'title': 'Journey Villa', 'description': 'Amazing place',
            'house_type': 'Villa', 'location': 'Bole',
            'price': '12000.00', 'bedrooms': 4, 'bathrooms': 3.0,
            'max_guests': 8, 'amenities': 'WiFi, Pool',
        })
        self.assertEqual(prop_resp.status_code, status.HTTP_201_CREATED)
        prop_id = prop_resp.data['id']

        # Verify role upgraded
        user = User.objects.get(username='journeyowner')
        self.assertEqual(user.role, 'OWNER')

        # Step 4: Public cannot see it (unpaid)
        anon_client = APIClient()
        anon_resp = anon_client.get('/api/properties/')
        self.assertEqual(len(anon_resp.data['results']), 0)

        # Step 5: Owner pays for the property
        pay_resp = self.client.post('/api/interactions/payments/pay/', {
            'property_id': prop_id,
        })
        self.assertEqual(pay_resp.status_code, status.HTTP_200_OK)

        # Step 6: Public can now see it
        anon_resp2 = anon_client.get('/api/properties/')
        self.assertEqual(len(anon_resp2.data['results']), 1)
        self.assertEqual(anon_resp2.data['results'][0]['title'], 'Journey Villa')

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_full_tenant_journey_register_browse_favorite(self):
        """
        Full Tenant Journey:
        1. Register (gets TENANT)
        2. Browse listed properties
        3. Favorite a property
        4. View favorites list (nested property data)
        5. Remove favorite
        """
        # Setup: Create a property for the tenant to browse
        owner = User.objects.create_user(username='bgowner', password='P!', role='OWNER')
        Property.objects.create(
            owner=owner, title='Browse Me', house_type='Villa', price=5000,
            description='D', location='X', bedrooms=1, bathrooms=1,
            max_guests=1, amenities='N',
        )

        # Step 1: Register
        reg_resp = self.client.post('/api/auth/register/', {
            'username': 'journeytenant',
            'email': 'jtenant@test.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(reg_resp.status_code, status.HTTP_201_CREATED)

        # Step 2: Login
        token_resp = self.client.post('/api/auth/token/', {
            'username': 'journeytenant', 'password': 'StrongPass123!',
        })
        access = token_resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        # Step 3: Browse properties
        browse_resp = self.client.get('/api/properties/')
        self.assertEqual(browse_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(browse_resp.data['results']), 1)
        prop_id = browse_resp.data['results'][0]['id']

        # Step 4: Favorite the property
        fav_resp = self.client.post('/api/interactions/favorites/', {'property': prop_id})
        self.assertEqual(fav_resp.status_code, status.HTTP_201_CREATED)
        fav_id = fav_resp.data['id']

        # Step 5: View favorites list (nested data)
        list_resp = self.client.get('/api/interactions/favorites/')
        self.assertEqual(len(list_resp.data['results']), 1)
        self.assertIn('title', list_resp.data['results'][0]['property'])

        # Step 6: Remove favorite
        del_resp = self.client.delete(f'/api/interactions/favorites/{fav_id}/')
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)

        # Verify it's gone
        list_resp2 = self.client.get('/api/interactions/favorites/')
        self.assertEqual(len(list_resp2.data['results']), 0)


# ===========================================================================
# 11. GEOLOCATION INTEGRATION
# ===========================================================================

class GeolocationE2ETest(APITestCase):
    """E2E tests for property geolocation fields."""

    def setUp(self):
        self.owner = User.objects.create_user(username='geowner', password='P!', role='OWNER')
        self.url = '/api/properties/'
        self.client.force_authenticate(user=self.owner)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_create_property_with_geolocation(self):
        """Property should be created with latitude and longitude."""
        data = {
            'title': 'Geo Prop', 'description': 'D', 'house_type': 'Villa',
            'location': 'Addis', 'price': '5000.00', 'bedrooms': 3,
            'bathrooms': 2.0, 'max_guests': 6, 'amenities': 'WiFi',
            'latitude': 9.033333, 'longitude': 38.700000
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(response.data['latitude']), 9.033333)
        self.assertEqual(float(response.data['longitude']), 38.700000)

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_update_property_geolocation(self):
        """Property geolocation should be updatable."""
        prop = Property.objects.create(
            owner=self.owner, title='Old Geo', description='D',
            house_type='Villa', location='X', price=1000,
            bedrooms=1, bathrooms=1, max_guests=1, amenities='N',
            latitude=1.0, longitude=1.0
        )
        response = self.client.patch(f'{self.url}{prop.id}/', {'latitude': 2.0})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prop.refresh_from_db()
        self.assertEqual(float(prop.latitude), 2.0)


# ===========================================================================
# 12. MESSAGING SYSTEM
# ===========================================================================

from messaging.models import Conversation, Message

class MessagingE2ETest(APITestCase):
    """E2E tests for the direct messaging system."""

    def setUp(self):
        self.tenant = User.objects.create_user(username='msgtenant', password='P!', role='TENANT')
        self.owner = User.objects.create_user(username='msgowner', password='P!', role='OWNER')
        self.other = User.objects.create_user(username='msgother', password='P!', role='TENANT')
        self.prop = Property.objects.create(
            owner=self.owner, title='Message Prop', house_type='Villa',
            price=5000, description='D', location='X', bedrooms=1,
            bathrooms=1, max_guests=1, amenities='N'
        )
        self.conv_url = '/api/messaging/conversations/'

    def test_create_conversation_and_send_message(self):
        """Testing conversation creation and message exchange."""
        # Create conversation manually (as we haven't built a 'start conv' endpoint yet, we'll use ORM and test views)
        conv = Conversation.objects.create(property=self.prop)
        conv.participants.add(self.tenant, self.owner)
        
        # Tenant sends a message
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(f'{self.conv_url}{conv.id}/send_message/', {'content': 'Is it available?'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['content'], 'Is it available?')
        
        # Owner views messages
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(f'{self.conv_url}{conv.id}/messages/')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['content'], 'Is it available?')

    def test_unauthorized_access_to_conversation(self):
        """Users not in the conversation should get 404/403."""
        conv = Conversation.objects.create(property=self.prop)
        conv.participants.add(self.tenant, self.owner)
        
        self.client.force_authenticate(user=self.other)
        response = self.client.get(f'{self.conv_url}{conv.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_conversations_only_shows_participants(self):
        """List view should only return conversations where the user is a participant."""
        conv = Conversation.objects.create(property=self.prop)
        conv.participants.add(self.tenant, self.owner)
        
        self.client.force_authenticate(user=self.tenant)
        response = self.client.get(self.conv_url)
        self.assertEqual(len(response.data['results']), 1)
        
        self.client.force_authenticate(user=self.other)
        response = self.client.get(self.conv_url)
        self.assertEqual(len(response.data['results']), 0)
