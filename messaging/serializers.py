from rest_framework import serializers
from django.db.models import Q
from .models import Conversation, Message
from users.models import CustomUser


class UserSummarySerializer(serializers.ModelSerializer):
    """Lightweight user representation for embedding in messages/conversations."""

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'role']


class MessageSerializer(serializers.ModelSerializer):
    """
    Serializer for Message objects.
    - sender is expanded for display (read-only).
    - content is validated to reject empty/whitespace-only messages.
    """
    sender = UserSummarySerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'content', 'timestamp', 'is_read']
        read_only_fields = ['id', 'conversation', 'sender', 'timestamp', 'is_read']

    def validate_content(self, value):
        """Reject empty or whitespace-only messages."""
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty.")
        return value.strip()


class ConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for listing conversations (inbox view).
    Includes:
    - Nested participants
    - Linked property title (for context, like Airbnb inquiry threads)
    - Last message preview (for inbox snippet display)
    - Unread message count (for badge/notification UI)
    """
    participants = UserSummarySerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    property_title = serializers.ReadOnlyField(source='property.title')

    class Meta:
        model = Conversation
        fields = [
            'id', 'participants', 'property', 'property_title',
            'last_message', 'unread_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'participants', 'created_at', 'updated_at']

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-timestamp').first()
        if last_msg:
            return {
                'id': last_msg.id,
                'sender': last_msg.sender.username,
                'content': last_msg.content[:100],  # Truncate preview
                'timestamp': last_msg.timestamp,
                'is_read': last_msg.is_read,
            }
        return None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return 0


class StartConversationSerializer(serializers.Serializer):
    """
    Serializer for starting a new conversation.
    Validates:
    - recipient_id exists and is not the current user.
    - property_id (optional) exists and is not soft-deleted.
    - No duplicate conversation already exists between the two users for the same property.
    """
    recipient_id = serializers.IntegerField()
    property_id = serializers.IntegerField(required=False, allow_null=True)
    initial_message = serializers.CharField()

    def validate_recipient_id(self, value):
        try:
            recipient = CustomUser.objects.get(id=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Recipient does not exist.")

        request = self.context.get('request')
        if request and request.user.id == value:
            raise serializers.ValidationError("You cannot start a conversation with yourself.")

        return value

    def validate_property_id(self, value):
        if value is None:
            return value
        from properties.models import Property
        try:
            Property.objects.get(id=value, is_deleted=False)
        except Property.DoesNotExist:
            raise serializers.ValidationError("Property does not exist or has been deleted.")
        return value

    def validate_initial_message(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Initial message cannot be empty.")
        return value.strip()

    def validate(self, attrs):
        """Check for duplicate conversations between same users about same property."""
        request = self.context.get('request')
        recipient_id = attrs.get('recipient_id')
        property_id = attrs.get('property_id')

        existing = Conversation.objects.filter(
            participants=request.user
        ).filter(
            participants=recipient_id
        )

        if property_id:
            existing = existing.filter(property_id=property_id)
        else:
            existing = existing.filter(property__isnull=True)

        if existing.exists():
            raise serializers.ValidationError(
                {"detail": "A conversation with this user about this property already exists."}
            )

        return attrs
