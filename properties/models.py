from django.db import models
from django.conf import settings
from django.utils import timezone

class PropertyQuerySet(models.QuerySet):
    def active(self):
        """Returns only properties that have not been soft deleted."""
        return self.filter(is_deleted=False)

class PropertyManager(models.Manager):
    def get_queryset(self):
        return PropertyQuerySet(self.model, using=self._db)
        
    def active(self):
        return self.get_queryset().active()

class Property(models.Model):
    HOUSE_TYPES = [
        ('Condo', 'Condo'),
        ('Villa', 'Villa'),
        ('Apartment', 'Apartment'),
        ('House', 'House'),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='properties')
    title = models.CharField(max_length=255)
    description = models.TextField()
    house_type = models.CharField(max_length=50, choices=HOUSE_TYPES)
    location = models.CharField(max_length=255)
    
    price = models.DecimalField(max_digits=12, decimal_places=2)
    floor_number = models.IntegerField(null=True, blank=True)
    bedrooms = models.IntegerField()
    bathrooms = models.DecimalField(max_digits=4, decimal_places=1)
    max_guests = models.IntegerField()
    amenities = models.TextField()
    
    image = models.ImageField(upload_to='properties/images/', null=True, blank=True)
    
    is_available = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=False)
    paid_until = models.DateTimeField(null=True, blank=True)
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PropertyManager()

    def delete(self, using=None, keep_parents=False):
        """Perform soft delete instead of actual delete."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def hard_delete(self):
        """Actual deletion from the database."""
        super().delete()

    def __str__(self):
        return f"{self.title} - {self.location}"
