# Generated manually for TabsForge School OS
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('academics', '0001_initial'),
        ('schools', '0001_initial'),
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Assessment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('type', models.CharField(choices=[('exam', 'Exam'), ('quiz', 'Quiz'), ('assignment', 'Assignment'), ('project', 'Project'), ('mid_term', 'Mid Term')], default='exam', max_length=20)),
                ('max_score', models.DecimalField(decimal_places=2, default=100.0, max_digits=6)),
                ('date', models.DateField()),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='schools.school')),
                ('school_class', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='academics.class')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='academics.subject')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='schools.term')),
            ],
            options={
                'ordering': ['-date', 'name'],
                'unique_together': {('school', 'term', 'subject', 'school_class', 'name', 'type')},
            },
        ),
        migrations.CreateModel(
            name='ReportCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('total_score', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('average_score', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('position', models.PositiveIntegerField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('published', 'Published')], default='draft', max_length=20)),
                ('teacher_comments', models.TextField(blank=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reportcards', to='schools.school')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='report_cards', to='students.student')),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='report_cards', to='schools.term')),
            ],
            options={
                'ordering': ['-term__start_date', 'student__last_name'],
                'unique_together': {('school', 'student', 'term')},
            },
        ),
        migrations.CreateModel(
            name='Grade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('score', models.DecimalField(decimal_places=2, max_digits=6)),
                ('remarks', models.CharField(blank=True, max_length=255)),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grades', to='gradebook.assessment')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grades', to='schools.school')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grades', to='students.student')),
            ],
            options={
                'ordering': ['-assessment__date', 'student__last_name'],
                'unique_together': {('school', 'assessment', 'student')},
            },
        ),
    ]
