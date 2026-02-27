from rest_framework import permissions


class IsConversationParticipant(permissions.BasePermission):
    """
    Object-level permission:
    Only users who are participants of a conversation may interact with it.
    This mirrors the security model of Airbnb, where inbox threads
    are strictly private to the involved parties.
    """

    def has_object_permission(self, request, view, obj):
        return request.user in obj.participants.all()
