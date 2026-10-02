# Generated manually for TabsForge School OS
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='School',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('logo', models.ImageField(blank=True, null=True, upload_to='schools/logos/')),
                ('address', models.TextField(blank=True)),
                ('contact_info', models.JSONField(blank=True, default=dict)),
                ('tier', models.CharField(choices=[('Sprout', 'Sprout'), ('Roots', 'Roots'), ('Bloom', 'Bloom'), ('Summit', 'Summit')], default='Sprout', max_length=20)),
                ('subdomain', models.SlugField(db_index=True, help_text='Unique subdomain for the school.', unique=True)),
                ('custom_domain', models.CharField(blank=True, db_index=True, max_length=255)),
                ('primary_color', models.CharField(default='#3B82F6', max_length=7)),
                ('secondary_color', models.CharField(default='#10B981', max_length=7)),
                ('status', models.CharField(choices=[('onboarding', 'Onboarding'), ('active', 'Active'), ('suspended', 'Suspended')], default='onboarding', max_length=20)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'School',
                'verbose_name_plural': 'Schools',
            },
        ),
        migrations.CreateModel(
            name='AcademicSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('is_current', models.BooleanField(default=False)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='academic_sessions', to='schools.school')),
            ],
            options={
                'ordering': ['-start_date'],
                'unique_together': {('school', 'name')},
                'verbose_name': 'Academic Session',
                'verbose_name_plural': 'Academic Sessions',
            },
        ),
        migrations.CreateModel(
            name='Term',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('is_current', models.BooleanField(default=False)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='terms', to='schools.school')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='terms', to='schools.academicsession')),
            ],
            options={
                'ordering': ['start_date'],
                'unique_together': {('school', 'session', 'name')},
                'verbose_name': 'Term',
                'verbose_name_plural': 'Terms',
            },
        ),
    ]
