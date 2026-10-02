"""Tests for the Nigerian-readiness P0 features.

Covers:
- Student biodata fields (state of origin, LGA, religion, blood group, etc.)
- Report-card affective/psychomotor trait ratings + snapshot fields
- Termii SMS provider (mocked HTTP — no real credentials needed)
- Paystack/Flutterwave payment endpoints in credential-free mode
"""
import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import User
from academics.models import Class, Section, Subject
from attendance.models import Attendance
from finance.models import Invoice, OnlinePaymentIntent, Payment
from gradebook.models import (
    Assessment, Grade, GradingScheme, GradeBoundary, ReportCard, TraitRating,
)
from notifications.models import SMSMessage
from notifications.utils import queue_sms
from schools.models import AcademicSession, School, Term
from students.models import Guardian, GuardianStudent, Student, StudentEnrollment


class P0Base(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(
            name='P0 School', subdomain='p0-school',
            tier='Sprout', status=School.Status.ACTIVE,
        )
        self.admin = User.objects.create_user(
            email='admin@p0.example', password='Adminpass123!',
            first_name='Admin', last_name='One', role=User.Roles.SCHOOL_ADMIN,
            school=self.school, is_staff=True,
        )
        self.parent_user = User.objects.create_user(
            email='parent@p0.example', password='Parentpass123!',
            first_name='Par', last_name='Ent', role=User.Roles.PARENT,
            school=self.school,
        )
        self.admin_token, _ = Token.objects.get_or_create(user=self.admin)
        self.parent_token, _ = Token.objects.get_or_create(user=self.parent_user)

        self.session = AcademicSession.objects.create(
            school=self.school, name='2025/2026',
            start_date='2025-09-01', end_date='2026-08-31', is_current=True,
        )
        self.term = Term.objects.create(
            school=self.school, session=self.session, name='First Term',
            start_date='2025-09-08', end_date='2025-12-19', is_current=True,
        )
        self.sclass = Class.objects.create(school=self.school, name='JSS 1')
        self.section = Section.objects.create(
            school=self.school, school_class=self.sclass, name='A',
        )
        self.student = Student.objects.create(
            school=self.school, admission_number='P0/0001',
            first_name='Chidi', last_name='Okafor', gender='male',
        )
        self.guardian = Guardian.objects.create(
            school=self.school, user=self.parent_user,
            first_name='Par', last_name='Ent', phone='08031234567',
        )
        GuardianStudent.objects.create(
            school=self.school, guardian=self.guardian,
            student=self.student, is_primary=True,
        )
        StudentEnrollment.objects.create(
            school=self.school, student=self.student, session=self.session,
            term=self.term, section=self.section,
        )

    def auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')


class StudentBiodataTests(P0Base):
    """Nigerian student-record fields must round-trip through the API."""

    def test_create_student_with_full_biodata(self):
        self.auth(self.admin_token)
        payload = {
            'admission_number': 'P0/0002',
            'first_name': 'Ngozi', 'last_name': 'Eze', 'gender': 'female',
            'date_of_birth': '2014-03-12', 'address': '12 Aliyu Rd, Enugu',
            'nationality': 'Nigerian', 'state_of_origin': 'Enugu',
            'lga': 'Enugu North', 'religion': 'christianity',
            'nin': '12345678901', 'blood_group': 'O+', 'genotype': 'AA',
            'medical_conditions': 'Asthmatic — inhaler in sickbay',
            'previous_school': 'Sunrise Nursery & Primary',
            'section': self.section.id,
            'guardian_first_name': 'Ada', 'guardian_last_name': 'Eze',
            'guardian_phone': '08060001122', 'guardian_relationship': 'mother',
        }
        res = self.client.post('/api/students/', payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        s = Student.objects.get(pk=res.data['id'])
        for field in ('state_of_origin', 'lga', 'religion', 'nin',
                      'blood_group', 'genotype', 'medical_conditions',
                      'previous_school', 'nationality'):
            self.assertEqual(getattr(s, field), payload[field])
        # Enrollment + guardian link were created too
        self.assertTrue(
            StudentEnrollment.objects.filter(
                student=s, term=self.term, section=self.section).exists())
        self.assertTrue(s.guardians.filter(guardian__phone='08060001122').exists())

    def test_biodata_returned_on_read_and_patchable(self):
        self.auth(self.admin_token)
        res = self.client.get(f'/api/students/{self.student.id}/')
        self.assertEqual(res.status_code, 200)
        for field in ('state_of_origin', 'lga', 'religion', 'nin',
                      'blood_group', 'genotype', 'medical_conditions',
                      'previous_school', 'nationality'):
            self.assertIn(field, res.data)

        res = self.client.patch(
            f'/api/students/{self.student.id}/',
            {'state_of_origin': 'Kano', 'lga': 'Nassarawa',
             'blood_group': 'A-', 'medical_conditions': 'Peanut allergy'},
            format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.student.refresh_from_db()
        self.assertEqual(self.student.state_of_origin, 'Kano')
        self.assertEqual(self.student.blood_group, 'A-')


class TraitAndSnapshotTests(P0Base):
    """Report-card trait ratings + attendance/class-average snapshots."""

    def _compute_card(self):
        """Enter grades + attendance, run the engine, return the card."""
        scheme = GradingScheme.objects.create(
            school=self.school, name='Default', is_default=True,
            ca1_weight=20, ca2_weight=20, exam_weight=60,
        )
        GradeBoundary.objects.create(
            school=self.school, scheme=scheme, label='A1',
            min_score=70, max_score=100, remark='Excellent',
        )
        subject = Subject.objects.create(school=self.school, name='English', code='ENG')
        for atype, score in (('ca1', 15), ('ca2', 18), ('exam', 50)):
            a = Assessment.objects.create(
                school=self.school, term=self.term, subject=subject,
                school_class=self.sclass, name=f'{atype} assess',
                type=atype, max_score=100 if atype == 'exam' else 20,
                date='2025-10-01',
            )
            Grade.objects.create(
                school=self.school, assessment=a,
                student=self.student, score=score,
            )
        # 2 days open, present once, absent once
        Attendance.objects.create(
            school=self.school, student=self.student, school_class=self.sclass,
            date='2025-09-08', status=Attendance.Status.PRESENT,
        )
        Attendance.objects.create(
            school=self.school, student=self.student, school_class=self.sclass,
            date='2025-09-09', status=Attendance.Status.ABSENT,
        )
        self.auth(self.admin_token)
        res = self.client.post('/api/report-cards/compute/',
                               {'term_id': self.term.id}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        return ReportCard.objects.get(student=self.student, term=self.term)

    def test_compute_populates_snapshot_fields(self):
        card = self._compute_card()
        self.assertEqual(card.days_open, 2)
        self.assertEqual(card.days_present, 1)
        self.assertIsNotNone(card.class_average)
        self.assertEqual(card.position, 1)
        # Snapshot survives later register changes — recompute not required
        Attendance.objects.create(
            school=self.school, student=self.student, school_class=self.sclass,
            date='2025-09-10', status=Attendance.Status.PRESENT,
        )
        card.refresh_from_db()
        self.assertEqual(card.days_open, 2, 'Snapshot must not drift live')

    def test_trait_ratings_upsert_via_patch(self):
        card = self._compute_card()
        self.auth(self.admin_token)
        res = self.client.patch(f'/api/report-cards/{card.id}/', {
            'trait_ratings': [
                {'trait': 'Punctuality', 'category': 'affective', 'rating': 4},
                {'trait': 'Honesty', 'category': 'affective', 'rating': 5},
                {'trait': 'Handwriting', 'category': 'psychomotor', 'rating': 3},
            ],
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(card.trait_ratings.count(), 3)
        self.assertEqual(
            card.trait_ratings.get(trait='Honesty').rating, 5)

        # Omitted traits are removed on re-save (client sends the full set)
        res = self.client.patch(f'/api/report-cards/{card.id}/', {
            'trait_ratings': [
                {'trait': 'Punctuality', 'category': 'affective', 'rating': 5},
            ],
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(card.trait_ratings.count(), 1)

    def test_trait_validation_rejects_bad_input(self):
        card = self._compute_card()
        self.auth(self.admin_token)
        res = self.client.patch(f'/api/report-cards/{card.id}/', {
            'trait_ratings': [
                {'trait': 'Punctuality', 'category': 'affective', 'rating': 7},
            ],
        }, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.patch(f'/api/report-cards/{card.id}/', {
            'trait_ratings': [
                {'trait': 'Punctuality', 'category': 'bogus', 'rating': 3},
            ],
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(card.trait_ratings.count(), 0)

    def test_parent_cannot_write_traits_and_sees_only_published(self):
        card = self._compute_card()
        self.auth(self.parent_token)
        # Draft card is invisible to parents
        res = self.client.get(f'/api/report-cards/{card.id}/')
        self.assertEqual(res.status_code, 404)
        # And they can't write one even if they guess the id
        res = self.client.patch(f'/api/report-cards/{card.id}/', {
            'trait_ratings': [
                {'trait': 'Punctuality', 'category': 'affective', 'rating': 5},
            ],
        }, format='json')
        self.assertIn(res.status_code, (403, 404))
        self.assertEqual(card.trait_ratings.count(), 0)

    def test_card_serialization_includes_new_fields(self):
        card = self._compute_card()
        TraitRating.objects.create(
            school=self.school, report_card=card,
            category='affective', trait='Punctuality', rating=4,
        )
        self.auth(self.admin_token)
        res = self.client.get(f'/api/report-cards/{card.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['days_open'], 2)
        self.assertEqual(res.data['days_present'], 1)
        self.assertIsNotNone(res.data['class_average'])
        traits = res.data['trait_ratings']
        self.assertEqual(len(traits), 1)
        self.assertEqual(traits[0]['trait'], 'Punctuality')


class TermiiProviderTests(TestCase):
    """Termii SMS provider — all HTTP is mocked, no credentials needed."""

    def _sms(self):
        school = School.objects.create(
            name='SMS School', subdomain='sms-school', tier='Sprout')
        return SMSMessage.objects.create(
            school=school, recipient='08031234567', message='Fee reminder',
        )

    @override_settings(SMS_PROVIDER='termii', TERMII_API_KEY='')
    def test_missing_api_key_fails_cleanly(self):
        sms = queue_sms(self._sms().school, '08031234567', 'hello')
        sms.refresh_from_db()
        self.assertEqual(sms.status, SMSMessage.Status.FAILED)
        self.assertIn('TERMII_API_KEY', sms.error_message)

    @override_settings(SMS_PROVIDER='termii', TERMII_API_KEY='test-key',
                       TERMII_SENDER_ID='P0School')
    @patch('notifications.providers._post_json')
    def test_successful_send_returns_message_id(self, mock_post):
        mock_post.return_value = (200, {'message_id': 'TM-998877'})
        sms = queue_sms(self._sms().school, '08031234567', 'hello')
        sms.refresh_from_db()
        self.assertEqual(sms.status, SMSMessage.Status.SENT)
        self.assertEqual(sms.provider_ref, 'TM-998877')
        # Verify the request payload Termii actually receives
        url, payload = mock_post.call_args[0][0], mock_post.call_args[0][1]
        self.assertIn('/api/sms/send', url)
        self.assertEqual(payload['api_key'], 'test-key')
        self.assertEqual(payload['from'], 'P0School')
        self.assertEqual(payload['to'], '2348031234567', '0-prefixed NG numbers → 234')
        self.assertEqual(payload['sms'], 'hello')

    @override_settings(SMS_PROVIDER='termii', TERMII_API_KEY='test-key')
    @patch('notifications.providers._post_json')
    def test_api_failure_marks_sms_failed(self, mock_post):
        mock_post.return_value = (400, {'message': 'Invalid sender id'})
        sms = queue_sms(self._sms().school, '08031234567', 'hello')
        sms.refresh_from_db()
        self.assertEqual(sms.status, SMSMessage.Status.FAILED)
        self.assertIn('Invalid sender id', sms.error_message)

    @override_settings(SMS_PROVIDER='termii', TERMII_API_KEY='test-key')
    @patch('notifications.providers._post_json')
    def test_network_error_marks_sms_failed(self, mock_post):
        mock_post.return_value = (0, {'error': 'timeout'})
        sms = queue_sms(self._sms().school, '08031234567', 'hello')
        sms.refresh_from_db()
        self.assertEqual(sms.status, SMSMessage.Status.FAILED)

    def test_phone_normalization(self):
        from notifications.providers import _normalize_ng_phone
        self.assertEqual(_normalize_ng_phone('08031234567'), '2348031234567')
        self.assertEqual(_normalize_ng_phone('2348031234567'), '2348031234567')
        self.assertEqual(_normalize_ng_phone('+234 803 123 4567'), '2348031234567')

    @override_settings(SMS_PROVIDER='stub')
    def test_stub_still_works(self):
        sms = queue_sms(self._sms().school, '08031234567', 'hello')
        sms.refresh_from_db()
        self.assertEqual(sms.status, SMSMessage.Status.SENT)


class PaymentGatewayTests(P0Base):
    """Online-payment endpoints in credential-free + mocked mode."""

    def _invoice(self, status='sent'):
        return Invoice.objects.create(
            school=self.school, student=self.student, term=self.term,
            invoice_number='INV-P0-1', total_amount=Decimal('50000'),
            amount_paid=Decimal('0'), due_date='2025-11-30',
            status=status,
        )

    @override_settings(PAYSTACK_SECRET_KEY='')
    def test_paystack_init_without_key_returns_503(self):
        self.auth(self.admin_token)
        res = self.client.post('/api/payments/paystack/initialize/',
                               {'invoice_id': self._invoice().id}, format='json')
        self.assertEqual(res.status_code, 503)
        self.assertIn('PAYSTACK_SECRET_KEY', res.data['error'])
        self.assertEqual(OnlinePaymentIntent.objects.count(), 0)

    @override_settings(FLUTTERWAVE_SECRET_KEY='')
    def test_flutterwave_init_without_key_returns_503(self):
        self.auth(self.admin_token)
        res = self.client.post('/api/payments/flutterwave/initialize/',
                               {'invoice_id': self._invoice().id}, format='json')
        self.assertEqual(res.status_code, 503)

    def test_unknown_provider_rejected(self):
        self.auth(self.admin_token)
        res = self.client.post('/api/payments/bitcoin/initialize/',
                               {'invoice_id': self._invoice().id}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_parent_cannot_pay_other_childs_invoice(self):
        other_parent = User.objects.create_user(
            email='other@p0.example', password='Pass1234!',
            role=User.Roles.PARENT, school=self.school,
        )
        Guardian.objects.create(
            school=self.school, user=other_parent,
            first_name='Other', last_name='Parent',
        )
        token, _ = Token.objects.get_or_create(user=other_parent)
        self.auth(token)
        res = self.client.post('/api/payments/paystack/initialize/',
                               {'invoice_id': self._invoice().id}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_paid_invoice_cannot_be_repaid(self):
        self.auth(self.admin_token)
        res = self.client.post('/api/payments/paystack/initialize/',
                               {'invoice_id': self._invoice(status='paid').id},
                               format='json')
        self.assertEqual(res.status_code, 400)

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_fake')
    @patch('api.payment_gateways._request')
    def test_paystack_init_and_verify_settles_payment(self, mock_req):
        self.auth(self.admin_token)
        invoice = self._invoice()
        mock_req.return_value = (200, {
            'status': True,
            'data': {'authorization_url': 'https://checkout.paystack.com/abc'},
        })
        res = self.client.post('/api/payments/paystack/initialize/',
                               {'invoice_id': invoice.id}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        reference = res.data['reference']
        intent = OnlinePaymentIntent.objects.get(reference=reference)
        self.assertEqual(intent.amount, Decimal('50000'))

        # Paystack verify → settles into a real Payment + receipt
        mock_req.return_value = (200, {
            'status': True,
            'data': {'status': 'success', 'amount': 5000000},
        })
        res = self.client.get(
            f'/api/payments/paystack/verify/?reference={reference}')
        self.assertEqual(res.status_code, 200, res.data)
        intent.refresh_from_db()
        self.assertEqual(intent.status, 'paid')
        payment = Payment.objects.get(invoice=invoice, reference=reference)
        self.assertEqual(payment.amount, Decimal('50000'))

        # Idempotent — verifying again does not double-pay
        res = self.client.get(
            f'/api/payments/paystack/verify/?reference={reference}')
        self.assertEqual(res.data.get('already_recorded'), True)
        self.assertEqual(
            Payment.objects.filter(invoice=invoice, reference=reference).count(), 1)

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_fake')
    @patch('api.payment_gateways._request')
    def test_failed_verify_marks_intent_failed(self, mock_req):
        self.auth(self.admin_token)
        invoice = self._invoice()
        intent = OnlinePaymentIntent.objects.create(
            school=self.school, invoice=invoice, provider='paystack',
            reference='TF-X-1', amount=invoice.balance,
        )
        mock_req.return_value = (200, {'status': True, 'data': {'status': 'failed'}})
        res = self.client.get('/api/payments/paystack/verify/?reference=TF-X-1')
        self.assertEqual(res.status_code, 402)
        intent.refresh_from_db()
        self.assertEqual(intent.status, 'failed')
        self.assertEqual(Payment.objects.count(), 0)

    def test_verify_unknown_reference_404(self):
        self.auth(self.admin_token)
        res = self.client.get('/api/payments/paystack/verify/?reference=NOPE')
        self.assertEqual(res.status_code, 404)

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_fake')
    def test_paystack_webhook_signature_verified(self):
        invoice = self._invoice()
        OnlinePaymentIntent.objects.create(
            school=self.school, invoice=invoice, provider='paystack',
            reference='TF-HOOK-1', amount=invoice.balance,
        )
        body = json.dumps({'event': 'charge.success',
                           'data': {'reference': 'TF-HOOK-1'}}).encode()
        # Bad signature → 403, no settlement
        res = self.client.post(
            '/api/webhooks/paystack/', body, content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE='bad-sig')
        self.assertEqual(res.status_code, 403)
        self.assertEqual(Payment.objects.count(), 0)

        # Good signature → settles without any login
        import hashlib, hmac
        sig = hmac.new(b'sk_test_fake', body, hashlib.sha512).hexdigest()
        res = self.client.post(
            '/api/webhooks/paystack/', body, content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=sig)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Payment.objects.filter(reference='TF-HOOK-1').exists())

    @override_settings(PAYSTACK_SECRET_KEY='')
    def test_paystack_webhook_without_key_503(self):
        res = self.client.post('/api/webhooks/paystack/', {},
                               content_type='application/json')
        self.assertEqual(res.status_code, 503)
