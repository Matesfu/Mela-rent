from rest_framework import serializers
from .models import Property

class PropertySerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.id')

    class Meta:
        model = Property
        exclude = ('is_deleted', 'deleted_at')
        read_only_fields = ('owner', 'created_at', 'updated_at', 'is_paid', 'paid_until')

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_bedrooms(self, value):
        if value < 0:
            raise serializers.ValidationError("Bedrooms cannot be negative.")
        return value

    def validate_bathrooms(self, value):
        if value < 0:
            raise serializers.ValidationError("Bathrooms cannot be negative.")
        return value

    def validate_max_guests(self, value):
        if value <= 0:
            raise serializers.ValidationError("Max guests must be at least 1.")
        return value
