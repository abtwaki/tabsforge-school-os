# Generated manually for TabsForge School OS
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('academics', '0001_initial'),
        ('schools', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Staff',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee_id', models.CharField(db_index=True, max_length=50)),
                ('designation', models.CharField(blank=True, max_length=100)),
                ('department', models.CharField(blank=True, max_length=100)),
                ('employment_type', models.CharField(choices=[('full_time', 'Full Time'), ('part_time', 'Part Time'), ('contract', 'Contract')], default='full_time', max_length=20)),
                ('date_joined', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('assigned_classes', models.ManyToManyField(blank=True, related_name='assigned_staff', to='academics.class')),
                ('assigned_subjects', models.ManyToManyField(blank=True, related_name='assigned_staff', to='academics.subject')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staffs', to='schools.school')),
                ('user', models.OneToOneField(limit_choices_to={'role': 'staff'}, on_delete=django.db.models.deletion.CASCADE, related_name='staff_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['employee_id'],
                'verbose_name': 'Staff Member',
                'verbose_name_plural': 'Staff',
                'unique_together': {('school', 'employee_id')},
            },
        ),
    ]
