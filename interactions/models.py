from django.db import models
from django.conf import settings

class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'property')

    def __str__(self):
        return f"{self.user.username} - {self.property.title}"


class PaymentLog(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'SUCCESS'),
        ('FAILED', 'FAILED'),
    ]

    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='payments')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUCCESS')

    def __str__(self):
        return f"{self.owner.username} paid {self.amount_paid} for {self.property.title} ({self.status})"
