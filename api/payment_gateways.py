"""Online payment gateway integrations — Paystack and Flutterwave.

Flow:
  1. Parent (or bursar) clicks "Pay online" on an invoice
     → POST /api/payments/<provider>/initialize/ {invoice_id}
     → OnlinePaymentIntent (pending) + the gateway's checkout URL
  2. Gateway redirects the payer back to the app
     → GET /api/payments/<provider>/verify/?reference=…
     → verified charge settles into a real Payment + auto receipt
  3. Optionally the gateway pushes a server webhook
     → POST /api/webhooks/<provider>/ (signature-verified, no login needed)

Everything is env-driven — with no keys configured the endpoints answer 503
instead of pretending to work:
    PAYSTACK_SECRET_KEY, PAYSTACK_BASE_URL (default https://api.paystack.co)
    FLUTTERWAVE_SECRET_KEY, FLUTTERWAVE_BASE_URL, FLUTTERWAVE_SECRET_HASH
    FRONTEND_URL — where the payer returns after checkout
"""
import hashlib
import hmac
import json
import logging
import secrets
import urllib.error
import urllib.request

from django.conf import settings
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from core.utils import audit, get_current_school
from finance.models import Invoice, OnlinePaymentIntent, Payment

logger = logging.getLogger(__name__)

TIMEOUT = 30


class GatewayNotConfigured(Exception):
    pass


# ── Low-level HTTP ────────────────────────────────────────────────────────────

def _request(method, url, payload=None, headers=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type': 'application/json', **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read() or '{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or '{}')
        except Exception:
            return e.code, {}
    except urllib.error.URLError as e:
        return 0, {'error': str(e)}


def _paystack(method, path, payload=None):
    key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    if not key:
        raise GatewayNotConfigured('PAYSTACK_SECRET_KEY is not configured on the server.')
    base = getattr(settings, 'PAYSTACK_BASE_URL', 'https://api.paystack.co').rstrip('/')
    return _request(method, f'{base}{path}', payload, {'Authorization': f'Bearer {key}'})


def _flutterwave(method, path, payload=None):
    key = getattr(settings, 'FLUTTERWAVE_SECRET_KEY', '')
    if not key:
        raise GatewayNotConfigured('FLUTTERWAVE_SECRET_KEY is not configured on the server.')
    base = getattr(settings, 'FLUTTERWAVE_BASE_URL', 'https://api.flutterwave.com').rstrip('/')
    return _request(method, f'{base}{path}', payload, {'Authorization': f'Bearer {key}'})


# ── Shared helpers ────────────────────────────────────────────────────────────

def _authorised_invoice(request, school, invoice_id):
    """The invoice a payer may pay: parents only their children's; staff any."""
    try:
        invoice = Invoice.objects.select_related('student').get(pk=invoice_id, school=school)
    except Invoice.DoesNotExist:
        return None, Response({'error': 'Invoice not found.'}, status=404)
    if request.user.role == User.Roles.PARENT:
        guardian = getattr(request.user, 'guardian_profile', None)
        linked = guardian and invoice.student.guardians.filter(guardian=guardian).exists()
        if not linked:
            return None, Response({'error': 'You can only pay invoices for your own children.'}, status=403)
    if invoice.status in (Invoice.Status.PAID, Invoice.Status.CANCELLED, Invoice.Status.DRAFT):
        return None, Response({'error': f'Invoice is {invoice.get_status_display()} — no payment can be taken.'}, status=400)
    return invoice, None


def _settle(intent, gateway_payload=None):
    """Convert a confirmed intent into a real Payment (receipt auto-created).

    Idempotent — a settled intent is never paid twice, and a duplicate Payment
    reference for the invoice is guarded by re-checking inside the lock.
    """
    if intent.status == OnlinePaymentIntent.Status.PAID:
        return True
    with transaction.atomic():
        intent = OnlinePaymentIntent.objects.select_for_update().get(pk=intent.pk)
        if intent.status == OnlinePaymentIntent.Status.PAID:
            return True
        already = Payment.objects.filter(
            invoice=intent.invoice, method=intent.provider, reference=intent.reference,
        ).exists()
        if not already:
            Payment.objects.create(
                school=intent.school,
                invoice=intent.invoice,
                amount=intent.amount,
                method=intent.provider,
                reference=intent.reference,
            )
        intent.status = OnlinePaymentIntent.Status.PAID
        if gateway_payload:
            intent.gateway_payload = gateway_payload
            intent.save(update_fields=['status', 'gateway_payload'])
        else:
            intent.save(update_fields=['status'])
    return True


# ── Initialize / verify endpoints ────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initialize_payment(request, provider):
    """POST /api/payments/<provider>/initialize/  body: {invoice_id}"""
    school = get_current_school(request)
    if not school:
        return Response({'error': 'School context required.'}, status=400)
    invoice, error = _authorised_invoice(request, school, request.data.get('invoice_id'))
    if error:
        return error

    reference = f"TF-{school.subdomain.upper()}-{invoice.id}-{secrets.token_hex(4)}"
    amount = invoice.balance
    payer_email = request.data.get('email') or request.user.email
    callback = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/payment-return?provider={provider}&reference={reference}"

    try:
        if provider == OnlinePaymentIntent.Providers.PAYSTACK:
            code, body = _paystack('POST', '/transaction/initialize', {
                'email': payer_email,
                'amount': int(amount * 100),  # kobo
                'reference': reference,
                'callback_url': callback,
                'metadata': {'invoice_id': invoice.id, 'school_id': school.id},
            })
            if code != 200 or not body.get('status'):
                return Response({'error': body.get('message') or 'Paystack declined the transaction.'}, status=502)
            checkout_url = body['data']['authorization_url']
        elif provider == OnlinePaymentIntent.Providers.FLUTTERWAVE:
            code, body = _flutterwave('POST', '/v3/payments', {
                'tx_ref': reference,
                'amount': str(amount),
                'currency': 'NGN',
                'redirect_url': callback,
                'customer': {'email': payer_email},
                'meta': {'invoice_id': invoice.id, 'school_id': school.id},
            })
            if code != 200 or body.get('status') != 'success':
                return Response({'error': body.get('message') or 'Flutterwave declined the transaction.'}, status=502)
            checkout_url = body['data']['link']
        else:
            return Response({'error': f'Unsupported provider: {provider}'}, status=400)
    except GatewayNotConfigured as exc:
        return Response({'error': str(exc)}, status=503)

    OnlinePaymentIntent.objects.create(
        school=school, invoice=invoice, provider=provider,
        reference=reference, amount=amount, payer_email=payer_email,
        gateway_payload={'init_response': body},
    )
    audit(request, 'payment.online_initiate', invoice)
    return Response({'authorization_url': checkout_url, 'reference': reference})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_payment(request, provider):
    """GET /api/payments/<provider>/verify/?reference=…"""
    school = get_current_school(request)
    if not school:
        return Response({'error': 'School context required.'}, status=400)
    reference = request.query_params.get('reference', '')
    try:
        intent = OnlinePaymentIntent.objects.select_related('invoice').get(
            school=school, provider=provider, reference=reference,
        )
    except OnlinePaymentIntent.DoesNotExist:
        return Response({'error': 'Payment reference not found.'}, status=404)

    if intent.status == OnlinePaymentIntent.Status.PAID:
        return Response({'status': 'paid', 'reference': reference, 'already_recorded': True})

    try:
        if provider == OnlinePaymentIntent.Providers.PAYSTACK:
            code, body = _paystack('GET', f'/transaction/verify/{reference}')
            success = code == 200 and body.get('status') and body['data'].get('status') == 'success'
        elif provider == OnlinePaymentIntent.Providers.FLUTTERWAVE:
            # Flutterwave verifies by transaction id; the tx_ref query also works.
            tx_id = request.query_params.get('transaction_id') or intent.gateway_payload.get('init_response', {}).get('data', {}).get('id')
            code, body = _flutterwave('GET', f'/v3/transactions/verify_by_reference?tx_ref={reference}')
            data = (body.get('data') or {})
            success = code == 200 and body.get('status') == 'success' and data.get('status') == 'successful'
        else:
            return Response({'error': f'Unsupported provider: {provider}'}, status=400)
    except GatewayNotConfigured as exc:
        return Response({'error': str(exc)}, status=503)

    if success:
        _settle(intent, gateway_payload={'verify_response': body})
        audit(request, 'payment.online_settled', intent.invoice)
        return Response({'status': 'paid', 'reference': reference})

    intent.status = OnlinePaymentIntent.Status.FAILED
    intent.save(update_fields=['status'])
    return Response({'status': 'failed', 'reference': reference}, status=402)


# ── Webhooks (no login — signature is the auth) ───────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def paystack_webhook(request):
    """Paystack → charge.success webhook. Verified by HMAC-SHA512 signature."""
    key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    if not key:
        return Response({'error': 'Not configured.'}, status=503)
    signature = request.headers.get('X-Paystack-Signature', '')
    digest = hmac.new(key.encode(), request.body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(digest, signature):
        return Response({'error': 'Invalid signature.'}, status=403)

    event = request.data if isinstance(request.data, dict) else {}
    if event.get('event') != 'charge.success':
        return Response({'detail': 'Ignored.'})
    reference = (event.get('data') or {}).get('reference', '')
    intent = OnlinePaymentIntent.objects.filter(provider='paystack', reference=reference).first()
    if intent:
        _settle(intent, gateway_payload={'webhook': event})
    return Response({'detail': 'ok'})


@api_view(['POST'])
@permission_classes([AllowAny])
def flutterwave_webhook(request):
    """Flutterwave → charge.completed webhook. Verified by verif-hash header."""
    expected = getattr(settings, 'FLUTTERWAVE_SECRET_HASH', '')
    if not expected:
        return Response({'error': 'Not configured.'}, status=503)
    if request.headers.get('verif-hash') != expected:
        return Response({'error': 'Invalid signature.'}, status=403)

    event = request.data if isinstance(request.data, dict) else {}
    data = event.get('data') or {}
    reference = data.get('tx_ref', '')
    if event.get('event') == 'charge.completed' and data.get('status') == 'successful':
        intent = OnlinePaymentIntent.objects.filter(provider='flutterwave', reference=reference).first()
        if intent:
            _settle(intent, gateway_payload={'webhook': event})
    return Response({'detail': 'ok'})
