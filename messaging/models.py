from django.db import models
from django.conf import settings


class Conversation(models.Model):
    """
    Represents a direct messaging thread between two users,
    optionally linked to a specific Property listing.

    Professional design notes:
    - ManyToMany for participants enables flexible N-party conversations.
    - Optional property FK ties conversations to listing context (like Airbnb inquiry threads).
    - updated_at auto-bumps on every save, used for ordering conversations by recency.
    """
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations',
    )
    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
        help_text='The property this conversation is about (optional).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']  # Most recent conversations first (inbox pattern)

    def __str__(self):
        return f"Conversation #{self.id}"


class Message(models.Model):
    """
    A single message within a Conversation.

    Professional design notes:
    - is_read enables "unread badge" UI (standard in Airbnb, WhatsApp, etc.)
    - ordering by timestamp ensures chronological display.
    - Cascade delete ensures messages are removed when a conversation is deleted.
    """
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message #{self.id} from {self.sender_id} at {self.timestamp}"
