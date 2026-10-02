"""
Role-based pending task reminder system.

Returns a list of pending tasks for the current user based on their role
and the current state of school data. Also triggers in-app notifications
for overdue tasks.
"""
from datetime import date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from core.utils import get_current_school
from notifications.models import InAppNotification


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_tasks(request):
    """Return a list of pending tasks for the current user."""
    user = request.user
    school = get_current_school(request)
    tasks = []

    if not school:
        return Response({'tasks': tasks})

    today = date.today()

    if user.role in (User.Roles.STAFF,):
        tasks += _teacher_tasks(user, school, today)
    elif user.role == User.Roles.SCHOOL_ADMIN:
        tasks += _admin_tasks(user, school, today)
    elif user.role == User.Roles.ACCOUNTANT:
        tasks += _accountant_tasks(user, school, today)
    elif user.role == User.Roles.PARENT:
        tasks += _parent_tasks(user, school, today)
    elif user.role == User.Roles.STUDENT:
        tasks += _student_tasks(user, school, today)

    # Create in-app notifications for overdue (high-priority) tasks
    for task in tasks:
        if task.get('priority') == 'high' and task.get('overdue'):
            _maybe_notify(user, school, task['title'], task['description'])

    return Response({'tasks': tasks, 'count': len(tasks)})


def _maybe_notify(user, school, title, message):
    """Create an in-app notification if not already sent today."""
    already = InAppNotification.objects.filter(
        recipient=user, school=school, title=title,
        created_at__date=date.today(),
    ).exists()
    if not already:
        InAppNotification.objects.create(
            recipient=user, school=school, title=title, message=message,
        )


def _teacher_tasks(user, school, today):
    tasks = []
    from homework.models import Assignment, Submission
    from attendance.models import Attendance

    # Ungraded submissions past due
    overdue_assignments = Assignment.objects.filter(
        school=school, teacher=user, due_date__lt=today, is_published=True,
    )
    for assignment in overdue_assignments:
        ungraded = Submission.objects.filter(
            school=school, assignment=assignment,
            status=Submission.Status.SUBMITTED,
        ).count()
        if ungraded > 0:
            tasks.append({
                'id': f'ungraded_{assignment.pk}',
                'title': f'Grade: {assignment.title}',
                'description': f'{ungraded} submission(s) awaiting grading for {assignment.school_class}',
                'type': 'grading',
                'priority': 'high',
                'overdue': True,
                'link': f'/homework/assignments/{assignment.pk}',
            })

    # Attendance not taken today
    if hasattr(user, 'staff_profile'):
        staff = user.staff_profile
        for cls in staff.assigned_classes.filter(school=school):
            already_taken = Attendance.objects.filter(
                school=school, school_class=cls, date=today,
            ).exists()
            if not already_taken:
                tasks.append({
                    'id': f'attendance_{cls.pk}',
                    'title': f'Take Attendance: {cls.name}',
                    'description': f"Today's attendance for {cls.name} has not been recorded.",
                    'type': 'attendance',
                    'priority': 'high',
                    'overdue': False,
                    'link': '/attendance',
                })

    return tasks


def _admin_tasks(user, school, today):
    tasks = []
    from admissions.models import Application

    pending_apps = Application.objects.filter(
        school=school, status=Application.Status.PENDING,
    ).count()
    if pending_apps > 0:
        tasks.append({
            'id': 'pending_admissions',
            'title': 'Pending Admissions',
            'description': f'{pending_apps} application(s) awaiting review.',
            'type': 'admissions',
            'priority': 'medium',
            'overdue': False,
            'link': '/admissions',
        })

    # Schools with unpublished report cards
    from gradebook.models import ReportCard
    draft_cards = ReportCard.objects.filter(
        school=school, status=ReportCard.Status.DRAFT,
    ).count()
    if draft_cards > 0:
        tasks.append({
            'id': 'draft_report_cards',
            'title': 'Draft Report Cards',
            'description': f'{draft_cards} report card(s) still in draft — publish before term end.',
            'type': 'academics',
            'priority': 'medium',
            'overdue': False,
            'link': '/results',
        })

    return tasks


def _accountant_tasks(user, school, today):
    tasks = []
    from finance.models import Invoice

    overdue_invoices = Invoice.objects.filter(
        school=school, due_date__lt=today,
        status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
    ).count()
    if overdue_invoices > 0:
        tasks.append({
            'id': 'overdue_invoices',
            'title': 'Overdue Invoices',
            'description': f'{overdue_invoices} invoice(s) are overdue. Follow up with parents.',
            'type': 'finance',
            'priority': 'high',
            'overdue': True,
            'link': '/finance/invoices',
        })

    draft_invoices = Invoice.objects.filter(school=school, status=Invoice.Status.DRAFT).count()
    if draft_invoices > 0:
        tasks.append({
            'id': 'unsent_invoices',
            'title': 'Unsent Invoices',
            'description': f'{draft_invoices} invoice(s) in draft — send them to parents.',
            'type': 'finance',
            'priority': 'medium',
            'overdue': False,
            'link': '/finance/invoices',
        })

    return tasks


def _parent_tasks(user, school, today):
    tasks = []
    if not hasattr(user, 'guardian_profile'):
        return tasks

    from finance.models import Invoice
    unpaid = Invoice.objects.filter(
        school=school,
        student__guardians__guardian=user.guardian_profile,
        status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL, Invoice.Status.OVERDUE],
    ).count()
    if unpaid > 0:
        tasks.append({
            'id': 'unpaid_fees',
            'title': 'Unpaid School Fees',
            'description': f'You have {unpaid} outstanding invoice(s). Please make payment.',
            'type': 'finance',
            'priority': 'high',
            'overdue': True,
            'link': '/fees',
        })

    return tasks


def _student_tasks(user, school, today):
    tasks = []
    if not hasattr(user, 'student_profile'):
        return tasks

    from homework.models import Assignment, Submission
    student = user.student_profile
    enrollments = student.enrollments.filter(school=school, status='active')
    classes = [e.section.school_class_id for e in enrollments.select_related('section__school_class')]

    overdue_hw = Assignment.objects.filter(
        school=school, school_class__in=classes,
        due_date__lt=today, is_published=True,
    ).exclude(
        submissions__student=student,
        submissions__status__in=[
            Submission.Status.SUBMITTED, Submission.Status.GRADED,
        ],
    ).distinct()

    for hw in overdue_hw:
        tasks.append({
            'id': f'overdue_hw_{hw.pk}',
            'title': f'Overdue: {hw.title}',
            'description': f'{hw.subject.name} assignment was due {hw.due_date}.',
            'type': 'homework',
            'priority': 'high',
            'overdue': True,
            'link': f'/homework',
        })

    return tasks
