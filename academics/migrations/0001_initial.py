# Generated manually for TabsForge School OS
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('schools', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Class',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(blank=True, max_length=20)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='classes', to='schools.school')),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Class',
                'verbose_name_plural': 'Classes',
                'unique_together': {('school', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(blank=True, max_length=20)),
                ('description', models.TextField(blank=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subjects', to='schools.school')),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('school', 'code')},
            },
        ),
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=50)),
                ('room', models.CharField(blank=True, max_length=50)),
                ('capacity', models.PositiveSmallIntegerField(default=0)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='schools.school')),
                ('school_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='academics.class')),
            ],
            options={
                'ordering': ['school_class', 'name'],
                'verbose_name': 'Section',
                'verbose_name_plural': 'Sections',
                'unique_together': {('school', 'school_class', 'name')},
            },
        ),
        migrations.CreateModel(
            name='ClassSubject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='classsubjects', to='schools.school')),
                ('school_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_subjects', to='academics.class')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_subjects', to='academics.subject')),
                ('teacher', models.ForeignKey(blank=True, limit_choices_to={'role': 'staff'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_class_subjects', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Class Subject',
                'verbose_name_plural': 'Class Subjects',
                'unique_together': {('school', 'school_class', 'subject')},
            },
        ),
        migrations.CreateModel(
            name='Timetable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('day', models.CharField(choices=[('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'), ('thursday', 'Thursday'), ('friday', 'Friday'), ('saturday', 'Saturday'), ('sunday', 'Sunday')], max_length=10)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('room', models.CharField(blank=True, max_length=50)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetables', to='schools.school')),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetables', to='academics.section')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetables', to='academics.subject')),
                ('teacher', models.ForeignKey(blank=True, limit_choices_to={'role': 'staff'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='timetables', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['day', 'start_time'],
            },
        ),
    ]
