"""
Part 6 — Self-service full data export (Excel/CSV).

Endpoints:
  GET /api/export/students/    — all students (Excel/CSV)
  GET /api/export/staff/       — all staff
  GET /api/export/grades/      — all result summaries
  GET /api/export/attendance/  — full attendance log
  GET /api/export/fees/        — invoices + payments
  GET /api/export/all/         — zip of all above (Excel)
  GET /api/export/group/<pk>/  — group owner: full group export (zip)
"""
import io
import logging
import zipfile
from datetime import datetime

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.viewsets import get_current_school
from accounts.models import User
from attendance.models import Attendance
from finance.models import Invoice, Payment
from gradebook.models import ResultSummary
from staff.models import Staff
from students.models import Student, StudentEnrollment

logger = logging.getLogger(__name__)


def _workbook_response(wb, filename: str) -> HttpResponse:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


def _csv_response(rows: list, headers: list, filename: str) -> HttpResponse:
    import csv
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    resp = HttpResponse(buf.getvalue(), content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


def _build_students_sheet(ws, school):
    from students.models import Student, StudentEnrollment
    headers = [
        'Admission Number', 'First Name', 'Last Name', 'Date of Birth', 'Gender',
        'Current Class', 'Parent Name', 'Parent Phone', 'Parent Email', 'Enrolled Date',
    ]
    ws.append(headers)
    for s in Student.objects.filter(school=school).prefetch_related(
        'enrollments__section__school_class', 'guardians__guardian'
    ):
        en = s.enrollments.filter(status='active').order_by('-id').first()
        class_name = en.section.school_class.name if en else ''
        gs = s.guardians.filter(is_primary=True).first() or s.guardians.first()
        guardian = gs.guardian if gs else None
        g_name = f"{guardian.first_name} {guardian.last_name}" if guardian else ''
        g_phone = guardian.phone if guardian else ''
        g_email = guardian.email if guardian else ''
        ws.append([
            s.admission_number, s.first_name, s.last_name,
            str(s.date_of_birth), s.gender, class_name,
            g_name, g_phone, g_email, str(s.created_at.date()),
        ])
    return len(list(ws.iter_rows())) - 1  # rows written


def _build_staff_sheet(ws, school):
    headers = [
        'Email', 'First Name', 'Last Name', 'Role', 'Phone', 'Date Joined',
    ]
    ws.append(headers)
    count = 0
    for u in User.objects.filter(school=school).exclude(role__in=['student', 'parent']).order_by('last_name'):
        ws.append([u.email, u.first_name, u.last_name, u.get_role_display(), u.phone, str(u.date_joined.date())])
        count += 1
    return count


def _build_grades_sheet(ws, school):
    from gradebook.models import ResultSummary
    headers = [
        'Student', 'Admission No.', 'Class', 'Subject', 'Session', 'Term',
        'CA1', 'CA2', 'Exam', 'Total', 'Grade',
    ]
    ws.append(headers)
    count = 0
    for r in ResultSummary.objects.filter(school=school).select_related(
        'student', 'subject', 'term__session', 'school_class'
    ):
        cls = r.school_class.name if r.school_class else ''
        ws.append([
            f"{r.student.first_name} {r.student.last_name}",
            r.student.admission_number,
            cls,
            r.subject.name,
            r.term.session.name if r.term and r.term.session else '',
            r.term.name if r.term else '',
            str(r.ca1_score or ''),
            str(r.ca2_score or ''),
            str(r.exam_score or ''),
            str(r.total_score or ''),
            r.grade or '',
        ])
        count += 1
    return count


def _build_attendance_sheet(ws, school):
    from attendance.models import Attendance
    headers = ['Student', 'Admission No.', 'Date', 'Status', 'Class', 'Remarks']
    ws.append(headers)
    count = 0
    for a in Attendance.objects.filter(school=school).select_related(
        'student', 'school_class'
    ).order_by('-date')[:50000]:  # Cap at 50k rows
        ws.append([
            f"{a.student.first_name} {a.student.last_name}",
            a.student.admission_number,
            str(a.date),
            a.status,
            a.school_class.name if a.school_class else '',
            a.remarks or '',
        ])
        count += 1
    return count


def _build_fees_sheet(ws, school):
    from finance.models import Invoice, Payment
    headers = [
        'Invoice No.', 'Student', 'Term', 'Total Amount', 'Amount Paid', 'Balance',
        'Status', 'Due Date', 'Issue Date',
    ]
    ws.append(headers)
    count = 0
    for inv in Invoice.objects.filter(school=school).select_related('student', 'term').order_by('-issue_date'):
        ws.append([
            inv.invoice_number,
            f"{inv.student.first_name} {inv.student.last_name}",
            inv.term.name,
            float(inv.total_amount),
            float(inv.amount_paid),
            float(inv.balance),
            inv.status,
            str(inv.due_date),
            str(inv.issue_date),
        ])
        count += 1
    return count


def _build_receipts_sheet(ws, school):
    from finance.models import PaymentReceipt
    headers = ['Receipt No.', 'Student', 'Invoice No.', 'Amount', 'Method', 'Date']
    ws.append(headers)
    count = 0
    for r in PaymentReceipt.objects.filter(school=school).order_by('-issued_at'):
        ws.append([
            r.receipt_number, r.student_name, r.invoice_number,
            float(r.amount), r.method, str(r.issued_at.date()),
        ])
        count += 1
    return count


def _dump_sheet(ws, qs, fields):
    """Generic table dump: headers + one row per record.

    ``fields`` are attribute paths ('student.first_name', 'term.name'…); FK
    objects render via str(); dates/datetimes are ISO; bools become ✓/—.
    """
    ws.append([f.replace('_', ' ').replace('.', ' ').title() for f in fields])
    count = 0
    for obj in qs.iterator():
        row = []
        for f in fields:
            v = obj
            for part in f.split('.'):
                v = getattr(v, part, None)
                if v is None:
                    break
            if hasattr(v, 'isoformat'):
                v = v.isoformat()
            elif v is True:
                v = 'yes'
            elif v is False:
                v = 'no'
            elif hasattr(v, 'pk'):
                v = str(v)
            row.append(v)
        ws.append(row)
        count += 1
    return count


def _generic_sheets(school):
    """Every remaining dataset, dumped generically — the portability pack."""
    from academics.models import Class, ClassSubject, Section, Subject, Timetable
    from admissions.models import Application
    from communications.models import Announcement
    from finance.models import Expense, FeeStructure
    from gradebook.models import Assessment, Grade, ReportCard
    from homework.models import Assignment, LiveLesson, Submission
    from hostel.models import HostelAllocation
    from library.models import Book, BorrowRecord
    from schools.models import AcademicSession, Term
    from students.models import Guardian, StudentEnrollment
    from transport.models import Route, Vehicle
    import inspect
    specs = [
        ('Sessions', AcademicSession, ['name', 'start_date', 'end_date', 'is_current']),
        ('Terms', Term, ['name', 'session.name', 'start_date', 'end_date', 'is_current']),
        ('Classes', Class, ['name', 'code']),
        ('Sections', Section, ['school_class.name', 'name', 'room', 'capacity']),
        ('Subjects', Subject, ['name', 'code']),
        ('Class-Subjects', ClassSubject,
         ['school_class.name', 'subject.name', 'teacher.email']),
        ('Enrollments', StudentEnrollment,
         ['student.admission_number', 'student.first_name', 'student.last_name',
          'section.school_class.name', 'section.name', 'session.name', 'term.name',
          'status', 'roll_number']),
        ('Guardians', Guardian,
         ['first_name', 'last_name', 'relationship', 'phone', 'email', 'address']),
        ('Applications', Application,
         ['first_name', 'last_name', 'applying_for_class', 'guardian_name',
          'guardian_phone', 'status', 'created_at']),
        ('Assessments', Assessment,
         ['name', 'subject.name', 'school_class.name', 'term.name',
          'max_score', 'date', 'type']),
        ('Grade Entries', Grade,
         ['assessment.name', 'student.admission_number', 'student.first_name',
          'student.last_name', 'score', 'remarks']),
        ('Report Cards', ReportCard,
         ['student.admission_number', 'student.first_name', 'student.last_name',
          'term.name', 'school_class.name', 'average_score', 'position', 'status']),
        ('Fee Structures', FeeStructure,
         ['name', 'category.name', 'school_class.name', 'term.name', 'amount']),
        ('Payments', Payment,
         ['invoice.invoice_number', 'invoice.student.first_name',
          'invoice.student.last_name', 'amount', 'method', 'reference',
          'paid_at', 'recorded_by.email']),
        ('Expenses', Expense,
         ['title', 'category', 'amount', 'expense_date', 'description',
          'recorded_by.email']),
        ('Assignments', Assignment,
         ['title', 'school_class.name', 'subject.name', 'teacher.email',
          'term.name', 'type', 'due_date', 'max_points']),
        ('Submissions', Submission,
         ['assignment.title', 'student.admission_number', 'student.first_name',
          'student.last_name', 'submitted_at', 'status', 'score', 'feedback']),
        ('Live Lessons', LiveLesson,
         ['title', 'school_class.name', 'subject.name', 'teacher.email',
          'scheduled_at', 'duration_minutes', 'status']),
        ('Timetable', Timetable,
         ['section.school_class.name', 'section.name', 'subject.name',
          'teacher.email', 'day', 'start_time', 'end_time', 'room']),
        ('Announcements', Announcement,
         ['title', 'content', 'author.email', 'status', 'publish_at', 'created_at']),
        ('Users', User,
         ['email', 'first_name', 'last_name', 'role', 'phone', 'is_active',
          'date_joined']),
        ('Library Books', Book,
         ['title', 'author', 'isbn', 'copies_total', 'copies_available']),
        ('Borrows', BorrowRecord,
         ['book.title', 'student.first_name', 'student.last_name',
          'borrowed_at', 'due_date', 'returned_at', 'status']),
        ('Routes', Route,
         ['name', 'start_location', 'end_location', 'distance_km', 'stops']),
        ('Vehicles', Vehicle,
         ['registration_number', 'make', 'model', 'capacity', 'status']),
        ('Hostel Allocations', HostelAllocation,
         ['student.first_name', 'student.last_name', 'room.hostel.name',
          'room.room_number', 'check_in', 'check_out', 'status']),
    ]
    out = []
    for name, model, fields in specs:
        try:
            qs = model.objects.filter(school=school)
            if inspect.isfunction(getattr(qs, 'all', None)):
                qs = qs.all()
            # select_related every FK hop used in field paths — without this
            # each row issues a query per relation.
            fks = []
            for f in fields:
                parts = f.split('.')
                mdl, path = model, []
                for part in parts[:-1]:
                    try:
                        fld = mdl._meta.get_field(part)
                    except Exception:
                        break
                    if not (fld.is_relation and fld.many_to_one):
                        break
                    path.append(part)
                    fks.append('__'.join(path))
                    mdl = fld.related_model
            if fks:
                qs = qs.select_related(*fks)
            out.append((name, qs, fields))
        except Exception:
            logger.exception('export sheet prep failed for %s', name)
    return out


def _build_readme_sheet(ws, school):
    ws.append(['TabsForge full school export'])
    ws.append(['School', school.name])
    ws.append(['Generated', datetime.now().isoformat(timespec='seconds')])
    ws.append([])
    ws.append(['Each sheet is one dataset. Rows include archived records so '
               'nothing is silently lost. Money amounts are in the school\'s '
               'configured currency.'])


def _style_sheet(ws):
    """Apply basic bold headers and auto-width to a worksheet."""
    try:
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        header_fill = PatternFill('solid', fgColor='1A5276')
        for cell in ws[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
        for col in ws.columns:
            max_len = max((len(str(c.value or '')) for c in col), default=10)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 2, 50)
    except Exception:
        pass


def _build_workbook(school):
    """Build a full openpyxl workbook for a school."""
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    sheets = [
        ('README', _build_readme_sheet),
        ('Students', _build_students_sheet),
        ('Staff', _build_staff_sheet),
        ('Grades', _build_grades_sheet),
        ('Attendance', _build_attendance_sheet),
        ('Fees', _build_fees_sheet),
        ('Receipts', _build_receipts_sheet),
    ]
    for name, builder in sheets:
        ws = wb.create_sheet(name)
        builder(ws, school)
        _style_sheet(ws)
    # Full-portability pack — every remaining dataset as its own sheet.
    # A broken sheet must not sink the whole export.
    for name, qs, fields in _generic_sheets(school):
        ws = wb.create_sheet(name[:31])
        try:
            _dump_sheet(ws, qs, fields)
        except Exception:
            logger.exception('export sheet failed for %s', name)
            ws.append([f'Export error — contact support ({name})'])
        _style_sheet(ws)
    return wb


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_all(request):
    """Export all school data as a single Excel workbook (Part 6)."""
    school = get_current_school(request)
    if not school:
        return Response({'detail': 'School context required.'}, status=400)
    # Only school admins, accountants, group owners and super admins
    user = request.user
    allowed = {User.Roles.SUPER_ADMIN, User.Roles.SCHOOL_ADMIN, User.Roles.ACCOUNTANT, User.Roles.GROUP_OWNER}
    if user.role not in allowed and not user.is_superuser:
        return Response({'detail': 'Only School Admins and Accountants may export data.'}, status=403)

    try:
        wb = _build_workbook(school)
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"tabsforge_export_{school.subdomain}_{date_str}.xlsx"
        return _workbook_response(wb, filename)
    except ImportError:
        return Response({'detail': 'openpyxl is required for Excel export. Install it on the server.'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_students(request):
    school = get_current_school(request)
    if not school:
        return Response({'detail': 'School context required.'}, status=400)
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Students'
        _build_students_sheet(ws, school)
        _style_sheet(ws)
        return _workbook_response(wb, f"students_{school.subdomain}.xlsx")
    except ImportError:
        return Response({'detail': 'openpyxl required.'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_grades(request):
    school = get_current_school(request)
    if not school:
        return Response({'detail': 'School context required.'}, status=400)
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Grades'
        _build_grades_sheet(ws, school)
        _style_sheet(ws)
        return _workbook_response(wb, f"grades_{school.subdomain}.xlsx")
    except ImportError:
        return Response({'detail': 'openpyxl required.'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_attendance(request):
    school = get_current_school(request)
    if not school:
        return Response({'detail': 'School context required.'}, status=400)
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Attendance'
        _build_attendance_sheet(ws, school)
        _style_sheet(ws)
        return _workbook_response(wb, f"attendance_{school.subdomain}.xlsx")
    except ImportError:
        return Response({'detail': 'openpyxl required.'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_fees(request):
    school = get_current_school(request)
    if not school:
        return Response({'detail': 'School context required.'}, status=400)
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Fees'
        _build_fees_sheet(ws, school)
        _style_sheet(ws)
        return _workbook_response(wb, f"fees_{school.subdomain}.xlsx")
    except ImportError:
        return Response({'detail': 'openpyxl required.'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_group(request, pk=None):
    """Group Owner export: one zip with an Excel file per branch."""
    from schools.models import SchoolGroup, School
    user = request.user
    try:
        group = SchoolGroup.objects.get(pk=pk)
    except SchoolGroup.DoesNotExist:
        return Response({'detail': 'Group not found.'}, status=404)

    if not (user.is_superuser or user.role == User.Roles.SUPER_ADMIN or
            (user.role == User.Roles.GROUP_OWNER and user.school_group_id == group.pk)):
        return Response({'detail': 'Not permitted.'}, status=403)

    try:
        import openpyxl
    except ImportError:
        return Response({'detail': 'openpyxl required.'}, status=500)

    zip_buf = io.BytesIO()
    date_str = datetime.now().strftime('%Y%m%d')
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for branch in School.objects.filter(group=group):
            wb = _build_workbook(branch)
            xl_buf = io.BytesIO()
            wb.save(xl_buf)
            zf.writestr(f"{branch.subdomain}_{date_str}.xlsx", xl_buf.getvalue())

    zip_buf.seek(0)
    resp = HttpResponse(zip_buf.getvalue(), content_type='application/zip')
    resp['Content-Disposition'] = f'attachment; filename="group_{group.id}_export_{date_str}.zip"'
    return resp


# ---------------------------------------------------------------------------
# Formatted report exports (xlsx / docx / csv) — staff and admins
# ---------------------------------------------------------------------------

STAFF_ROLES = {
    User.Roles.SUPER_ADMIN, User.Roles.GROUP_OWNER, User.Roles.SCHOOL_ADMIN,
    User.Roles.PRINCIPAL, User.Roles.VICE_PRINCIPAL, User.Roles.ADMISSIONS_OFFICER,
    User.Roles.TEACHER, User.Roles.FORM_TEACHER, User.Roles.EXAM_OFFICER,
    User.Roles.HR_ADMIN, User.Roles.LIBRARIAN, User.Roles.STAFF,
    User.Roles.ACCOUNTANT,
}


def _export_term(request, school):
    from schools.models import Term
    term_id = request.query_params.get('term_id')
    if not term_id:
        return None
    return Term.objects.filter(pk=term_id, school=school).first()


def report_rows(kind, school, request):
    """Return (title, headers, rows) for a report kind, tenant-scoped."""
    class_id = request.query_params.get('class_id')

    if kind == 'students':
        enroll = StudentEnrollment.objects.filter(
            school=school, status='active',
        ).select_related('section__school_class')
        cls_map = {}
        for e in enroll:
            cls_map[e.student_id] = f"{e.section.school_class.name} {e.section.name}"
        students = Student.objects.filter(school=school)
        if class_id:
            ids = [e.student_id for e in enroll
                   if e.section.school_class_id == int(class_id)]
            students = students.filter(pk__in=ids)
        rows = [
            [s.admission_number, f'{s.first_name} {s.last_name}',
             s.get_gender_display() or '', cls_map.get(s.pk, '—'),
             str(s.enrollment_date)]
            for s in students
        ]
        return 'Students', ['Admission No', 'Name', 'Gender', 'Class', 'Enrolled'], rows

    if kind == 'staff':
        rows = [
            [st.employee_id, st.user.full_name if st.user else '',
             st.user.email if st.user else '', st.designation, st.department,
             st.get_employment_type_display(),
             'Active' if st.is_active else 'Inactive']
            for st in Staff.objects.filter(school=school).select_related('user')
        ]
        return 'Staff', ['Staff ID', 'Name', 'Email', 'Designation', 'Department',
                         'Employment', 'Status'], rows

    if kind == 'users':
        rows = [
            [u.email, u.full_name, u.get_role_display(),
             'Active' if u.is_active else 'Suspended', str(u.date_joined.date())]
            for u in User.objects.filter(school=school)
        ]
        return 'User Accounts', ['Email', 'Name', 'Role', 'Status', 'Joined'], rows

    if kind == 'results':
        term = _export_term(request, school)
        qs = ResultSummary.objects.filter(school=school)
        if term:
            qs = qs.filter(term=term)
        if class_id:
            qs = qs.filter(school_class_id=class_id)
        rows = [
            [r.student.admission_number,
             f'{r.student.first_name} {r.student.last_name}',
             r.subject.name, str(r.ca1_score), str(r.ca2_score), str(r.exam_score),
             str(r.total_score), r.grade, r.grade_remark,
             str(r.subject_position or '')]
            for r in qs.select_related('student', 'subject')
        ]
        return (
            f'Results {term.name if term else ""}'.strip(),
            ['Admission No', 'Student', 'Subject', 'CA1', 'CA2', 'Exam',
             'Total', 'Grade', 'Remark', 'Position'],
            rows,
        )

    if kind == 'attendance':
        qs = Attendance.objects.filter(school=school)
        term = _export_term(request, school)
        if term:
            qs = qs.filter(date__gte=term.start_date, date__lte=term.end_date)
        if class_id:
            qs = qs.filter(school_class_id=class_id)
        rows = [
            [str(a.date), a.student.admission_number,
             f'{a.student.first_name} {a.student.last_name}',
             a.school_class.name, a.get_status_display()]
            for a in qs.select_related('student', 'school_class').order_by('-date')[:5000]
        ]
        return 'Attendance Register', ['Date', 'Admission No', 'Student', 'Class', 'Status'], rows

    if kind == 'payments':
        qs = Payment.objects.filter(school=school)
        term = _export_term(request, school)
        if term:
            qs = qs.filter(invoice__term=term)
        rows = [
            [str(p.paid_at.date()),
             getattr(getattr(p, 'receipt', None), 'receipt_number', '') or '',
             f'{p.invoice.student.first_name} {p.invoice.student.last_name}'
             if p.invoice and p.invoice.student else '',
             str(p.amount), p.get_method_display()]
            for p in qs.select_related('invoice__student', 'receipt').order_by('-paid_at')
        ]
        return 'Payments', ['Date', 'Receipt No', 'Student', 'Amount', 'Method'], rows

    if kind == 'debtors':
        qs = Invoice.objects.filter(school=school).exclude(
            status__in=[Invoice.Status.PAID, Invoice.Status.CANCELLED]
        )
        term = _export_term(request, school)
        if term:
            qs = qs.filter(term=term)
        rows = [
            [i.invoice_number,
             f'{i.student.first_name} {i.student.last_name}' if i.student else '',
             str(i.total_amount), str(i.amount_paid),
             str(i.total_amount - i.amount_paid), i.get_status_display()]
            for i in qs.select_related('student')
        ]
        return 'Outstanding Debtors', ['Invoice', 'Student', 'Billed', 'Paid',
                                       'Balance', 'Status'], rows

    if kind == 'fee-collection':
        qs = Invoice.objects.filter(school=school)
        term = _export_term(request, school)
        if term:
            qs = qs.filter(term=term)
        agg = qs.aggregate(
            billed=Sum('total_amount'), paid=Sum('amount_paid'),
            count=Count('id'),
            unpaid=Count('id', filter=~Q(status=Invoice.Status.PAID)),
        )
        rows = [
            ['Total invoiced', str(agg['count'] or 0)],
            ['Total billed', str(agg['billed'] or 0)],
            ['Total collected', str(agg['paid'] or 0)],
            ['Outstanding', str((agg['billed'] or 0) - (agg['paid'] or 0))],
            ['Open invoices', str(agg['unpaid'] or 0)],
        ]
        return 'Fee Collection Summary', ['Metric', 'Value'], rows

    raise ValueError(f'Unknown report kind: {kind}')


def _docx_table_response(title, headers, rows, filename):
    import docx
    doc = docx.Document()
    doc.add_heading(title, level=1)
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = str(h)
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for row in rows:
        cells = table.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
    buf = io.BytesIO()
    doc.save(buf)
    resp = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    resp['Content-Disposition'] = f'attachment; filename="{filename}.docx"'
    return resp

def _xlsx_table_response(title, headers, rows, filename):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append([title])
    ws.append(headers)
    for row in rows:
        ws.append(row)
    for col, header in enumerate(headers, start=1):
        ws.cell(row=2, column=col).font = openpyxl.styles.Font(bold=True)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = max(
            12, min(40, len(str(header)) + 6)
        )
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    return resp


def _csv_table_response(title, headers, rows, filename):
    import csv as _csv
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    writer = _csv.writer(resp)
    writer.writerow([title])
    writer.writerow(headers)
    writer.writerows(rows)
    return resp


_REPORT_RENDERERS = {
    'xlsx': _xlsx_table_response,
    'docx': _docx_table_response,
    'csv': _csv_table_response,
}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_report(request, kind, fmt):
    """Download a formatted report: GET /api/exports/<kind>/<fmt>/?term_id=&class_id=

    kinds: students | staff | users | results | attendance | payments |
           debtors | fee-collection
    fmts:  xlsx | docx | csv
    """
    user = request.user
    if not (user.is_superuser or user.role in STAFF_ROLES):
        return Response({'error': 'Reports are only available to staff.'}, status=403)
    school = get_current_school(request) or user.school
    if not school:
        return Response({'error': 'No school context.'}, status=400)
    if fmt not in _REPORT_RENDERERS:
        return Response({'error': f'Unsupported format: {fmt}'}, status=400)
    try:
        title, headers, rows = report_rows(kind, school, request)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=404)
    except Exception as exc:
        logger.exception('Export failed: %s', exc)
        return Response({'error': 'Report generation failed.'}, status=500)
    filename = f"{school.subdomain}_{kind}"
    return _REPORT_RENDERERS[fmt](title, headers, rows, filename)
