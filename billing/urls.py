from rest_framework.routers import DefaultRouter

from .viewsets import SubscriptionViewSet

router = DefaultRouter()
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')

urlpatterns = router.urls
