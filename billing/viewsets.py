"""DRF viewsets for billing and subscriptions."""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.permissions import IsSuperAdmin, IsSchoolAdmin
from core.permissions import IsTenantScoped
from core.utils import filter_by_school

from .models import Subscription
from .providers import create_subscription, termly_price
from .serializers import SubscriptionSerializer


class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role == user.Roles.SUPER_ADMIN:
            return qs
        return filter_by_school(qs, self.request)

    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdmin])
    def renew(self, request, pk=None):
        subscription = self.get_object()
        cycle = request.data.get('billing_cycle', subscription.billing_cycle)
        if cycle != 'termly':
            return Response({'detail': 'Billing cycle must be termly.'}, status=400)
        student_count = subscription.school.studentenrollments.filter(status='active').values('student_id').distinct().count()
        pricing = termly_price(student_count)
        amount = pricing['subscription_amount']
        result = create_subscription(amount, subscription.currency, metadata={'school': subscription.school_id, **pricing})
        subscription.provider = result['provider']
        subscription.provider_ref = result['provider_ref']
        subscription.amount = amount
        subscription.billing_cycle = cycle
        if result['status'] == 'completed':
            subscription.status = Subscription.Status.ACTIVE
        subscription.save()
        return Response({
            'subscription': SubscriptionSerializer(subscription).data,
            'pricing': pricing,
            'provider_response': result,
        })

    @action(detail=True, methods=['post'], permission_classes=[IsSchoolAdmin])
    def change_tier(self, request, pk=None):
        subscription = self.get_object()
        tier = request.data.get('tier')
        if tier not in {c[0] for c in subscription.school.Tiers.choices}:
            return Response({'detail': 'Invalid tier.'}, status=400)
        subscription.tier = tier
        subscription.school.tier = tier
        subscription.school.save(update_fields=['tier'])
        subscription.save(update_fields=['tier', 'updated_at'])
        return Response(SubscriptionSerializer(subscription).data)
