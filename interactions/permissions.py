from rest_framework import permissions

class IsTenantOrOwnerNotSelf(permissions.BasePermission):
    """
    Custom permission for Favorites.
    - User must be authenticated.
    - If user is TENANT, they can favorite anything.
    - If user is OWNER, the serializer validation handles the "not self" check, 
      so here we just enforce authentication.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

class IsOwner(permissions.BasePermission):
    """
    Custom permission to strictly allow only OWNERS.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            hasattr(request.user, 'role') and 
            request.user.role == 'OWNER'
        )
