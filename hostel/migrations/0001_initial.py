# Generated manually for TabsForge School OS
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('schools', '0001_initial'),
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Hostel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('address', models.TextField(blank=True)),
                ('warden_name', models.CharField(blank=True, max_length=100)),
                ('warden_phone', models.CharField(blank=True, max_length=30)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hostels', to='schools.school')),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('school', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Room',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('room_number', models.CharField(max_length=50)),
                ('capacity', models.PositiveIntegerField(default=1)),
                ('occupied', models.PositiveIntegerField(default=0)),
                ('amenities', models.JSONField(blank=True, default=dict)),
                ('hostel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rooms', to='hostel.hostel')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rooms', to='schools.school')),
            ],
            options={
                'ordering': ['room_number'],
                'unique_together': {('school', 'hostel', 'room_number')},
            },
        ),
        migrations.CreateModel(
            name='HostelAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('check_in', models.DateField()),
                ('check_out', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('checked_out', 'Checked Out')], default='active', max_length=20)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='allocations', to='hostel.room')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hostelallocations', to='schools.school')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hostel_allocations', to='students.student')),
            ],
            options={
                'ordering': ['-check_in'],
                'unique_together': {('school', 'room', 'student', 'check_in')},
            },
        ),
    ]
