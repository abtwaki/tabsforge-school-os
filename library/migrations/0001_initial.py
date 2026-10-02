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
            name='Book',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=255)),
                ('author', models.CharField(blank=True, max_length=255)),
                ('isbn', models.CharField(blank=True, db_index=True, max_length=50)),
                ('publisher', models.CharField(blank=True, max_length=255)),
                ('published_year', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('copies_total', models.PositiveIntegerField(default=1)),
                ('copies_available', models.PositiveIntegerField(default=1)),
                ('category', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(choices=[('available', 'Available'), ('borrowed', 'Borrowed'), ('lost', 'Lost'), ('damaged', 'Damaged')], default='available', max_length=20)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='books', to='schools.school')),
            ],
            options={
                'ordering': ['title'],
            },
        ),
        migrations.CreateModel(
            name='BorrowRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('borrowed_at', models.DateTimeField(auto_now_add=True)),
                ('due_date', models.DateField()),
                ('returned_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('borrowed', 'Borrowed'), ('returned', 'Returned'), ('overdue', 'Overdue')], default='borrowed', max_length=20)),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='borrows', to='library.book')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='borrowrecords', to='schools.school')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='borrows', to='students.student')),
            ],
            options={
                'ordering': ['-borrowed_at'],
            },
        ),
    ]
