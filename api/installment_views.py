"""
Part 3 — Installment plan views and payment gateway abstraction.

Endpoints:
  GET/POST  /api/installment-plans/
  GET/POST  /api/installment-plans/<pk>/schedules/
  POST      /api/payments/<pk>/receipt/        — download PDF receipt
  GET       /api/receipts/                     — list receipts for current school
  GET       /api/receipts/<pk>/pdf/            — download receipt PDF
  POST      /api/payments/ussd/initiate/       — initiate USSD payment (stub)
"""
import io
import logging
from decimal import Decimal

from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.permissions import IsTenantScoped
from api.viewsets import get_current_school, filter_by_school
from finance.models import InstallmentPlan, InstallmentSchedule, Invoice, Payment, PaymentReceipt

logger = logging.getLogger(__name__)


# ── Serializers ──────────────────────────────────────────────────────────────

class InstallmentScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstallmentSchedule
        fields = ['id', 'sequence', 'amount', 'due_date', 'label', 'school']
        read_only_fields = ['id', 'school']


class InstallmentPlanSerializer(serializers.ModelSerializer):
    schedule = InstallmentScheduleSerializer(many=True, read_only=True)

    class Meta:
        model = InstallmentPlan
        fields = ['id', 'school', 'fee_structure', 'name', 'number_of_instalments', 'is_default', 'schedule']
        read_only_fields = ['id', 'school']


class PaymentReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentReceipt
        fields = [
            'id', 'receipt_number', 'payment', 'student_name', 'invoice_number',
            'amount', 'method', 'issued_at',
        ]
        read_only_fields = ['id', 'receipt_number', 'issued_at']


# ── ViewSets ─────────────────────────────────────────────────────────────────

class InstallmentPlanViewSet(viewsets.ModelViewSet):
    serializer_class = InstallmentPlanSerializer
    permission_classes = [IsAuthenticated, IsTenantScoped]

    def get_queryset(self):
        school = get_current_school(self.request)
        qs = InstallmentPlan.objects.filter(school=school).select_related('fee_structure')
        if fs_id := self.request.query_params.get('fee_structure'):
            qs = qs.filter(fee_structure_id=fs_id)
        return qs

    def perform_create(self, serializer):
        school = get_current_school(self.request)
        serializer.save(school=school)

    @action(detail=True, methods=['get', 'post'], url_path='schedules')
    def schedules(self, request, pk=None):
        plan = self.get_object()
        if request.method == 'GET':
            items = plan.schedule.all()
            return Response(InstallmentScheduleSerializer(items, many=True).data)
        ser = InstallmentScheduleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(plan=plan, school=plan.school)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='generate-schedules')
    def generate_schedules(self, request, pk=None):
        """
        Auto-generate equal instalments for this plan.
        Body: { "start_date": "2024-01-01", "interval_days": 30 }
        """
        plan = self.get_object()
        start = request.data.get('start_date')
        interval = int(request.data.get('interval_days', 30))
        if not start:
            return Response({'detail': 'start_date required'}, status=400)

        from datetime import date, timedelta
        plan_amount = plan.fee_structure.amount
        per_install = (plan_amount / plan.number_of_instalments).quantize(Decimal('0.01'))
        plan.schedule.all().delete()

        created = []
        current_date = date.fromisoformat(start)
        for i in range(1, plan.number_of_instalments + 1):
            amt = per_install if i < plan.number_of_instalments else plan_amount - per_install * (plan.number_of_instalments - 1)
            sch = InstallmentSchedule.objects.create(
                school=plan.school, plan=plan,
                sequence=i, amount=amt, due_date=current_date,
                label=f'Instalment {i} of {plan.number_of_instalments}',
            )
            created.append(sch)
            current_date += timedelta(days=interval)

        return Response(InstallmentScheduleSerializer(created, many=True).data, status=201)


class PaymentReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentReceiptSerializer
    permission_classes = [IsAuthenticated, IsTenantScoped]

    def get_queryset(self):
        school = get_current_school(self.request)
        qs = PaymentReceipt.objects.filter(school=school).select_related('payment__invoice__student')
        if student_id := self.request.query_params.get('student'):
            qs = qs.filter(payment__invoice__student_id=student_id)
        if invoice_num := self.request.query_params.get('invoice'):
            qs = qs.filter(invoice_number=invoice_num)
        return qs

    @action(detail=True, methods=['get'], url_path='pdf')
    def download_pdf(self, request, pk=None):
        """Generate and stream a PDF receipt."""
        receipt = self.get_object()
        pdf_data = _generate_receipt_pdf(receipt)
        return HttpResponse(
            pdf_data,
            content_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="receipt_{receipt.receipt_number}.pdf"'},
        )


def _generate_receipt_pdf(receipt: PaymentReceipt) -> bytes:
    """Generate a simple PDF receipt using reportlab."""
    try:
        from reportlab.lib.pagesizes import A5
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A5, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        forest = colors.HexColor('#125A0F')
        gold = colors.HexColor('#D6A20D')

        school = receipt.school
        title_style = ParagraphStyle('title', parent=styles['Heading1'], textColor=forest, fontSize=16, spaceAfter=4)
        sub_style = ParagraphStyle('sub', parent=styles['Normal'], textColor=gold, fontSize=10, spaceAfter=12)

        story.append(Paragraph(school.name, title_style))
        story.append(Paragraph('PAYMENT RECEIPT', sub_style))
        story.append(Spacer(1, 0.3*cm))

        data = [
            ['Receipt No.', receipt.receipt_number],
            ['Date', receipt.issued_at.strftime('%d %b %Y %H:%M')],
            ['Student', receipt.student_name],
            ['Invoice No.', receipt.invoice_number],
            ['Amount Paid', f'NGN {receipt.amount:,.2f}'],
            ['Payment Method', receipt.method.replace('_', ' ').title()],
        ]
        t = Table(data, colWidths=[5*cm, 9*cm])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f9f0')),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8f8f8')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(
            '<i>This is an official receipt generated by TabsForge School OS. '
            'Please keep it for your records.</i>',
            ParagraphStyle('footer', parent=styles['Normal'], fontSize=8, textColor=colors.gray)
        ))

        doc.build(story)
        return buf.getvalue()
    except ImportError:
        # Fallback text receipt if reportlab missing
        text = (
            f"PAYMENT RECEIPT\n"
            f"{'='*40}\n"
            f"School:    {receipt.school.name}\n"
            f"Receipt:   {receipt.receipt_number}\n"
            f"Date:      {receipt.issued_at.strftime('%d %b %Y %H:%M')}\n"
            f"Student:   {receipt.student_name}\n"
            f"Invoice:   {receipt.invoice_number}\n"
            f"Amount:    NGN {receipt.amount:,.2f}\n"
            f"Method:    {receipt.method}\n"
            f"{'='*40}\n"
            f"Official receipt - TabsForge School OS\n"
        )
        return text.encode()


# ── USSD Payment Gateway Stub ────────────────────────────────────────────────

class USSDPaymentProvider:
    """
    USSD payment provider interface (Part 3).

    In production, integrate with a local USSD aggregator such as:
    - VTpass API (https://vtpass.com/documentation)
    - Interswitch USSD (https://developer.interswitchgroup.com)
    - Flutterwave USSD: https://developer.flutterwave.com/docs/collecting-payments/ussd

    This stub demonstrates the interface so the payment flow is complete.
    Replace the _initiate() implementation with the real API call.
    """

    def initiate(self, invoice: Invoice, phone: str) -> dict:
        """
        Initiate a USSD payment session.
        Returns { 'ussd_code': '*903*...*#', 'session_id': '...', 'status': 'pending' }
        """
        return self._initiate(invoice, phone)

    def _initiate(self, invoice: Invoice, phone: str) -> dict:
        # Stub: in production, call the USSD provider API here
        session_id = f"USSD-{invoice.school.subdomain.upper()}-{invoice.id}"
        ussd_code = f"*903*{invoice.invoice_number}*{int(invoice.balance)}#"
        logger.info("USSD stub: initiate payment for invoice %s, phone %s", invoice.invoice_number, phone)
        return {
            'ussd_code': ussd_code,
            'session_id': session_id,
            'status': 'pending',
            'note': 'Dial the USSD code on your phone to complete payment.',
            'provider': 'stub',
        }

    def verify(self, session_id: str) -> dict:
        """Check payment status for a USSD session."""
        # Stub always returns pending
        return {'session_id': session_id, 'status': 'pending', 'provider': 'stub'}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_ussd_payment(request):
    """
    Initiate a USSD payment for an invoice.
    Body: { "invoice_id": 1, "phone": "+2348012345678" }
    """
    invoice_id = request.data.get('invoice_id')
    phone = request.data.get('phone', '').strip()
    if not invoice_id:
        return Response({'detail': 'invoice_id required'}, status=400)
    school = get_current_school(request)
    try:
        invoice = Invoice.objects.get(pk=invoice_id, school=school)
    except Invoice.DoesNotExist:
        return Response({'detail': 'Invoice not found.'}, status=404)
    if invoice.balance <= 0:
        return Response({'detail': 'Invoice is already fully paid.'}, status=400)

    provider = USSDPaymentProvider()
    result = provider.initiate(invoice, phone or request.user.phone)
    return Response(result)
