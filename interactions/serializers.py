from rest_framework import serializers
from .models import Favorite, PaymentLog
from properties.serializers import PropertySerializer

class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ['id', 'user', 'property', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
        
    def validate_property(self, value):
        # We need the request user to validate ownership constraints
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return value
            
        user = request.user
        
        # Rule: Owners cannot favorite their own properties
        if hasattr(user, 'role') and user.role == 'OWNER':
            if value.owner == user:
                raise serializers.ValidationError("Owners cannot favorite their own properties.")
                
        # Rule: Soft-deleted properties cannot be favorited
        if value.is_deleted:
            raise serializers.ValidationError("This property is no longer available.")
            
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user = request.user
            property_obj = attrs.get('property')
            if property_obj and Favorite.objects.filter(user=user, property=property_obj).exists():
                raise serializers.ValidationError({"detail": "You have already favorited this property."})
        return attrs

class FavoriteListSerializer(serializers.ModelSerializer):
    """
    Used for GET requests to instantly render the favorited properties
    without forcing the frontend to make secondary fetches.
    """
    property = PropertySerializer(read_only=True)

    class Meta:
        model = Favorite
        fields = ['id', 'property', 'created_at']


class MockPaymentSerializer(serializers.Serializer):
    property_id = serializers.IntegerField()

    def validate_property_id(self, value):
        from properties.models import Property
        try:
            prop = Property.objects.get(id=value, is_deleted=False)
        except Property.DoesNotExist:
            raise serializers.ValidationError("Property does not exist or has been deleted.")
            
        request = self.context.get('request')
        if request and request.user != prop.owner:
            raise serializers.ValidationError("You do not own this property.")
            
        return value
