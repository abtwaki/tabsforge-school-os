"""
PDF report generation for TabsForge School OS.

Uses ReportLab to generate downloadable PDF reports for:
- Student report cards
- Fee collection summary
- Outstanding debtors
- Income & expenditure statement
- Levy breakdown
- Per-student fee ledger
"""
import io
import os
from datetime import date

from django.conf import settings
from django.http import HttpResponse

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Brand palette
GREEN = colors.HexColor('#125A0F') if REPORTLAB_AVAILABLE else None
GOLD = colors.HexColor('#D6A20D') if REPORTLAB_AVAILABLE else None
NAVY = colors.HexColor('#0B367B') if REPORTLAB_AVAILABLE else None
LIGHT_GRAY = colors.HexColor('#F5F5F5') if REPORTLAB_AVAILABLE else None


def _require_reportlab():
    if not REPORTLAB_AVAILABLE:
        raise ImportError('reportlab is required for PDF generation. Install it with: pip install reportlab')


def _get_pdf_response(filename):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


_TF_MARK = settings.BASE_DIR / 'core' / 'assets' / 'tabsforge-logo-mark.png'


def _school_header(story, school, title, styles):
    """Add school logo/name header to a story."""
    bold = styles['h1']
    text = [Paragraph(school.name.upper(), bold)]
    if school.address:
        text.append(Paragraph(school.address, styles['Normal']))
    text.append(Paragraph(title, styles['h2']))
    logo_path = ''
    try:
        if school.logo and os.path.exists(school.logo.path):
            logo_path = school.logo.path
    except (ValueError, OSError):
        logo_path = ''
    if logo_path:
        logo = Image(logo_path, width=1.8 * cm, height=1.8 * cm, kind='proportional')
        header = Table([[logo, text]], colWidths=[2.2 * cm, None])
        header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header)
    else:
        story.extend(text)
    story.append(HRFlowable(width='100%', thickness=2, color=GREEN))
    story.append(Spacer(1, 0.3 * cm))


def _tf_footer(canvas, doc):
    """'Powered by TabsForge' watermark footer on every page."""
    canvas.saveState()
    width, _ = A4
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 0.7 * cm, 'Powered by TabsForge School OS')
    if _TF_MARK.exists():
        canvas.drawImage(str(_TF_MARK), width - 3 * cm, 0.45 * cm,
                         width=0.7 * cm, height=0.7 * cm,
                         preserveAspectRatio=True, mask='auto')
    canvas.restoreState()


def generate_report_card_pdf(report_card):
    """Generate a PDF report card for a single student."""
    _require_reportlab()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []
    school = report_card.school
    student = report_card.student
    term = report_card.term

    # Header
    _school_header(story, school, 'STUDENT REPORT CARD', styles)

    # School's adopted report format config (from uploaded template / settings)
    cfg = school.report_config or {}
    show_position = cfg.get('show_position', True)
    show_class_size = cfg.get('show_class_size', True)
    show_grade_points = cfg.get('show_grade_points', False)
    show_teacher_comment = cfg.get('show_teacher_comment', True)
    show_principal_comment = cfg.get('show_principal_comment', True)
    show_attendance = cfg.get('show_attendance_summary', True)

    # Student info table
    position_text = ''
    if show_position:
        position_text = str(report_card.position or '')
        if show_class_size and report_card.class_size:
            position_text += f" of {report_card.class_size}"
    info = [
        ['Name:', student.first_name + ' ' + student.last_name,
         'Admission No:', student.admission_number],
        ['Class:', str(report_card.school_class or ''), 'Term:', str(term.name)],
        ['Session:', str(term.session.name), 'Position:', position_text],
        ['Average:', f"{report_card.average_score or 0:.1f}%",
         'Class Avg:', f"{report_card.class_average:.1f}%" if report_card.class_average is not None else '—'],
    ]
    if show_attendance:
        # Prefer the snapshot captured at compute time; fall back to a live
        # count for cards generated before attendance tracking was added.
        if report_card.days_open is not None:
            present, total_days = report_card.days_present or 0, report_card.days_open
        else:
            from attendance.models import Attendance
            att = Attendance.objects.filter(school=school, student=student,
                                            date__gte=term.start_date, date__lte=term.end_date)
            total_days = att.count()
            present = att.filter(status__in=['present', 'late']).count()
        info.append(['Attendance:', f"{present}/{total_days} days", '', ''])
    t = Table(info, colWidths=[3 * cm, 6 * cm, 3 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, LIGHT_GRAY]),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * cm))

    # Subject results
    story.append(Paragraph('SUBJECT RESULTS', styles['h3']))

    # Gather results
    from gradebook.models import ResultSummary
    results = ResultSummary.objects.filter(
        school=school, student=student, term=term,
    ).select_related('subject').order_by('subject__name')

    header_row = ['Subject', 'CA1', 'CA2', 'Exam', 'Total', 'Grade', 'Remark']
    col_widths = [5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.8 * cm, 1.5 * cm, 2.5 * cm]
    if show_grade_points:
        header_row.append('Points')
        col_widths.append(1.4 * cm)
    if show_position:
        header_row.append('Position')
        col_widths.append(2 * cm)
    data = [header_row]
    for r in results:
        row = [
            r.subject.name,
            f"{r.ca1_score:.0f}",
            f"{r.ca2_score:.0f}",
            f"{r.exam_score:.0f}",
            f"{r.total_score:.1f}",
            r.grade,
            r.grade_remark,
        ]
        if show_grade_points:
            row.append(str(r.grade_points))
        if show_position:
            row.append(str(r.subject_position or ''))
        data.append(row)

    t2 = Table(data, colWidths=col_widths)
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.4 * cm))

    # Affective & psychomotor trait ratings (1–5) — the Nigerian report card
    # behaviour/skills section.
    traits = list(report_card.trait_ratings.all())
    if traits:
        story.append(Paragraph('BEHAVIOUR &amp; SKILLS (rated 1 – 5)', styles['h3']))
        groups = [
            ('AFFECTIVE TRAITS', [t for t in traits if t.category == 'affective']),
            ('PSYCHOMOTOR SKILLS', [t for t in traits if t.category == 'psychomotor']),
        ]
        for heading, group in groups:
            if not group:
                continue
            tdata = [[heading, 'Rating (1–5)']] + [[t.trait, str(t.rating)] for t in group]
            tt = Table(tdata, colWidths=[11 * cm, 5 * cm])
            tt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), LIGHT_GRAY),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ]))
            story.append(tt)
            story.append(Spacer(1, 0.25 * cm))

    # Comments
    if show_teacher_comment and report_card.teacher_comments:
        story.append(Paragraph(f"<b>Class Teacher's Comment:</b> {report_card.teacher_comments}", styles['Normal']))
    if show_principal_comment and report_card.principal_comments:
        story.append(Paragraph(f"<b>Principal's Comment:</b> {report_card.principal_comments}", styles['Normal']))
    if report_card.next_term_begins:
        story.append(Paragraph(f"<b>Next Term Begins:</b> {report_card.next_term_begins:%d %B %Y}", styles['Normal']))

    # Signature lines per the school's adopted format
    signature_labels = cfg.get('signature_labels') or ['Class Teacher', 'Principal']
    if signature_labels:
        story.append(Spacer(1, 0.8 * cm))
        sig_table = Table(
            [['_' * 22, label] for label in signature_labels],
            colWidths=[8 * cm, 8 * cm],
        )
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 18),
        ]))
        story.append(sig_table)

    story.append(Spacer(1, 0.6 * cm))
    footer_note = cfg.get('footer_note') or 'Powered by TabsForge School OS'
    story.append(Paragraph(f'<i>{footer_note}</i>',
                            ParagraphStyle('watermark', fontSize=8, textColor=colors.grey)))

    doc.build(story, onFirstPage=_tf_footer, onLaterPages=_tf_footer)
    buf.seek(0)
    return buf.getvalue()


def generate_fee_collection_summary(school, term):
    """PDF: Fee Collection Summary for a term."""
    _require_reportlab()
    from finance.models import Invoice, Payment
    from django.db.models import Sum

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []
    _school_header(story, school, f'FEE COLLECTION SUMMARY — {term.name}', styles)

    invoices = Invoice.objects.filter(school=school, term=term).select_related('student')
    total_billed = sum(i.total_amount for i in invoices)
    total_collected = sum(i.amount_paid for i in invoices)
    total_outstanding = total_billed - total_collected

    summary = [
        ['Total Invoiced', f'₦{total_billed:,.2f}'],
        ['Total Collected', f'₦{total_collected:,.2f}'],
        ['Outstanding Balance', f'₦{total_outstanding:,.2f}'],
    ]
    ts = Table(summary, colWidths=[8 * cm, 8 * cm])
    ts.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [LIGHT_GRAY, colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(ts)
    story.append(Spacer(1, 0.5 * cm))

    # Per-status breakdown
    story.append(Paragraph('Status Breakdown', styles['h3']))
    from finance.models import Invoice
    status_data = [['Status', 'Count', 'Amount']]
    for status in Invoice.Status:
        qs = invoices.filter(status=status.value)
        count = qs.count()
        amount = sum(i.total_amount for i in qs)
        if count:
            status_data.append([status.label, str(count), f'₦{amount:,.2f}'])
    t2 = Table(status_data, colWidths=[6 * cm, 4 * cm, 7 * cm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f'Generated: {date.today():%d %B %Y}', styles['Normal']))
    story.append(Paragraph('<i>Powered by TabsForge School OS</i>',
                            ParagraphStyle('wm', fontSize=8, textColor=colors.grey)))

    doc.build(story, onFirstPage=_tf_footer, onLaterPages=_tf_footer)
    buf.seek(0)
    return buf.getvalue()


def generate_debtors_report(school, term):
    """PDF: Outstanding Debtors Report."""
    _require_reportlab()
    from finance.models import Invoice

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []
    _school_header(story, school, f'OUTSTANDING DEBTORS REPORT — {term.name}', styles)

    debtors = Invoice.objects.filter(
        school=school, term=term, status__in=['sent', 'partial', 'overdue'],
    ).select_related('student').order_by('-total_amount')

    data = [['Student', 'Adm. No', 'Total Billed', 'Paid', 'Balance', 'Status']]
    for inv in debtors:
        data.append([
            inv.student.first_name + ' ' + inv.student.last_name,
            inv.student.admission_number,
            f'₦{inv.total_amount:,.2f}',
            f'₦{inv.amount_paid:,.2f}',
            f'₦{inv.balance:,.2f}',
            inv.get_status_display(),
        ])

    col_widths = [4 * cm, 2.5 * cm, 3 * cm, 3 * cm, 3 * cm, 2.5 * cm]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
    ]))
    story.append(t)
    total_outstanding = sum(inv.balance for inv in debtors)
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f'<b>Total Outstanding: ₦{total_outstanding:,.2f}</b>', styles['Normal']))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f'Generated: {date.today():%d %B %Y}', styles['Normal']))
    story.append(Paragraph('<i>Powered by TabsForge School OS</i>',
                            ParagraphStyle('wm', fontSize=8, textColor=colors.grey)))

    doc.build(story, onFirstPage=_tf_footer, onLaterPages=_tf_footer)
    buf.seek(0)
    return buf.getvalue()


def generate_income_expenditure(school, term):
    """PDF: Income & Expenditure Statement."""
    _require_reportlab()
    from finance.models import Payment, Expense

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []
    _school_header(story, school, f'INCOME & EXPENDITURE — {term.name}', styles)

    # Income = all payments made in this term
    payments = Payment.objects.filter(school=school, invoice__term=term)
    total_income = sum(p.amount for p in payments)

    # Expenses
    expenses = Expense.objects.filter(school=school, term=term).order_by('category')
    total_expense = sum(e.amount for e in expenses)
    surplus = total_income - total_expense

    story.append(Paragraph('INCOME', styles['h3']))
    inc_data = [['Description', 'Amount'], ['Fee collections received', f'₦{total_income:,.2f}']]
    t = Table(inc_data, colWidths=[12 * cm, 6 * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph('EXPENDITURE', styles['h3']))
    exp_data = [['Category', 'Description', 'Amount']]
    for e in expenses:
        exp_data.append([e.get_category_display(), e.title, f'₦{e.amount:,.2f}'])
    if not expenses:
        exp_data.append(['—', 'No expenses recorded', '₦0.00'])

    t2 = Table(exp_data, colWidths=[4 * cm, 9 * cm, 5 * cm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.3 * cm))

    colour = GREEN if surplus >= 0 else colors.red
    story.append(Paragraph(f'<b>Net Surplus / (Deficit): ₦{surplus:,.2f}</b>',
                            ParagraphStyle('surplus', fontSize=11, textColor=colour)))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f'Generated: {date.today():%d %B %Y}', styles['Normal']))
    story.append(Paragraph('<i>Powered by TabsForge School OS</i>',
                            ParagraphStyle('wm', fontSize=8, textColor=colors.grey)))

    doc.build(story, onFirstPage=_tf_footer, onLaterPages=_tf_footer)
    buf.seek(0)
    return buf.getvalue()


def generate_student_fee_ledger(school, student, term=None):
    """PDF: Per-student fee ledger."""
    _require_reportlab()
    from finance.models import Invoice

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    styles = getSampleStyleSheet()
    story = []
    _school_header(story, school, 'STUDENT FEE LEDGER', styles)

    story.append(Paragraph(f"<b>Student:</b> {student.first_name} {student.last_name} "
                            f"({student.admission_number})", styles['Normal']))
    story.append(Spacer(1, 0.3 * cm))

    qs = Invoice.objects.filter(school=school, student=student).select_related('term')
    if term:
        qs = qs.filter(term=term)
    qs = qs.order_by('term__start_date', '-issue_date')

    data = [['Invoice #', 'Term', 'Billed', 'Paid', 'Balance', 'Status']]
    for inv in qs:
        data.append([
            inv.invoice_number,
            inv.term.name,
            f'₦{inv.total_amount:,.2f}',
            f'₦{inv.amount_paid:,.2f}',
            f'₦{inv.balance:,.2f}',
            inv.get_status_display(),
        ])

    col_widths = [3.5 * cm, 3.5 * cm, 3 * cm, 3 * cm, 3 * cm, 2.5 * cm]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
    ]))
    story.append(t)

    total_balance = sum(inv.balance for inv in qs)
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f'<b>Total Outstanding: ₦{total_balance:,.2f}</b>', styles['Normal']))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f'Generated: {date.today():%d %B %Y}', styles['Normal']))
    story.append(Paragraph('<i>Powered by TabsForge School OS</i>',
                            ParagraphStyle('wm', fontSize=8, textColor=colors.grey)))

    doc.build(story, onFirstPage=_tf_footer, onLaterPages=_tf_footer)
    buf.seek(0)
    return buf.getvalue()
