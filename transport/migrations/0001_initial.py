# Generated manually for TabsForge School OS
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('schools', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Route',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('start_location', models.CharField(max_length=255)),
                ('end_location', models.CharField(max_length=255)),
                ('stops', models.JSONField(blank=True, default=list)),
                ('distance_km', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='routes', to='schools.school')),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('school', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Vehicle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('registration_number', models.CharField(db_index=True, max_length=50)),
                ('make', models.CharField(blank=True, max_length=100)),
                ('model', models.CharField(blank=True, max_length=100)),
                ('capacity', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('active', 'Active'), ('maintenance', 'Maintenance'), ('inactive', 'Inactive')], default='active', max_length=20)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vehicles', to='schools.school')),
            ],
            options={
                'ordering': ['registration_number'],
                'unique_together': {('school', 'registration_number')},
            },
        ),
        migrations.CreateModel(
            name='VehicleAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('driver_name', models.CharField(blank=True, max_length=100)),
                ('driver_phone', models.CharField(blank=True, max_length=30)),
                ('effective_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='transport.route')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vehicleassignments', to='schools.school')),
                ('vehicle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='transport.vehicle')),
            ],
            options={
                'ordering': ['-effective_date'],
            },
        ),
    ]
