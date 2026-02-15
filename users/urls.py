from django.urls import path
from .views import RegisterView, UserProfileView

app_name = 'users'

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('users/profile/', UserProfileView.as_view(), name='profile'),
]
