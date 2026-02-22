from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.test import override_settings

from .models import Property

User = get_user_model()

class PropertyTests(APITestCase):

    def setUp(self):
        # Create users
        self.owner = User.objects.create_user(
            username="testowner", email="owner@test.com", password="password123", role="OWNER"
        )
        self.tenant = User.objects.create_user(
            username="testtenant", email="tenant@test.com", password="password123", role="TENANT"
        )
        self.other_owner = User.objects.create_user(
            username="otherowner", email="other@test.com", password="password123", role="OWNER"
        )

        # Create properties
        self.property1_data = {
            "title": "Beautiful Villa",
            "description": "A very nice place",
            "house_type": "Villa",
            "location": "Addis Ababa",
            "price": "5000.00",
            "bedrooms": 3,
            "bathrooms": 2.0,
            "max_guests": 6,
            "amenities": "WiFi, Pool"
        }
        
        # Manually create a property that is NOT paid
        self.property1 = Property.objects.create(
            owner=self.owner,
            is_paid=False,
            **self.property1_data
        )

        # Create a PAID property
        self.paid_property = Property.objects.create(
            owner=self.owner,
            title="Paid Condo",
            description="Luxury",
            house_type="Condo",
            location="Downtown",
            price="10000.00",
            bedrooms=2,
            bathrooms=1.0,
            max_guests=4,
            amenities="Gym",
            is_paid=True,
            paid_until=timezone.now() + timedelta(days=30)
        )

        self.url_list = '/api/properties/'
        self.url_detail1 = f'/api/properties/{self.property1.id}/'
        self.url_detail_paid = f'/api/properties/{self.paid_property.id}/'

    def test_create_property_as_owner(self):
        self.client.force_authenticate(user=self.owner)
        data = {
            "title": "New Apartment",
            "description": "Testing create",
            "house_type": "Apartment",
            "location": "Bole",
            "price": "3000.00",
            "bedrooms": 1,
            "bathrooms": 1.0,
            "max_guests": 2,
            "amenities": "WiFi"
        }
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], "New Apartment")
        self.assertEqual(response.data['owner'], self.owner.id)

    def test_create_property_unauthenticated(self):
        data = {"title": "Test", "price": "1000.00"}
        response = self.client.post(self.url_list, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_property_owner_only(self):
        # 1. Owner updates
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(self.url_detail1, {"price": "6000.00"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.property1.refresh_from_db()
        self.assertEqual(self.property1.price, 6000.00)

        # 2. Other owner tries to update an UNPAID property they don't own
        # They will get a 404 because the strict get_queryset() filters out unpaid properties 
        # that don't belong to the requesting user.
        self.client.force_authenticate(user=self.other_owner)
        response2 = self.client.patch(self.url_detail1, {"price": "1000.00"})
        self.assertEqual(response2.status_code, status.HTTP_404_NOT_FOUND)

        # 3. Other owner tries to update a PAID property they don't own
        # They will see it in the queryset (it's paid), but the IsOwnerOrReadOnly permission blocks the PATCH
        response3 = self.client.patch(self.url_detail_paid, {"price": "1000.00"})
        self.assertEqual(response3.status_code, status.HTTP_403_FORBIDDEN)

    def test_soft_delete(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(self.url_detail1)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        self.property1.refresh_from_db()
        self.assertTrue(self.property1.is_deleted)
        self.assertIsNotNone(self.property1.deleted_at)

    @override_settings(REQUIRE_LISTING_PAYMENT=True)
    def test_payment_gating_enabled_public_view(self):
        # Public user should ONLY see the paid property
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only contain 1 item (the paid one)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], "Paid Condo")

    @override_settings(REQUIRE_LISTING_PAYMENT=False)
    def test_payment_gating_disabled_public_view(self):
        # If REQUIRE_LISTING_PAYMENT is False, public user should see BOTH
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    @override_settings(REQUIRE_LISTING_PAYMENT=True)
    def test_owner_can_see_own_unpaid_property(self):
        # The owner should see BOTH their properties, even if one is unpaid
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_filtering_and_searching(self):
        # We will set payment required to false to test raw filtering easily
        with override_settings(REQUIRE_LISTING_PAYMENT=False):
            # Test exact match
            response = self.client.get(self.url_list + "?house_type=Condo")
            self.assertEqual(len(response.data['results']), 1)
            self.assertEqual(response.data['results'][0]['house_type'], 'Condo')

            # Test Price Range
            response2 = self.client.get(self.url_list + "?min_price=6000")
            self.assertEqual(len(response2.data['results']), 1)
            self.assertEqual(response2.data['results'][0]['price'], '10000.00')

            # Test Search
            response3 = self.client.get(self.url_list + "?search=Addis")
            self.assertEqual(len(response3.data['results']), 1)
            self.assertEqual(response3.data['results'][0]['location'], 'Addis Ababa')
