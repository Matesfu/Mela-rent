from django.contrib import admin
from .models import Property

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'location', 'price', 'is_paid', 'is_available', 'is_deleted')
    list_filter = ('is_paid', 'is_available', 'is_deleted', 'house_type')
    search_fields = ('title', 'location', 'owner__username')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
