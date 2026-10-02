"""CSV import endpoints for students and staff."""
import csv
import io

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from api.permissions import IsSchoolAdmin, IsSuperAdmin
from core.utils import get_current_school
from schools.models import School
from staff.models import Staff
from students.models import Student
from .onboarding_views import onboard_school


def _school_for_user(user):
    if user.is_superuser or user.role == user.Roles.SUPER_ADMIN:
        return None
    return user.school


STUDENT_TEMPLATE = [
    'first_name', 'last_name', 'admission_number', 'gender', 'class_name', 'section_name', 'parent_email', 'parent_phone'
]

STAFF_TEMPLATE = [
    'first_name', 'last_name', 'email', 'employee_id', 'designation', 'department', 'employment_type', 'role'
]

SCHOOL_TEMPLATE = [
    'school_name', 'address', 'subdomain', 'tier', 'admin_email', 'admin_name', 'admin_password', 'billing_cycle'
]


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSchoolAdmin | IsSuperAdmin])
def csv_template_view(request, import_type):
    """Return a downloadable CSV template for the requested import type."""
    if import_type == 'students':
        headers = STUDENT_TEMPLATE
    elif import_type == 'staff':
        headers = STAFF_TEMPLATE
    elif import_type == 'schools':
        headers = SCHOOL_TEMPLATE
    else:
        return Response({'detail': 'Unsupported import type.'}, status=400)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerow(['' for _ in headers])
    output.seek(0)

    response = Response(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{import_type}_template.csv"'
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsSchoolAdmin | IsSuperAdmin])
def csv_import_view(request, import_type):
    """Validate and optionally commit a CSV import for students or staff."""
    if import_type not in {'students', 'staff', 'schools'}:
        return Response({'detail': 'Unsupported import type.'}, status=400)

    if import_type == 'schools' and not (
        request.user.is_superuser or request.user.role == request.user.Roles.SUPER_ADMIN
    ):
        return Response(
            {'detail': 'Only super admins can import schools.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    file = request.FILES.get('file')
    if not file:
        return Response({'detail': 'CSV file is required.'}, status=400)

    school = _school_for_user(request.user)
    commit = request.query_params.get('commit') == 'true'

    try:
        decoded = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))
    except Exception as exc:
        return Response({'detail': f'Could not read CSV: {exc}'}, status=400)

    rows = list(reader)
    if not rows:
        return Response({'detail': 'CSV file is empty.'}, status=400)

    errors = []
    created = 0
    updated = 0

    try:
        with transaction.atomic():
            for idx, row in enumerate(rows, start=1):
                row_errors = _process_row(import_type, row, school, commit)
                if row_errors:
                    errors.append({'row': idx, 'errors': row_errors})
                elif commit:
                    created += 1
            if errors and not commit:
                # Validation pass: don't persist anything.
                pass
            elif errors:
                # Validation errors during commit should roll back.
                raise Exception('rollback')
    except Exception:
        # Rolled back because of errors during commit.
        return Response(
            {'detail': 'Import failed; no records were saved.', 'errors': errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if errors:
        return Response(
            {'detail': 'Validation failed. Set ?commit=true to save valid rows.', 'errors': errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if commit:
        return Response({
            'detail': f'Imported {created} {import_type} successfully.',
            'created': created,
            'updated': updated,
        })

    return Response({
        'detail': f'{len(rows)} rows validated successfully. Set ?commit=true to save.',
        'rows': len(rows),
    })


def _process_row(import_type, row, school, commit):
    """Validate and optionally save a single CSV row."""
    errors = []
    for key in row:
        if row[key] is not None:
            row[key] = row[key].strip()

    if import_type == 'students':
        first = row.get('first_name', '')
        last = row.get('last_name', '')
        adm = row.get('admission_number', '')
        if not first:
            errors.append('first_name is required.')
        if not last:
            errors.append('last_name is required.')
        if not adm:
            errors.append('admission_number is required.')
        class_name = row.get('class_name', '')
        section_name = row.get('section_name', '')
        gender = (row.get('gender', '') or 'other').lower()
        if gender not in {'male', 'female', 'other'}:
            errors.append('gender must be male, female or other.')
        # Resolve the target section up-front so unknown classes fail validation.
        section = None
        if class_name:
            from academics.models import Class, Section
            try:
                cls = Class.objects.get(school=school, name__iexact=class_name)
            except Class.DoesNotExist:
                errors.append(f'Unknown class "{class_name}".')
            else:
                if section_name:
                    try:
                        section = cls.sections.get(school=school, name__iexact=section_name)
                    except Section.DoesNotExist:
                        errors.append(
                            f'Unknown section "{section_name}" in class "{class_name}".'
                        )
                else:
                    section = cls.sections.filter(school=school).first()
        if errors:
            return errors
        if commit:
            student, _ = Student.objects.update_or_create(
                school=school,
                admission_number=adm,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'gender': gender,
                },
            )
            # Enrol the student when the CSV names a class/section.
            if section is not None:
                from academics.models import Section as _Section
                section = _Section.objects.get(pk=section.pk, school=school)
                session = school.academic_sessions.filter(is_current=True).first()
                term = school.terms.filter(is_current=True).first()
                if session and term:
                    from students.models import StudentEnrollment
                    StudentEnrollment.objects.get_or_create(
                        school=school, student=student,
                        session=session, term=term,
                        defaults={'section': section},
                    )
            # Optionally create/link a guardian contact.
            parent_email = row.get('parent_email', '')
            if parent_email:
                user, _ = User.objects.update_or_create(
                    email=parent_email,
                    defaults={
                        'first_name': row.get('parent_name', 'Parent'),
                        'last_name': '',
                        'role': User.Roles.PARENT,
                        'school': school,
                    },
                )
                from students.models import Guardian, GuardianStudent
                guardian, _ = Guardian.objects.update_or_create(
                    school=school, user=user,
                    defaults={
                        'first_name': user.first_name or 'Parent',
                        'last_name': user.last_name or student.last_name,
                        'email': parent_email,
                        'phone': row.get('parent_phone', ''),
                    },
                )
                GuardianStudent.objects.get_or_create(
                    school=school, guardian=guardian, student=student,
                    defaults={'is_primary': True},
                )
        return None

    if import_type == 'staff':
        first = row.get('first_name', '')
        last = row.get('last_name', '')
        email = row.get('email', '')
        emp_id = row.get('employee_id', '')
        if not first:
            errors.append('first_name is required.')
        if not last:
            errors.append('last_name is required.')
        if not email:
            errors.append('email is required.')
        if not emp_id:
            errors.append('employee_id is required.')
        role = (row.get('role') or 'staff').lower()
        role_map = {
            'staff': User.Roles.STAFF,
            'teacher': User.Roles.TEACHER,
            'form_teacher': User.Roles.FORM_TEACHER,
            'exam_officer': User.Roles.EXAM_OFFICER,
            'principal': User.Roles.PRINCIPAL,
            'vice_principal': User.Roles.VICE_PRINCIPAL,
            'admissions_officer': User.Roles.ADMISSIONS_OFFICER,
            'hr_admin': User.Roles.HR_ADMIN,
            'librarian': User.Roles.LIBRARIAN,
            'accountant': User.Roles.ACCOUNTANT,
            'school_admin': User.Roles.SCHOOL_ADMIN,
        }
        if role not in role_map:
            errors.append(f'role must be one of: {", ".join(sorted(role_map))}.')
        if errors:
            return errors
        if commit:
            user, _ = User.objects.update_or_create(
                email=email,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'role': role_map[role],
                    'school': school,
                },
            )
            Staff.objects.update_or_create(
                school=school,
                employee_id=emp_id,
                defaults={
                    'user': user,
                    'designation': row.get('designation', ''),
                    'department': row.get('department', ''),
                    'employment_type': row.get('employment_type', 'full_time').lower(),
                },
            )
        return None

    if import_type == 'schools':
        for key in row:
            if row[key] is not None:
                row[key] = row[key].strip()
        errors, _, _ = onboard_school(row, commit=commit)
        return errors if errors else None

    return ['Unknown import type.']
