"""
Result computation engine for TabsForge School OS.

Takes raw assessment grades and produces ResultSummary + ReportCard rows
with class positions, subject positions, grades, and remarks.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Sum

from academics.models import Class, Subject
from gradebook.models import Assessment, Grade, GradeBoundary, GradingScheme, ReportCard, ResultSummary
from schools.models import Term
from students.models import Student, StudentEnrollment


# ---------------------------------------------------------------------------
# Grade determination
# ---------------------------------------------------------------------------

def get_grade(school, total_score, scheme=None):
    """Return (label, remark, points) for a given score.

    Priority: school.report_config['grade_bands'] (from the school's adopted
    report format) -> the school's default GradingScheme -> WAEC defaults.
    """
    bands = (school.report_config or {}).get('grade_bands') or []
    if bands:
        score = Decimal(str(total_score))
        for band in sorted(bands, key=lambda b: Decimal(str(b.get('min', 0))), reverse=True):
            if score >= Decimal(str(band.get('min', 0))):
                return (
                    str(band.get('label', '')),
                    str(band.get('remark', '')),
                    Decimal(str(band.get('points', 0))),
                )
        return 'F9', 'Fail', Decimal('0')
    if scheme is None:
        scheme = GradingScheme.objects.filter(school=school, is_default=True).first()
    if scheme is None:
        return _default_grade(total_score)

    boundaries = scheme.boundaries.order_by('-min_score')
    for b in boundaries:
        if Decimal(str(total_score)) >= b.min_score:
            return b.label, b.remark, b.points
    return 'F9', 'Fail', 0


def _compute_total(school, scheme, ca1, ca2, exam):
    """Weighted total honoring school.report_config['weights'] first."""
    weights = (school.report_config or {}).get('weights') or {}
    try:
        w1, w2, w3 = (Decimal(str(weights[k])) for k in ('ca1', 'ca2', 'exam'))
        if w1 + w2 + w3 > 0:
            total_w = w1 + w2 + w3
            return (Decimal(str(ca1)) * w1 + Decimal(str(ca2)) * w2
                    + Decimal(str(exam)) * w3) / total_w
    except (KeyError, TypeError, ArithmeticError):
        pass
    if scheme:
        return scheme.compute_total(ca1, ca2, exam)
    return (Decimal(str(ca1)) + Decimal(str(ca2)) + Decimal(str(exam))) / Decimal('3')


def _default_grade(score):
    """WAEC-style default boundaries if no scheme is configured."""
    score = float(score or 0)
    if score >= 75: return 'A1', 'Excellent', 5
    if score >= 70: return 'B2', 'Very Good', 4
    if score >= 65: return 'B3', 'Good', 3
    if score >= 60: return 'C4', 'Credit', 2
    if score >= 55: return 'C5', 'Credit', 2
    if score >= 50: return 'C6', 'Credit', 2
    if score >= 45: return 'D7', 'Pass', 1
    if score >= 40: return 'E8', 'Pass', 1
    return 'F9', 'Fail', 0


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_results_for_term(school, term):
    """
    Compute / refresh all ResultSummary and ReportCard rows for a given term.

    Approach:
    1. For each enrolled student/class combination, read their CA1, CA2, and Exam grades.
    2. Apply the school's grading scheme to compute a weighted total.
    3. Determine grade label / remark.
    4. Rank students by subject within each class (subject position).
    5. Rank students by overall average within each class (class position).
    6. Write ResultSummary and ReportCard rows (upsert).
    """
    scheme = GradingScheme.objects.filter(school=school, is_default=True).first()

    # Gather enrollments for this term
    enrollments = (
        StudentEnrollment.objects
        .filter(school=school, term=term)
        .select_related('student', 'section__school_class')
    )

    # Build a map: student_id -> class
    student_class = {}
    for e in enrollments:
        student_class[e.student_id] = e.section.school_class

    # Gather all assessments for this term
    assessments = (
        Assessment.objects
        .filter(school=school, term=term)
        .select_related('subject', 'school_class')
    )

    # Build a lookup: (student_id, subject_id, class_id) -> {ca1, ca2, exam}
    scores = {}  # (student_id, subject_id) -> {ca1, ca2, exam}

    for assessment in assessments:
        grades = Grade.objects.filter(school=school, assessment=assessment)
        for grade in grades:
            key = (grade.student_id, assessment.subject_id)
            if key not in scores:
                scores[key] = {'ca1': Decimal('0'), 'ca2': Decimal('0'), 'exam': Decimal('0')}
            atype = assessment.type
            if atype == 'ca1':
                scores[key]['ca1'] = grade.score
            elif atype == 'ca2':
                scores[key]['ca2'] = grade.score
            elif atype in ('exam', 'mid_term'):
                scores[key]['exam'] = grade.score

    # Compute totals and write ResultSummary rows
    result_rows = {}  # (student_id, subject_id) -> ResultSummary instance data
    with transaction.atomic():
        for (student_id, subject_id), comps in scores.items():
            sc = school
            student = Student.objects.get(pk=student_id, school=sc)
            subject = Subject.objects.get(pk=subject_id, school=sc)
            cls = student_class.get(student_id)

            ca1 = comps['ca1']
            ca2 = comps['ca2']
            exam = comps['exam']

            total = _compute_total(sc, scheme, ca1, ca2, exam)

            total = round(total, 2)
            label, remark, points = get_grade(sc, total, scheme)

            rs, _ = ResultSummary.objects.update_or_create(
                school=sc, student=student, term=term, subject=subject,
                defaults=dict(
                    school_class=cls,
                    scheme=scheme,
                    ca1_score=ca1,
                    ca2_score=ca2,
                    exam_score=exam,
                    total_score=total,
                    grade=label,
                    grade_remark=remark,
                    grade_points=points,
                ),
            )
            result_rows[(student_id, subject_id)] = rs

    # Assign subject positions per class
    class_subject_students = {}  # (class_id, subject_id) -> [(total, student_id)]
    for (student_id, subject_id), rs in result_rows.items():
        cls = student_class.get(student_id)
        if cls:
            key = (cls.pk, subject_id)
            class_subject_students.setdefault(key, []).append((rs.total_score, student_id))

    with transaction.atomic():
        for (class_id, subject_id), entries in class_subject_students.items():
            entries.sort(key=lambda x: x[0], reverse=True)
            for rank, (score, student_id) in enumerate(entries, start=1):
                ResultSummary.objects.filter(
                    school=school, student_id=student_id,
                    term=term, subject_id=subject_id,
                ).update(subject_position=rank)

    # Compute overall averages per student per class
    class_student_totals = {}  # (class_id, student_id) -> [totals]
    for (student_id, subject_id), rs in result_rows.items():
        cls = student_class.get(student_id)
        if cls:
            key = (cls.pk, student_id)
            class_student_totals.setdefault(key, []).append(float(rs.total_score))

    # Assign class positions and write ReportCard rows
    class_averages = {}  # (class_id) -> [(average, student_id)]
    for (class_id, student_id), totals in class_student_totals.items():
        avg = sum(totals) / len(totals)
        class_averages.setdefault(class_id, []).append((avg, student_id, sum(totals), len(totals)))

    with transaction.atomic():
        from attendance.models import Attendance
        for class_id, entries in class_averages.items():
            entries.sort(key=lambda x: x[0], reverse=True)
            class_size = len(entries)
            cls = Class.objects.get(pk=class_id)
            class_avg = sum(e[0] for e in entries) / class_size if class_size else 0

            # Days the register was marked for this class during the term —
            # Nigerian report cards show "days present / days school opened".
            days_open = (
                Attendance.objects
                .filter(school=school, school_class=cls,
                        date__gte=term.start_date, date__lte=term.end_date)
                .values('date').distinct().count()
            )

            for rank, (avg, student_id, total, count) in enumerate(entries, start=1):
                student = Student.objects.get(pk=student_id)
                card, created = ReportCard.objects.get_or_create(
                    school=school, student=student, term=term,
                    # New cards start hidden from parents/students — release is
                    # a deliberate approval step, not a side-effect of compute.
                    defaults=dict(status=ReportCard.Status.DRAFT),
                )
                card.school_class = cls
                card.total_score = round(total, 2)
                card.average_score = round(avg, 2)
                card.class_average = round(class_avg, 2)
                card.subjects_count = count
                card.position = rank
                card.class_size = class_size
                card.days_open = days_open
                card.days_present = Attendance.objects.filter(
                    school=school, student=student, school_class=cls,
                    date__gte=term.start_date, date__lte=term.end_date,
                    status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE],
                ).count()
                card.save(update_fields=[
                    'school_class', 'total_score', 'average_score', 'class_average',
                    'subjects_count', 'position', 'class_size',
                    'days_open', 'days_present',
                ])

    return len(result_rows)
