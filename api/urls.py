"""API URL configuration."""
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from billing.viewsets import SubscriptionViewSet

from . import auth_views, csv_views, dashboard_views, marketing_views, onboarding_views
from . import viewsets as views
from . import admissions_views, homework_views, messaging_views, result_views, ai_views, reminder_views
from . import channels_views, installment_views, group_views, risk_views, export_views, guest_views, rollover_views
from . import payment_gateways

router = DefaultRouter()

# Schools / calendar
router.register(r'schools', views.SchoolViewSet, basename='school')
router.register(r'academic-sessions', views.AcademicSessionViewSet, basename='academic-session')
router.register(r'terms', views.TermViewSet, basename='term')

# Academics
router.register(r'classes', views.ClassViewSet, basename='class')
router.register(r'sections', views.SectionViewSet, basename='section')
router.register(r'subjects', views.SubjectViewSet, basename='subject')
router.register(r'class-subjects', views.ClassSubjectViewSet, basename='class-subject')
router.register(r'timetable', views.TimetableViewSet, basename='timetable')

# Students
router.register(r'students', views.StudentViewSet, basename='student')
router.register(r'guardians', views.GuardianViewSet, basename='guardian')
router.register(r'guardian-students', views.GuardianStudentViewSet, basename='guardian-student')
router.register(r'enrollments', views.StudentEnrollmentViewSet, basename='enrollment')

# Staff
router.register(r'staff', views.StaffViewSet, basename='staff')

# Attendance
router.register(r'attendance', views.AttendanceViewSet, basename='attendance')

# Gradebook (original)
router.register(r'assessments', views.AssessmentViewSet, basename='assessment')
router.register(r'grades', views.GradeViewSet, basename='grade')

# Grading schemes and result engine
router.register(r'grading-schemes', result_views.GradingSchemeViewSet, basename='grading-scheme')
router.register(r'grade-boundaries', result_views.GradeBoundaryViewSet, basename='grade-boundary')
router.register(r'results', result_views.ResultSummaryViewSet, basename='result')
router.register(r'report-cards', result_views.EnhancedReportCardViewSet, basename='report-card')

# Finance
router.register(r'fee-categories', views.FeeCategoryViewSet, basename='fee-category')
router.register(r'fee-structures', views.FeeStructureViewSet, basename='fee-structure')
router.register(r'invoices', views.InvoiceViewSet, basename='invoice')
router.register(r'payments', views.PaymentViewSet, basename='payment')
router.register(r'expenses', views.ExpenseViewSet, basename='expense')

# Communications
router.register(r'announcements', views.AnnouncementViewSet, basename='announcement')
router.register(r'notices', views.NoticeViewSet, basename='notice')

# Library
router.register(r'library/books', views.BookViewSet, basename='book')
router.register(r'library/borrows', views.BorrowRecordViewSet, basename='borrow')

# Transport
router.register(r'transport/routes', views.RouteViewSet, basename='route')
router.register(r'transport/vehicles', views.VehicleViewSet, basename='vehicle')
router.register(r'transport/assignments', views.VehicleAssignmentViewSet, basename='vehicle-assignment')

# Hostel
router.register(r'hostels', views.HostelViewSet, basename='hostel')
router.register(r'hostel/rooms', views.RoomViewSet, basename='room')
router.register(r'hostel/allocations', views.HostelAllocationViewSet, basename='hostel-allocation')

# Users
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'audit-logs', views.AuditLogViewSet, basename='audit-log')

# Notifications
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'notifications/emails', views.EmailMessageViewSet, basename='email')
router.register(r'notifications/sms', views.SMSMessageViewSet, basename='sms')

# Billing
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')

# Admissions
router.register(r'admission-config', admissions_views.AdmissionConfigViewSet, basename='admission-config')
router.register(r'applications', admissions_views.ApplicationViewSet, basename='application')

# Homework & live lessons
router.register(r'assignments', homework_views.AssignmentViewSet, basename='assignment')
router.register(r'submissions', homework_views.SubmissionViewSet, basename='submission')
router.register(r'live-lessons', homework_views.LiveLessonViewSet, basename='live-lesson')

# Messaging
router.register(r'conversations', messaging_views.ConversationViewSet, basename='conversation')
router.register(r'messages', messaging_views.MessageViewSet, basename='message')

# Part 3: Installment plans & receipts
router.register(r'installment-plans', installment_views.InstallmentPlanViewSet, basename='installment-plan')
router.register(r'receipts', installment_views.PaymentReceiptViewSet, basename='receipt')

# Part 4: School groups
router.register(r'groups', group_views.SchoolGroupViewSet, basename='school-group')

urlpatterns = [
    # Auth
    path('auth/login/', auth_views.login_view, name='auth-login'),
    path('auth/logout/', auth_views.logout_view, name='auth-logout'),
    path('auth/me/', auth_views.me_view, name='auth-me'),
    path('auth/complete-tutorial/', auth_views.complete_tutorial, name='complete-tutorial'),
    path('auth/change-password/', auth_views.change_password, name='change-password'),

    # Part 2: OTP + channel preference
    path('auth/send-otp/', channels_views.send_otp, name='send-otp'),
    path('auth/verify-otp/', channels_views.verify_otp, name='verify-otp'),
    path('auth/reset-password/', channels_views.reset_password, name='reset-password'),
    path('auth/totp/setup/', channels_views.totp_setup, name='totp-setup'),
    path('auth/totp/enable/', channels_views.totp_enable, name='totp-enable'),
    path('auth/totp/disable/', channels_views.totp_disable, name='totp-disable'),
    path('auth/request-registration/', channels_views.request_registration_link, name='request-registration'),
    path('auth/complete-registration/', channels_views.complete_registration, name='complete-registration'),
    path('users/<int:pk>/channel-preference/', channels_views.update_channel_preference, name='channel-preference'),
    path('users/me/channel-preference/', channels_views.update_channel_preference, {'pk': None}, name='channel-preference-me'),

    # Part 2: WhatsApp webhook
    path('whatsapp/webhook/', channels_views.whatsapp_webhook, name='whatsapp-webhook'),

    # Part 8: Guest demo access
    path('auth/guest-token/', guest_views.guest_token, name='guest-token'),
    path('auth/demo-credentials/', guest_views.demo_credentials, name='demo-credentials'),

    # Marketing
    path('marketing/demo-request/', marketing_views.demo_request, name='demo-request'),
    path('marketing/demo-leads/', marketing_views.demo_leads, name='demo-leads'),
    path('marketing/demo-leads/<int:pk>/contact/', marketing_views.demo_lead_contact, name='demo-lead-contact'),
    path('marketing/demo-leads/<int:pk>/', marketing_views.demo_lead_delete, name='demo-lead-delete'),

    # Health
    path('health/', auth_views.health_check, name='health'),

    # Dashboard
    path('dashboard/', dashboard_views.dashboard_view, name='dashboard'),
    path('analytics/', dashboard_views.analytics_view, name='analytics'),

    # Onboarding (Super Admin only)
    path('onboarding/', onboarding_views.onboarding_view, name='onboarding'),
    path('onboarding/check_subdomain/', onboarding_views.check_subdomain_view, name='check-subdomain'),
    path('onboarding/tiers/', onboarding_views.tiers_view, name='onboarding-tiers'),
    path('onboarding/approvals/', onboarding_views.onboarding_approvals_view, name='onboarding-approvals'),
    path('onboarding/approvals/<int:pk>/', onboarding_views.approval_detail_view, name='approval-detail'),
    path('onboarding/approvals/<int:pk>/approve/', onboarding_views.approve_school_view, name='approve-school'),
    path('onboarding/approvals/<int:pk>/flag/', onboarding_views.flag_school_view, name='flag-school'),
    path('onboarding/approvals/<int:pk>/reject/', onboarding_views.reject_school_view, name='reject-school'),
    path('onboarding/approvals/<int:pk>/resend-welcome/', onboarding_views.resend_welcome_view, name='resend-welcome'),

    # CSV imports
    path('import/<str:import_type>/', csv_views.csv_import_view, name='csv-import'),
    path('import/<str:import_type>/template/', csv_views.csv_template_view, name='csv-template'),

    # Admissions
    path('admission-number-preview/', admissions_views.admission_number_preview, name='admission-number-preview'),

    # Result engine
    path('reports/fee-collection-pdf/', result_views.fee_collection_pdf, name='fee-collection-pdf'),
    path('reports/debtors-pdf/', result_views.debtors_pdf, name='debtors-pdf'),
    path('reports/income-expenditure-pdf/', result_views.income_expenditure_pdf, name='income-expenditure-pdf'),
    path('reports/student-ledger-pdf/', result_views.student_ledger_pdf, name='student-ledger-pdf'),

    # AI Suite
    path('ai/admissions-assistant/', ai_views.ai_admissions_assistant, name='ai-admissions-assistant'),
    path('ai/debtor-alert/', ai_views.ai_debtor_alert, name='ai-debtor-alert'),
    path('ai/lesson-plan/', ai_views.ai_lesson_plan, name='ai-lesson-plan'),
    path('ai/report-comment/', ai_views.ai_report_comment, name='ai-report-comment'),
    path('ai/timetable-conflicts/', ai_views.check_timetable_conflicts, name='timetable-conflicts'),
    path('ai/chat/', ai_views.ai_chat, name='ai-chat'),

    # Session rollover (promotion / graduation)
    path('rollover/preview/', rollover_views.rollover_preview, name='rollover-preview'),
    path('rollover/', rollover_views.rollover_execute, name='rollover-execute'),

    # Part 5: Academic early-warning AI
    path('ai/run-risk-analysis/', risk_views.run_risk_analysis, name='run-risk-analysis'),
    path('ai/at-risk-students/', risk_views.at_risk_students, name='at-risk-students'),
    path('ai/at-risk-students/<int:pk>/resolve/', risk_views.resolve_risk_flag, name='resolve-risk-flag'),

    # Part 3: USSD payment
    path('payments/ussd/initiate/', installment_views.initiate_ussd_payment, name='ussd-initiate'),
    path('payments/<str:provider>/initialize/', payment_gateways.initialize_payment, name='payment-initialize'),
    path('payments/<str:provider>/verify/', payment_gateways.verify_payment, name='payment-verify'),
    path('webhooks/paystack/', payment_gateways.paystack_webhook, name='paystack-webhook'),
    path('webhooks/flutterwave/', payment_gateways.flutterwave_webhook, name='flutterwave-webhook'),
    path('receipts/<int:pk>/pdf/', installment_views.PaymentReceiptViewSet.as_view({'get': 'download_pdf'}), name='receipt-pdf'),

    # Part 6: Data export
    path('export/all/', export_views.export_all, name='export-all'),
    # Formatted reports: /api/exports/<kind>/<xlsx|docx|csv>/
    path('exports/<str:kind>/<str:fmt>/', export_views.export_report, name='export-report'),
    path('export/students/', export_views.export_students, name='export-students'),
    path('export/grades/', export_views.export_grades, name='export-grades'),
    path('export/attendance/', export_views.export_attendance, name='export-attendance'),
    path('export/fees/', export_views.export_fees, name='export-fees'),
    path('export/group/<int:pk>/', export_views.export_group, name='export-group'),

    # Task reminders
    path('tasks/', reminder_views.pending_tasks, name='pending-tasks'),

    # API docs
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='docs'),

    path('', include(router.urls)),
]
