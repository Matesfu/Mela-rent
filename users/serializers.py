from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    Accepts username, email, password, password2 (confirmation), and role.
    Hashes the password before saving.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        label='Confirm Password',
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'password2', 'role')
        extra_kwargs = {
            'email': {'required': True},
        }

    def validate_email(self, value):
        """Ensure the email is unique (case-insensitive)."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        """Ensure both passwords match."""
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {"password2": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        """Create and return a new user with a hashed password."""
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the authenticated user's profile.
    Excludes the password and other sensitive fields.
    """

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'date_joined', 'last_login')
        read_only_fields = fields
