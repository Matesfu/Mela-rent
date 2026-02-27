from rest_framework import viewsets, permissions, status, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    StartConversationSerializer,
)
from .permissions import IsConversationParticipant
from users.models import CustomUser


class ConversationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Inbox-style conversation management.

    Endpoints:
    - GET    /conversations/              → List user's conversations (inbox)
    - POST   /conversations/start/        → Start a new conversation with a user
    - GET    /conversations/{id}/          → Retrieve a single conversation
    - DELETE /conversations/{id}/          → Delete a conversation
    - GET    /conversations/{id}/messages/ → List all messages in a conversation
    - POST   /conversations/{id}/send_message/ → Send a message in a conversation
    - POST   /conversations/{id}/mark_as_read/ → Mark all unread messages as read
    """
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated, IsConversationParticipant]

    def get_queryset(self):
        """Return only conversations the authenticated user participates in."""
        return Conversation.objects.filter(
            participants=self.request.user
        ).prefetch_related('participants', 'messages')

    # ------------------------------------------------------------------
    # Custom Actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=['post'], url_path='start')
    def start_conversation(self, request):
        """
        Start a new conversation with another user.
        Optionally link it to a property (like an Airbnb inquiry).

        POST /conversations/start/
        Body: { "recipient_id": int, "property_id": int|null, "initial_message": str }
        """
        serializer = StartConversationSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        recipient = CustomUser.objects.get(id=serializer.validated_data['recipient_id'])
        property_id = serializer.validated_data.get('property_id')

        # Create the conversation
        conv = Conversation.objects.create(property_id=property_id)
        conv.participants.add(request.user, recipient)

        # Create the initial message
        Message.objects.create(
            conversation=conv,
            sender=request.user,
            content=serializer.validated_data['initial_message'],
        )

        return Response(
            ConversationSerializer(conv, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """
        List all messages in a conversation.

        GET /conversations/{id}/messages/
        """
        conversation = self.get_object()
        msgs = conversation.messages.select_related('sender').all()
        serializer = MessageSerializer(msgs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """
        Send a new message in an existing conversation.

        POST /conversations/{id}/send_message/
        Body: { "content": str }
        """
        conversation = self.get_object()
        content = request.data.get('content', '').strip()

        if not content:
            return Response(
                {"detail": "Message content cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content,
        )

        # Bump conversation's updated_at for inbox ordering
        conversation.save()

        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='mark_as_read')
    def mark_as_read(self, request, pk=None):
        """
        Mark all unread messages in a conversation as read
        (excluding messages sent by the requesting user).

        POST /conversations/{id}/mark_as_read/
        """
        conversation = self.get_object()
        updated = conversation.messages.filter(
            is_read=False
        ).exclude(
            sender=request.user
        ).update(is_read=True)

        return Response(
            {"detail": f"{updated} message(s) marked as read."},
            status=status.HTTP_200_OK,
        )
