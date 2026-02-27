from rest_framework import viewsets, mixins, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .models import Favorite, PaymentLog
from .serializers import FavoriteSerializer, FavoriteListSerializer, MockPaymentSerializer
from .permissions import IsTenantOrOwnerNotSelf, IsOwner
from properties.models import Property


class FavoriteViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsTenantOrOwnerNotSelf]

    def get_queryset(self):
        """Only return favorites that belong to the querying user"""
        return Favorite.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return FavoriteListSerializer
        return FavoriteSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MockPaymentView(APIView):
    permission_classes = [IsOwner]

    def post(self, request):
        serializer = MockPaymentSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            property_id = serializer.validated_data['property_id']
            prop = Property.objects.get(id=property_id)
            
            # Get environment configurations
            price = getattr(settings, 'PROPERTY_LISTING_PRICE', 15.00)
            expiry_days = getattr(settings, 'LISTING_EXPIRATION_DAYS', 30)
            
            # Log the mock transaction
            PaymentLog.objects.create(
                property=prop,
                owner=request.user,
                amount_paid=price,
                status='SUCCESS'
            )
            
            # Upgrade the property's validity
            prop.is_paid = True
            prop.paid_until = timezone.now() + timedelta(days=expiry_days)
            prop.save()

            return Response({
                "message": f"Payment of {price} successful!",
                "property_id": prop.id,
                "is_paid": prop.is_paid,
                "paid_until": prop.paid_until
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
