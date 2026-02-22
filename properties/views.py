from rest_framework import viewsets, permissions, filters, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
from django.utils import timezone
import django_filters

from .models import Property
from .serializers import PropertySerializer
from .permissions import IsOwnerOrReadOnly


class PropertyFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr='lte')
    
    bedrooms = django_filters.NumberFilter(field_name="bedrooms")
    bedrooms__gte = django_filters.NumberFilter(field_name="bedrooms", lookup_expr='gte')
    bedrooms__lte = django_filters.NumberFilter(field_name="bedrooms", lookup_expr='lte')

    bathrooms = django_filters.NumberFilter(field_name="bathrooms")
    bathrooms__gte = django_filters.NumberFilter(field_name="bathrooms", lookup_expr='gte')
    bathrooms__lte = django_filters.NumberFilter(field_name="bathrooms", lookup_expr='lte')

    max_guests = django_filters.NumberFilter(field_name="max_guests")
    max_guests__gte = django_filters.NumberFilter(field_name="max_guests", lookup_expr='gte')
    max_guests__lte = django_filters.NumberFilter(field_name="max_guests", lookup_expr='lte')

    location = django_filters.CharFilter(field_name="location", lookup_expr='icontains')
    amenities = django_filters.CharFilter(field_name="amenities", lookup_expr='icontains')

    class Meta:
        model = Property
        fields = ['house_type', 'is_available']


class PropertyViewSet(viewsets.ModelViewSet):
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PropertyFilter
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['price', 'created_at']

    def get_queryset(self):
        """
        Dynamically filter the queryset based on:
        1. Soft deletion (never return is_deleted=True)
        2. Payment Environment variable (if REQUIRE_LISTING_PAYMENT=True, require is_paid=True and paid_until > now for non-owners)
        Owners can always see their own soft-deleted or unpaid properties (though we strip soft-deleted even for owners to keep list logic clean, they can't access them anymore).
        Actually, let's keep it simple: No one sees soft deleted properties via list/retrieve API.
        """
        user = self.request.user
        queryset = Property.objects.active() # active() filters out is_deleted=True
        
        # If listing payment is required, we must filter out unpaid or expired listings
        # UNLESS the user requesting them is the owner of the listing.
        if settings.REQUIRE_LISTING_PAYMENT:
            now = timezone.now()
            # A property is valid if it's paid AND its paid_until is in the future.
            # However, for an owner, they should see their OWN properties regardless of payment status.
            if user.is_authenticated:
                # User sees: (paid AND not expired) OR (owner == user)
                import operator
                from django.db.models import Q
                
                # Payment condition
                payment_condition = Q(is_paid=True, paid_until__gt=now)
                # Ownership condition
                owner_condition = Q(owner=user)
                
                queryset = queryset.filter(payment_condition | owner_condition)
            else:
                # Anonymous users only see paid & valid properties
                queryset = queryset.filter(is_paid=True, paid_until__gt=now)
                
        return queryset

    def perform_create(self, serializer):
        # The user creating the property is assigned as the owner automatically
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        # Override destroy to trigger soft delete instead of hard delete
        instance.delete()
