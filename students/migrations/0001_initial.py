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
            name='Student',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('admission_number', models.CharField(db_index=True, max_length=50)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('gender', models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], max_length=10)),
                ('address', models.TextField(blank=True)),
                ('enrollment_date', models.DateField(auto_now_add=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='students', to='schools.school')),
                ('user', models.OneToOneField(blank=True, limit_choices_to={'role': 'student'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['last_name', 'first_name'],
                'unique_together': {('school', 'admission_number')},
            },
        ),
        migrations.CreateModel(
            name='Guardian',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('email', models.EmailField(blank=True)),
                ('relationship', models.CharField(choices=[('father', 'Father'), ('mother', 'Mother'), ('guardian', 'Guardian'), ('other', 'Other')], default='guardian', max_length=20)),
                ('address', models.TextField(blank=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guardians', to='schools.school')),
                ('user', models.OneToOneField(blank=True, limit_choices_to={'role': 'parent'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='guardian_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['last_name', 'first_name'],
            },
        ),
        migrations.CreateModel(
            name='GuardianStudent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('relationship', models.CharField(default='guardian', max_length=20)),
                ('is_primary', models.BooleanField(default=False)),
                ('guardian', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wards', to='students.guardian')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guardianstudents', to='schools.school')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guardians', to='students.student')),
            ],
            options={
                'verbose_name': 'Guardian-Student Link',
                'verbose_name_plural': 'Guardian-Student Links',
                'unique_together': {('school', 'guardian', 'student')},
            },
        ),
        migrations.CreateModel(
            name='StudentEnrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('roll_number', models.CharField(blank=True, max_length=20)),
                ('status', models.CharField(choices=[('active', 'Active'), ('completed', 'Completed'), ('withdrawn', 'Withdrawn')], default='active', max_length=20)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='studentenrollments', to='schools.school')),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='academics.section')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='schools.academicsession')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='students.student')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='schools.term')),
            ],
            options={
                'ordering': ['-session__start_date', 'student__last_name'],
                'unique_together': {('school', 'student', 'session', 'term')},
            },
        ),
    ]
