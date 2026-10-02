"""Role-aware dashboard and analytics endpoints."""
from django.db.models import Avg, Count, Sum
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from academics.models import Class
from accounts.models import User
from api.permissions import IsSuperAdmin
from attendance.models import Attendance
from core.utils import get_current_school
from finance.models import Expense, Invoice, Payment
from gradebook.models import Grade
from schools.models import School
from staff.models import Staff
from students.models import GuardianStudent, Student


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    """Return KPIs and onboarding checklist for the current user's school."""
    user = request.user
    school = get_current_school(request) or user.school

    if user.is_superuser or user.role == user.Roles.SUPER_ADMIN:
        return Response({
            'kpis': {
                'total_schools': School.objects.count(),
                'active_schools': School.objects.filter(status=School.Status.ACTIVE).count(),
                'pending_approvals': School.objects.filter(status=School.Status.ONBOARDING).count(),
                'total_users': User.objects.count(),
            }
        })

    if not school:
        return Response({'detail': 'No school assigned.'}, status=status.HTTP_400_BAD_REQUEST)

    students = Student.objects.filter(school=school)
    staff = Staff.objects.filter(school=school)
    invoices = Invoice.objects.filter(school=school)
    payments = Payment.objects.filter(school=school)

    checklist = {
        'add_classes': Class.objects.filter(school=school).exists(),
        'add_staff': staff.exists(),
        'add_students': students.exists(),
        'set_fees': invoices.exists(),
        'customize_branding': school.primary_color != '#125A0F' or bool(school.logo),
        'invite_parents': GuardianStudent.objects.filter(school=school).exists(),
    }
    completed = sum(1 for v in checklist.values() if v)

    avg_grade = Grade.objects.filter(school=school).aggregate(avg=Avg('score'))['avg']
    attendance_rate = Attendance.objects.filter(school=school, status='present').count()
    total_attendance = Attendance.objects.filter(school=school).count()
    attendance_pct = (attendance_rate / total_attendance * 100) if total_attendance else 0

    billed = float(invoices.aggregate(total=Sum('total_amount'))['total'] or 0)
    collected = float(payments.aggregate(total=Sum('amount'))['total'] or 0)
    outstanding = billed - float(
        invoices.aggregate(total=Sum('amount_paid'))['total'] or 0
    )
    open_invoices = invoices.exclude(
        status__in=[Invoice.Status.PAID, Invoice.Status.CANCELLED]
    ).count()
    expenses_total = float(
        Expense.objects.filter(school=school).aggregate(total=Sum('amount'))['total'] or 0
    )

    return Response({
        'kpis': {
            'total_students': students.count(),
            'total_staff': staff.count(),
            'attendance_today': round(attendance_pct, 1),
            'fees_collected': collected,
            'outstanding_fees': outstanding,
            'total_billed': billed,
            'open_invoices': open_invoices,
            'collection_rate': round(collected / billed * 100, 1) if billed else 0,
            'expenses_total': expenses_total,
            'net_balance': round(collected - expenses_total, 2),
            'average_grade': round(avg_grade or 0, 1),
        },
        'checklist': checklist,
        'checklist_progress': {
            'completed': completed,
            'total': len(checklist),
            'percent': round((completed / len(checklist)) * 100, 0) if checklist else 0,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def analytics_view(request):
    """Platform-wide analytics for super admins."""
    return Response({
        'kpis': {
            'total_schools': School.objects.count(),
            'active_schools': School.objects.filter(status=School.Status.ACTIVE).count(),
            'onboarding_schools': School.objects.filter(status=School.Status.ONBOARDING).count(),
            'suspended_schools': School.objects.filter(status=School.Status.SUSPENDED).count(),
            'total_users': User.objects.count(),
            'total_students': Student.objects.count(),
            'total_staff': Staff.objects.count(),
            'total_payments': float(Payment.objects.aggregate(total=Sum('amount'))['total'] or 0),
        },
        'schools_by_tier': {
            t[0]: School.objects.filter(tier=t[0]).count()
            for t in School.Tiers.choices
        },
    })
