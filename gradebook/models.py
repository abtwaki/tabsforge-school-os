"""Gradebook models: assessments, grades, grading schemes, and result summaries."""
from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from core.models import TenantModel


class GradingScheme(TenantModel):
    """Defines assessment component weights and grade boundaries for a school.

    A school can have multiple schemes (e.g. Primary vs SS) but one default.
    """
    name = models.CharField(max_length=100, default='Standard')
    is_default = models.BooleanField(default=False)
    # Component weights (must sum to 100)
    ca1_weight = models.PositiveSmallIntegerField(
        default=20,
        validators=[MaxValueValidator(100)],
        help_text='Weight for Continuous Assessment 1 (e.g. 20 = 20%)',
    )
    ca2_weight = models.PositiveSmallIntegerField(
        default=20,
        validators=[MaxValueValidator(100)],
    )
    exam_weight = models.PositiveSmallIntegerField(
        default=60,
        validators=[MaxValueValidator(100)],
    )

    class Meta:
        verbose_name = 'Grading Scheme'
        ordering = ['-is_default', 'name']

    def __str__(self):
        return f"{self.name} ({self.ca1_weight}/{self.ca2_weight}/{self.exam_weight})"

    def compute_total(self, ca1, ca2, exam):
        """Return weighted total (out of 100) given raw scores (Decimal or numeric)."""
        _100 = Decimal('100')
        d_ca1 = Decimal(str(ca1)) if ca1 else Decimal('0')
        d_ca2 = Decimal(str(ca2)) if ca2 else Decimal('0')
        d_exam = Decimal(str(exam)) if exam else Decimal('0')
        return (
            d_ca1 * self.ca1_weight / _100
            + d_ca2 * self.ca2_weight / _100
            + d_exam * self.exam_weight / _100
        )


class GradeBoundary(TenantModel):
    """A single grade boundary row within a grading scheme."""
    scheme = models.ForeignKey(
        GradingScheme, on_delete=models.CASCADE, related_name='boundaries',
    )
    label = models.CharField(max_length=10, help_text='e.g. A1, B2, F9')
    remark = models.CharField(max_length=50, help_text='e.g. Excellent, Pass')
    min_score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    points = models.PositiveSmallIntegerField(
        default=0,
        help_text='Grade point (for GPA computation), e.g. A1=5',
    )

    class Meta:
        ordering = ['-min_score']
        unique_together = [['school', 'scheme', 'label']]
        verbose_name = 'Grade Boundary'

    def __str__(self):
        return f"{self.label} ({self.min_score}–{self.max_score})"


class Assessment(TenantModel):
    class Types(models.TextChoices):
        EXAM = 'exam', 'Exam'
        CA1 = 'ca1', 'Continuous Assessment 1'
        CA2 = 'ca2', 'Continuous Assessment 2'
        QUIZ = 'quiz', 'Quiz'
        ASSIGNMENT = 'assignment', 'Assignment'
        PROJECT = 'project', 'Project'
        MID_TERM = 'mid_term', 'Mid Term'

    term = models.ForeignKey(
        'schools.Term', on_delete=models.CASCADE, related_name='assessments',
    )
    subject = models.ForeignKey(
        'academics.Subject', on_delete=models.CASCADE, related_name='assessments',
    )
    school_class = models.ForeignKey(
        'academics.Class', on_delete=models.CASCADE, related_name='assessments',
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=Types.choices, default=Types.EXAM)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100.00)
    date = models.DateField()

    class Meta:
        ordering = ['-date', 'name']
        unique_together = [['school', 'term', 'subject', 'school_class', 'name', 'type']]

    def __str__(self):
        return f"{self.name} – {self.subject} ({self.school_class})"


class Grade(TenantModel):
    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name='grades',
    )
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='grades',
    )
    score = models.DecimalField(
        max_digits=6, decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [['school', 'assessment', 'student']]
        ordering = ['-assessment__date', 'student__last_name']

    def __str__(self):
        return f"{self.student} – {self.assessment} = {self.score}"


class ResultSummary(TenantModel):
    """Aggregated per-student per-subject per-term result.

    Populated by the result computation engine (api/result_engine.py).
    Stores final weighted totals, grades, and positions.
    """
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='results',
    )
    term = models.ForeignKey(
        'schools.Term', on_delete=models.CASCADE, related_name='results',
    )
    subject = models.ForeignKey(
        'academics.Subject', on_delete=models.CASCADE, related_name='results',
    )
    school_class = models.ForeignKey(
        'academics.Class', on_delete=models.CASCADE,
        related_name='results', null=True, blank=True,
    )
    scheme = models.ForeignKey(
        GradingScheme, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='results',
    )

    # Raw component scores (out of the scheme max for each component)
    ca1_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    ca2_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    exam_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # Computed fields (filled by result engine)
    total_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    grade = models.CharField(max_length=10, blank=True)
    grade_remark = models.CharField(max_length=50, blank=True)
    grade_points = models.PositiveSmallIntegerField(default=0)

    # Positions (filled after all students are computed)
    subject_position = models.PositiveIntegerField(null=True, blank=True)
    class_position = models.PositiveIntegerField(null=True, blank=True)

    # Teacher comment for this subject result
    teacher_comment = models.TextField(blank=True)

    class Meta:
        unique_together = [['school', 'student', 'term', 'subject']]
        ordering = ['subject__name']
        verbose_name = 'Result Summary'
        verbose_name_plural = 'Result Summaries'

    def __str__(self):
        return f"{self.student} | {self.subject} | {self.term} = {self.total_score}"


class ReportCard(TenantModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'

    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='report_cards',
    )
    term = models.ForeignKey(
        'schools.Term', on_delete=models.CASCADE, related_name='report_cards',
    )
    school_class = models.ForeignKey(
        'academics.Class', on_delete=models.CASCADE,
        related_name='report_cards', null=True, blank=True,
    )
    total_score = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
    )
    average_score = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
    )
    # Number of subjects taken
    subjects_count = models.PositiveSmallIntegerField(default=0)
    position = models.PositiveIntegerField(null=True, blank=True)
    class_size = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT,
    )
    teacher_comments = models.TextField(blank=True)
    principal_comments = models.TextField(blank=True)
    next_term_begins = models.DateField(null=True, blank=True)
    # Snapshot of term attendance at compute time (Nigerian report cards show
    # "X of Y days present" alongside the academic results).
    days_open = models.PositiveSmallIntegerField(null=True, blank=True)
    days_present = models.PositiveSmallIntegerField(null=True, blank=True)
    class_average = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Average score across the whole class — parents compare against the pupil\'s own average.',
    )

    class Meta:
        unique_together = [['school', 'student', 'term']]
        ordering = ['-term__start_date', 'student__last_name']

    def __str__(self):
        return f"Report card for {self.student} – {self.term}"


class AtRiskFlag(TenantModel):
    """
    Tracks students flagged as academically at-risk by the AI early-warning system (Part 5).
    """
    class FlagType(models.TextChoices):
        GRADE_DECLINE = 'grade_decline', 'Consecutive Grade Decline'
        LOW_ATTENDANCE = 'low_attendance', 'Attendance Below Threshold'
        MULTIPLE = 'multiple', 'Multiple Risk Factors'

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='risk_flags')
    term = models.ForeignKey('schools.Term', on_delete=models.CASCADE, related_name='risk_flags')
    flag_type = models.CharField(max_length=20, choices=FlagType.choices, default=FlagType.GRADE_DECLINE)
    reason = models.TextField(help_text='Human-readable explanation of the risk signal.')
    details = models.JSONField(default=dict, blank=True)
    resolved = models.BooleanField(default=False)
    notified_teacher = models.BooleanField(default=False)
    notified_parent = models.BooleanField(default=False)
    flagged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-flagged_at']
        unique_together = [['school', 'student', 'term', 'flag_type']]
        verbose_name = 'At-Risk Flag'

    def __str__(self):
        return f"AtRisk: {self.student} ({self.flag_type}) - {self.term}"


class TraitRating(TenantModel):
    """Affective & psychomotor trait ratings on a report card.

    Nigerian report cards grade behaviour/skills on a 1–5 scale alongside
    academic scores — e.g. Punctuality (affective) or Handwriting (psychomotor).
    The trait name is free text so each school can use its own checklist.
    """
    class Category(models.TextChoices):
        AFFECTIVE = 'affective', 'Affective (Behaviour)'
        PSYCHOMOTOR = 'psychomotor', 'Psychomotor (Skills)'

    report_card = models.ForeignKey(
        ReportCard, on_delete=models.CASCADE, related_name='trait_ratings'
    )
    category = models.CharField(max_length=15, choices=Category.choices)
    trait = models.CharField(max_length=60)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='1–5 scale (1 = poor … 5 = excellent)',
    )

    class Meta:
        ordering = ['category', 'trait']
        unique_together = [['school', 'report_card', 'category', 'trait']]

    def __str__(self):
        return f"{self.trait}: {self.rating}"
