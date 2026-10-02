"""Payment provider stub layer for TabsForge School OS.

Real integrations can be enabled by setting PAYMENT_PROVIDER in the environment.
Supported values: "paystack", "flutterwave".
If no provider is configured or the provider is "manual", a stub reference is returned.
"""
import uuid

from django.conf import settings


def get_provider():
    return getattr(settings, 'PAYMENT_PROVIDER', 'manual').lower()


def create_subscription(amount, currency, metadata=None):
    """Create a subscription charge/payment intent stub.

    Returns a dict with provider, provider_ref, status, and metadata.
    """
    provider = get_provider()
    ref = str(uuid.uuid4())
    if provider == 'paystack':
        # Real Paystack integration would POST /transaction/initialize
        return {
            'provider': 'paystack',
            'provider_ref': f'paystack_{ref}',
            'status': 'pending',
            'authorization_url': f'https://paystack.com/pay/{ref}',
            'metadata': metadata or {},
        }
    if provider == 'flutterwave':
        # Real Flutterwave integration would POST /payments
        return {
            'provider': 'flutterwave',
            'provider_ref': f'flutterwave_{ref}',
            'status': 'pending',
            'authorization_url': f'https://flutterwave.com/pay/{ref}',
            'metadata': metadata or {},
        }
    return {
        'provider': 'manual',
        'provider_ref': f'manual_{ref}',
        'status': 'completed',
        'metadata': metadata or {},
    }


SIZE_TIERS = (
    {'key': 'tier_1', 'minimum': 0, 'maximum': 499, 'rate': 2700, 'setup_fee': 50000},
    {'key': 'tier_2', 'minimum': 500, 'maximum': 999, 'rate': 2250, 'setup_fee': 100000},
    {'key': 'tier_3', 'minimum': 1000, 'maximum': None, 'rate': 1750, 'setup_fee': 150000},
)


def size_tier_for(student_count):
    count = max(0, int(student_count))
    for pricing in SIZE_TIERS:
        if pricing['maximum'] is None or count <= pricing['maximum']:
            return pricing
    return SIZE_TIERS[-1]


def termly_price(student_count, first_term=False):
    count = max(0, int(student_count))
    pricing = size_tier_for(count)
    billable_students = max(0, count - 50) if first_term else count
    return {
        'size_tier': pricing['key'],
        'active_students': count,
        'free_students': min(count, 50) if first_term else 0,
        'billable_students': billable_students,
        'rate': pricing['rate'],
        'subscription_amount': billable_students * pricing['rate'],
        'setup_fee': pricing['setup_fee'],
    }


def tier_price(tier, billing_cycle='termly'):
    return termly_price(0, first_term=True)['setup_fee'] if billing_cycle == 'termly' else 0
