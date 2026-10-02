"""Session rollover: promotion, graduation, and enrolment carry-forward.

Endpoints:
  GET  /api/rollover/preview/?source_session=&target_session=
  POST /api/rollover/  {source_session, target_session, target_term, mappings}

A "mapping" entry tells the engine what to do with each class's active
students:  { "12": "promote:15" }  { "14": "graduate" }  { "9": "skip" }
"""
import logging
from collections import defaultdict

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from academics.models import Class, Section
from core.utils import audit, get_current_school
from schools.models import AcademicSession, Term
from students.models import StudentEnrollment

logger = logging.getLogger(__name__)

ROLLOVER_ROLES = {
    User.Roles.SUPER_ADMIN, User.Roles.SCHOOL_ADMIN,
    User.Roles.PRINCIPAL, User.Roles.VICE_PRINCIPAL,
    User.Roles.GROUP_OWNER,
}


def _allowed(user):
    return user.is_authenticated and (
        user.is_superuser or user.role in ROLLOVER_ROLES)


def _active_enrollments(school, session):
    """Latest active enrollment per student in the session, with class info."""
    enrs = (
        StudentEnrollment.objects
        .filter(school=school, session=session,
                status=StudentEnrollment.Status.ACTIVE)
        .select_related('student', 'section__school_class', 'term')
        .order_by('student_id', '-term__start_date')
    )
    latest = {}
    for e in enrs:
        latest.setdefault(e.student_id, e)  # first row = latest term
    return latest


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rollover_preview(request):
    """Per-class counts of promotable students for a source session."""
    school = get_current_school(request)
    if not _allowed(request.user):
        return Response({'error': 'Not permitted.'}, status=403)
    if school is None:
        return Response({'error': 'No school context — pick a school first.'}, status=400)
    source_id = request.query_params.get('source_session')
    target_id = request.query_params.get('target_session')
    try:
        source = AcademicSession.objects.get(pk=source_id, school=school)
    except (AcademicSession.DoesNotExist, TypeError, ValueError):
        return Response({'source_session': 'Source session not found.'}, status=404)

    enrs = _active_enrollments(school, source)
    by_class = defaultdict(list)
    for e in enrs.values():
        by_class[e.section.school_class_id].append(e)

    # Students already enrolled in the target session (re-run awareness).
    already = set()
    if target_id:
        try:
            target = AcademicSession.objects.get(pk=target_id, school=school)
            already = set(
                StudentEnrollment.objects
                .filter(school=school, session=target)
                .values_list('student_id', flat=True))
        except (AcademicSession.DoesNotExist, TypeError, ValueError):
            pass

    classes = []
    for cls in Class.objects.filter(school=school).order_by('name'):
        students = by_class.get(cls.id, [])
        classes.append({
            'class_id': cls.id,
            'class_name': cls.name,
            'students': len(students),
            'already_in_target': sum(1 for e in students if e.student_id in already),
            'sections': [
                {'id': s.id, 'name': s.name}
                for s in Section.objects.filter(school=school, school_class=cls)
            ],
        })
    return Response({
        'source_session': {'id': source.id, 'name': source.name},
        'classes': classes,
        'all_classes': [
            {'id': c.id, 'name': c.name}
            for c in Class.objects.filter(school=school).order_by('name')
        ],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rollover_execute(request):
    """Run the rollover: promote mapped classes, graduate the rest."""
    school = get_current_school(request)
    if not _allowed(request.user):
        return Response({'error': 'Not permitted.'}, status=403)
    if school is None:
        return Response({'error': 'No school context — pick a school first.'}, status=400)

    try:
        source = AcademicSession.objects.get(
            pk=request.data.get('source_session'), school=school)
        target_session = AcademicSession.objects.get(
            pk=request.data.get('target_session'), school=school)
        target_term = Term.objects.get(
            pk=request.data.get('target_term'), school=school,
            session=target_session)
    except (AcademicSession.DoesNotExist, Term.DoesNotExist,
            TypeError, ValueError):
        return Response(
            {'error': 'source_session, target_session and target_term must '
                      'all exist in this school (term must belong to the '
                      'target session).'}, status=400)
    if source.pk == target_session.pk:
        return Response(
            {'error': 'Source and target sessions must differ.'}, status=400)

    mappings = request.data.get('mappings') or {}
    if not mappings:
        return Response({'mappings': 'Map at least one class.'}, status=400)

    enrs = _active_enrollments(school, source)
    by_class = defaultdict(list)
    for e in enrs.values():
        by_class[e.section.school_class_id].append(e)

    results = []
    with transaction.atomic():
        for raw_class_id, action in mappings.items():
            try:
                cls = Class.objects.get(pk=int(raw_class_id), school=school)
            except (Class.DoesNotExist, TypeError, ValueError):
                results.append({'class': raw_class_id, 'error': 'class not found'})
                continue
            students = by_class.get(cls.id, [])
            promoted = graduated = skipped_n = 0
            skips = []

            if action == 'graduate':
                for e in students:
                    StudentEnrollment.objects.filter(
                        school=school, session=source, student=e.student,
                    ).update(status=StudentEnrollment.Status.COMPLETED)
                    graduated += 1
            elif action == 'skip':
                skipped_n = len(students)
            elif str(action).startswith('promote:'):
                try:
                    target_class = Class.objects.get(
                        pk=int(str(action).split(':', 1)[1]), school=school)
                except (Class.DoesNotExist, TypeError, ValueError):
                    results.append({'class': cls.name,
                                    'error': 'target class not found'})
                    continue
                target_sections = list(
                    Section.objects.filter(school=school, school_class=target_class))
                if not target_sections:
                    results.append({'class': cls.name, 'error':
                        f'target class {target_class.name} has no sections — '
                        'create one first'})
                    continue
                by_name = {s.name: s for s in target_sections}
                for e in students:
                    dest = by_name.get(e.section.name, target_sections[0])
                    _, created = StudentEnrollment.objects.get_or_create(
                        school=school, student=e.student,
                        session=target_session, term=target_term,
                        defaults={'section': dest,
                                  'status': StudentEnrollment.Status.ACTIVE},
                    )
                    StudentEnrollment.objects.filter(
                        school=school, session=source, student=e.student,
                    ).update(status=StudentEnrollment.Status.COMPLETED)
                    if created:
                        promoted += 1
                    else:
                        skipped_n += 1
                        skips.append(f'{e.student.first_name} {e.student.last_name}')
            else:
                results.append({'class': cls.name, 'error': 'unknown action'})
                continue
            results.append({
                'class': cls.name, 'promoted': promoted,
                'graduated': graduated, 'skipped': skipped_n,
                'skipped_students': skips,
            })

    audit(request, 'session.rollover', source, {
        'target_session': target_session.name, 'target_term': target_term.name,
        'results': results,
    })
    return Response({'detail': 'Rollover complete.', 'results': results})
