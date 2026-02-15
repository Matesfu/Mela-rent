from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """Custom user model with role-based access control."""

    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        TENANT = 'TENANT', 'Tenant'
        ADMIN = 'ADMIN', 'Admin'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.TENANT,
    )

    def __str__(self):
        return f"{self.username} ({self.role})"
