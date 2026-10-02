"""DRF serializers for billing."""
from rest_framework import serializers

from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'school', 'school_name', 'tier', 'billing_cycle', 'amount', 'currency',
            'status', 'provider', 'provider_ref', 'starts_at', 'ends_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
