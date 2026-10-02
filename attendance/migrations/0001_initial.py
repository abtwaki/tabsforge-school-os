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
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField()),
                ('status', models.CharField(choices=[('present', 'Present'), ('absent', 'Absent'), ('late', 'Late'), ('excused', 'Excused')], default='present', max_length=10)),
                ('remarks', models.TextField(blank=True)),
                ('marked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='marked_attendances', to=settings.AUTH_USER_MODEL)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='schools.school')),
                ('school_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='academics.class')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendances', to='students.student')),
            ],
            options={
                'ordering': ['-date', 'student__last_name'],
                'verbose_name': 'Attendance',
                'verbose_name_plural': 'Attendance Records',
                'unique_together': {('school', 'student', 'school_class', 'date')},
            },
        ),
    ]
