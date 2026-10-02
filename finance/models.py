"""Finance and accounting models."""
import uuid
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import User
from core.models import TenantModel


class FeeCategory(TenantModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        unique_together = [['school', 'name']]
        ordering = ['name']

    def __str__(self):
        return self.name


class FeeStructure(TenantModel):
    category = models.ForeignKey(
        FeeCategory, on_delete=models.CASCADE, related_name='structures',
    )
    name = models.CharField(max_length=100)
    school_class = models.ForeignKey(
        'academics.Class', on_delete=models.CASCADE, related_name='fee_structures',
    )
    term = models.ForeignKey(
        'schools.Term', on_delete=models.CASCADE, related_name='fee_structures',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.school_class} - {self.amount}"


class InstallmentPlan(TenantModel):
    """
    Defines how a fee can be split into instalments (Part 3).
    Linked to a FeeStructure. e.g. 2-instalment, 3-instalment.
    """
    fee_structure = models.ForeignKey(
        FeeStructure, on_delete=models.CASCADE, related_name='installment_plans',
    )
    name = models.CharField(max_length=100, help_text='e.g. "Full Payment", "2-Instalment"')
    number_of_instalments = models.PositiveIntegerField(default=1)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['number_of_instalments']

    def __str__(self):
        return f"{self.name} ({self.fee_structure.name})"


class InstallmentSchedule(TenantModel):
    """One instalment in a plan — due_date + amount for sequence_number n."""
    plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name='schedule')
    sequence = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    label = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ['sequence']
        unique_together = [['plan', 'sequence']]

    def __str__(self):
        return f"{self.plan.name} - Instalment {self.sequence} ({self.due_date})"


class Invoice(TenantModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SENT = 'sent', 'Sent'
        PARTIAL = 'partial', 'Partially Paid'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'
        CANCELLED = 'cancelled', 'Cancelled'

    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='invoices',
    )
    invoice_number = models.CharField(max_length=50, db_index=True)
    term = models.ForeignKey(
        'schools.Term', on_delete=models.CASCADE, related_name='invoices',
    )
    # Part 3: optional instalment plan
    installment_plan = models.ForeignKey(
        InstallmentPlan, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoices',
    )
    current_installment_sequence = models.PositiveIntegerField(default=1)
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT,
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [['school', 'invoice_number']]
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.invoice_number} - {self.student}"

    @property
    def balance(self):
        return self.total_amount - self.amount_paid


class Payment(TenantModel):
    class Methods(models.TextChoices):
        CASH = 'cash', 'Cash'
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        MOBILE_MONEY = 'mobile_money', 'Mobile Money'
        CARD = 'card', 'Card'
        CHEQUE = 'cheque', 'Cheque'
        USSD = 'ussd', 'USSD'
        PAYSTACK = 'paystack', 'Paystack'
        FLUTTERWAVE = 'flutterwave', 'Flutterwave'

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name='payments',
    )
    # Part 3: which instalment this payment applies to
    installment_sequence = models.PositiveIntegerField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(
        max_length=20, choices=Methods.choices, default=Methods.CASH,
    )
    reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='recorded_payments',
    )
    provider_response = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-paid_at']

    def __str__(self):
        return f"Payment {self.amount} on {self.invoice}"


class ReceiptSequence(TenantModel):
    """Per-school, per-year atomic counter for receipt numbers.

    Incremented inside ``select_for_update()`` so concurrent payments can
    never receive the same receipt number.
    """
    year = models.PositiveIntegerField()
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [['school', 'year']]

    @classmethod
    def allocate(cls, school, year):
        """Atomically allocate the next receipt sequence value for a school/year."""
        seq, _ = cls.objects.select_for_update().get_or_create(
            school=school, year=year, defaults={'next_value': 1},
        )
        value = seq.next_value
        seq.next_value = value + 1
        seq.save(update_fields=['next_value'])
        return value


class PaymentReceipt(TenantModel):
    """
    Auto-generated digital receipt for every payment (Part 3).
    Created by signal on Payment.post_save.
    """
    receipt_number = models.CharField(max_length=60, unique=True)
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='receipt')
    student_name = models.CharField(max_length=200)
    invoice_number = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20)
    issued_at = models.DateTimeField(auto_now_add=True)
    pdf_file = models.FileField(upload_to='finance/receipts/', blank=True, null=True)

    class Meta:
        ordering = ['-issued_at']

    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.student_name}"


@receiver(post_save, sender=Payment)
def auto_create_receipt(sender, instance, created, **kwargs):
    """Every new payment automatically gets a receipt — atomically.

    Runs inside ``transaction.atomic()`` so the receipt insert, the invoice
    balance update and the receipt-number sequence advance together or roll
    back together. ``select_for_update()`` locks the invoice row and the
    sequence row so concurrent payments can neither double-apply a balance
    update nor draw duplicate receipt numbers.
    """
    if not created:
        return
    with transaction.atomic():
        # Lock the invoice row first so concurrent payment signals
        # serialise on it.
        inv = Invoice.objects.select_for_update().get(pk=instance.invoice_id)
        if PaymentReceipt.objects.filter(payment=instance).exists():
            return
        school = instance.school
        year = instance.paid_at.year if instance.paid_at else timezone.now().year
        seq_value = ReceiptSequence.allocate(school, year)
        receipt_number = (
            f"RCP/{(school.subdomain or 'SCHOOL').upper()}/{year}/{seq_value:05d}"
        )
        PaymentReceipt.objects.create(
            school=school,
            receipt_number=receipt_number,
            payment=instance,
            student_name=str(inv.student),
            invoice_number=inv.invoice_number,
            amount=instance.amount,
            method=instance.method,
        )
        inv.amount_paid = inv.payments.aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        if inv.amount_paid >= inv.total_amount:
            inv.status = Invoice.Status.PAID
        elif inv.amount_paid > 0:
            inv.status = Invoice.Status.PARTIAL
        inv.save(update_fields=['amount_paid', 'status'])


class Expense(TenantModel):
    """A school expenditure / expense ledger entry."""

    class Categories(models.TextChoices):
        SALARIES = 'salaries', 'Salaries & Wages'
        UTILITIES = 'utilities', 'Utilities'
        MAINTENANCE = 'maintenance', 'Maintenance & Repairs'
        SUPPLIES = 'supplies', 'Supplies & Consumables'
        TRANSPORT = 'transport', 'Transport'
        CATERING = 'catering', 'Catering'
        RENT = 'rent', 'Rent / Lease'
        INSURANCE = 'insurance', 'Insurance'
        EVENTS = 'events', 'Events & Activities'
        OTHER = 'other', 'Other'

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=30, choices=Categories.choices, default=Categories.OTHER,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    term = models.ForeignKey(
        'schools.Term', on_delete=models.CASCADE,
        related_name='expenses', null=True, blank=True,
    )
    recorded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='recorded_expenses',
    )
    receipt = models.FileField(
        upload_to='finance/receipts/', blank=True, null=True,
    )

    class Meta:
        ordering = ['-expense_date']
        verbose_name = 'Expense'

    def __str__(self):
        return f"{self.title} – {self.amount} ({self.expense_date})"


class OnlinePaymentIntent(TenantModel):
    """Tracks a parent-initiated online payment until the gateway confirms it.

    An intent is created when a payer clicks "Pay online"; when Paystack or
    Flutterwave confirms the charge (via /verify or webhook) a real Payment
    row + receipt is created. This keeps the ledger honest — a Payment record
    always means money actually received.
    """

    class Providers(models.TextChoices):
        PAYSTACK = 'paystack', 'Paystack'
        FLUTTERWAVE = 'flutterwave', 'Flutterwave'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        ABANDONED = 'abandoned', 'Abandoned'

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name='online_intents',
    )
    provider = models.CharField(max_length=20, choices=Providers.choices)
    reference = models.CharField(max_length=80, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    payer_email = models.EmailField(blank=True)
    gateway_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [['school', 'provider', 'reference']]

    def __str__(self):
        return f"{self.provider}:{self.reference} → {self.invoice.invoice_number} ({self.status})"
