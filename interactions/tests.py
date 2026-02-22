from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test import override_settings

from properties.models import Property
from .models import Favorite, PaymentLog

User = get_user_model()

class InteractionsTests(APITestCase):

    def setUp(self):
        # Create Users
        self.owner1 = User.objects.create_user(username="owner1", role="OWNER", password="123")
        self.owner2 = User.objects.create_user(username="owner2", role="OWNER", password="123")
        self.tenant = User.objects.create_user(username="tenant1", role="TENANT", password="123")

        # Create Properties
        self.prop1 = Property.objects.create(
            owner=self.owner1, title="Owner 1 Prop", house_type="Villa", price=100.0, bedrooms=1, bathrooms=1, max_guests=1, is_paid=False
        )
        self.prop2 = Property.objects.create(
            owner=self.owner2, title="Owner 2 Prop", house_type="Villa", price=100.0, bedrooms=1, bathrooms=1, max_guests=1, is_paid=False
        )
        
        self.fav_url = '/api/interactions/favorites/'
        self.pay_url = '/api/interactions/payments/pay/'

    # ------------------
    # 1. Favorites Tests
    # ------------------
    def test_tenant_can_favorite_any_property(self):
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self.fav_url, {"property": self.prop1.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Favorite.objects.count(), 1)
        
    def test_owner_can_favorite_others_property(self):
        self.client.force_authenticate(user=self.owner1)
        # Owner 1 favors Owner 2's property (Valid)
        response = self.client.post(self.fav_url, {"property": self.prop2.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
    def test_owner_cannot_favorite_own_property(self):
        self.client.force_authenticate(user=self.owner1)
        # Owner 1 tries to favorite Owner 1's property (Invalid)
        response = self.client.post(self.fav_url, {"property": self.prop1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Owners cannot favorite their own properties.", str(response.data))

    def test_duplicate_favorites_prevented(self):
        self.client.force_authenticate(user=self.tenant)
        self.client.post(self.fav_url, {"property": self.prop1.id})
        # Try again
        response = self.client.post(self.fav_url, {"property": self.prop1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Favorite.objects.count(), 1)

    # ------------------
    # 2. Payment Tests
    # ------------------
    @override_settings(PROPERTY_LISTING_PRICE=25.00, LISTING_EXPIRATION_DAYS=30)
    def test_owner_can_pay_for_own_property(self):
        self.client.force_authenticate(user=self.owner1)
        self.assertFalse(self.prop1.is_paid)
        
        response = self.client.post(self.pay_url, {"property_id": self.prop1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify Property was upgraded
        self.prop1.refresh_from_db()
        self.assertTrue(self.prop1.is_paid)
        self.assertIsNotNone(self.prop1.paid_until)
        
        # Verify Log was created
        log = PaymentLog.objects.first()
        self.assertEqual(log.amount_paid, 25.00)
        self.assertEqual(log.owner, self.owner1)

    def test_tenant_cannot_access_payment_endpoint(self):
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(self.pay_url, {"property_id": self.prop1.id})
        # The IsOwner permission strictly checks for "OWNER" role
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_cannot_pay_for_others_property(self):
        self.client.force_authenticate(user=self.owner1)
        # Try to pay for owner2's property
        response = self.client.post(self.pay_url, {"property_id": self.prop2.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("You do not own this property.", str(response.data))
