# Generated manually for TabsForge School OS
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('academics', '0001_initial'),
        ('schools', '0001_initial'),
        ('students', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FeeCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('is_mandatory', models.BooleanField(default=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feecategories', to='schools.school')),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('school', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('invoice_number', models.CharField(db_index=True, max_length=50)),
                ('issue_date', models.DateField(auto_now_add=True)),
                ('due_date', models.DateField()),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('amount_paid', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('sent', 'Sent'), ('partial', 'Partially Paid'), ('paid', 'Paid'), ('overdue', 'Overdue'), ('cancelled', 'Cancelled')], default='draft', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invoices', to='schools.school')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invoices', to='students.student')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invoices', to='schools.term')),
            ],
            options={
                'ordering': ['-issue_date'],
                'unique_together': {('school', 'invoice_number')},
            },
        ),
        migrations.CreateModel(
            name='FeeStructure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='structures', to='finance.feecategory')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feestructures', to='schools.school')),
                ('school_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fee_structures', to='academics.class')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fee_structures', to='schools.term')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('method', models.CharField(choices=[('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'), ('mobile_money', 'Mobile Money'), ('card', 'Card'), ('cheque', 'Cheque')], default='cash', max_length=20)),
                ('reference', models.CharField(blank=True, max_length=100)),
                ('paid_at', models.DateTimeField(auto_now_add=True)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='finance.invoice')),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_payments', to=settings.AUTH_USER_MODEL)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='schools.school')),
            ],
            options={
                'ordering': ['-paid_at'],
            },
        ),
    ]
