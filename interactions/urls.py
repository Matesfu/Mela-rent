from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FavoriteViewSet, MockPaymentView

router = DefaultRouter()
router.register(r'favorites', FavoriteViewSet, basename='favorite')

urlpatterns = [
    path('', include(router.urls)),
    path('payments/pay/', MockPaymentView.as_view(), name='mock-payment'),
]
