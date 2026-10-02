"""API RBAC and tenant isolation tests."""
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import User
from academics.models import Class
from billing.models import Subscription
from schools.models import AcademicSession, School, Term
from students.models import Student


@override_settings(ROOT_URLCONF='project.urls')
class TenantIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school_a = School.objects.create(name='School A', subdomain='school-a', tier='Sprout', status=School.Status.ACTIVE)
        self.school_b = School.objects.create(name='School B', subdomain='school-b', tier='Sprout', status=School.Status.ACTIVE)

        self.admin_a = User.objects.create_user(
            email='admin@school-a.example', password='password123',
            first_name='Admin', last_name='A', role=User.Roles.SCHOOL_ADMIN,
            school=self.school_a, is_staff=True,
        )
        self.admin_b = User.objects.create_user(
            email='admin@school-b.example', password='password123',
            first_name='Admin', last_name='B', role=User.Roles.SCHOOL_ADMIN,
            school=self.school_b, is_staff=True,
        )

        self.class_a = Class.objects.create(school=self.school_a, name='Class A')
        self.class_b = Class.objects.create(school=self.school_b, name='Class B')

        self.token_a, _ = Token.objects.get_or_create(user=self.admin_a)
        self.token_b, _ = Token.objects.get_or_create(user=self.admin_b)

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_school_a_admin_cannot_list_school_b_classes(self):
        self.authenticate(self.token_a)
        response = self.client.get(reverse('class-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item['name'] for item in response.data.get('results', response.data)]
        self.assertIn('Class A', names)
        self.assertNotIn('Class B', names)

    def test_school_b_admin_cannot_list_school_a_classes(self):
        self.authenticate(self.token_b)
        response = self.client.get(reverse('class-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item['name'] for item in response.data.get('results', response.data)]
        self.assertIn('Class B', names)
        self.assertNotIn('Class A', names)

    def test_school_b_admin_cannot_access_school_a_class_detail(self):
        self.authenticate(self.token_b)
        url = reverse('class-detail', kwargs={'pk': self.class_a.pk})
        response = self.client.get(url)
        # DRF returns 404 because the object is excluded by tenant filtering.
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

    def test_login_returns_token_and_user_info(self):
        response = self.client.post(
            reverse('auth-login'),
            {'email': 'admin@school-a.example', 'password': 'password123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['email'], 'admin@school-a.example')

    def test_logout_removes_token(self):
        self.authenticate(self.token_a)
        response = self.client.post(reverse('auth-logout'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(user=self.admin_a).exists())

    def test_health_check_is_public(self):
        self.client.credentials()  # no auth
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')

    def test_onboarding_creates_school_and_admin(self):
        """Super Admin can create a school via the onboarding endpoint."""
        super_admin = User.objects.create_superuser(
            email='super@tabsforge.com', password='SuperAdmin123!',
            first_name='Super', last_name='Admin',
        )
        super_admin.role = User.Roles.SUPER_ADMIN
        super_admin.save()
        super_token, _ = Token.objects.get_or_create(user=super_admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {super_token.key}')

        payload = {
            'school_name': 'New School',
            'address': '123 Main St',
            'contact_info': {'phone': '555-1234'},
            'subdomain': 'new-school',
            'tier': 'Sprout',
            'admin_email': 'admin@new-school.example',
            'admin_name': 'New Admin',
            'admin_password': 'NewPassword123!',
        }
        response = self.client.post(reverse('onboarding'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['subdomain'], 'new-school')
        self.assertTrue(School.objects.filter(subdomain='new-school').exists())
        self.assertTrue(
            User.objects.filter(email='admin@new-school.example', role=User.Roles.SCHOOL_ADMIN).exists()
        )
        school = School.objects.get(subdomain='new-school')
        self.assertEqual(school.status, School.Status.ONBOARDING)
        self.assertTrue(AcademicSession.objects.filter(school=school, is_current=True).exists())
        self.assertTrue(Term.objects.filter(school=school, is_current=True).exists())

    def test_onboarding_public_signup_creates_pending_school(self):
        """Anonymous self-service signup creates a school in ONBOARDING status.

        The school admin cannot log in until a super admin approves the
        school — covered by
        test_school_admin_cannot_login_until_super_admin_approves_school.
        """
        self.client.credentials()  # no auth
        response = self.client.post(reverse('onboarding'), {
            'school_name': 'Anon School', 'address': '123', 'subdomain': 'anon-school',
            'tier': 'Sprout', 'admin_email': 'anon@anon.example',
            'admin_name': 'Anon', 'admin_password': 'AnonPass123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        school = School.objects.get(subdomain='anon-school')
        self.assertEqual(school.status, School.Status.ONBOARDING)
        admin = User.objects.get(email='anon@anon.example')
        login_resp = self.client.post(reverse('auth-login'), {
            'email': 'anon@anon.example', 'password': 'AnonPass123!',
        }, format='json')
        self.assertEqual(login_resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_onboarding_rejects_duplicate_admin_email_without_partial_school(self):
        """Super Admin: duplicate admin email should be rejected without creating a school."""
        super_admin = User.objects.create_superuser(
            email='super2@tabsforge.com', password='SuperAdmin123!',
            first_name='Super', last_name='Admin',
        )
        super_admin.role = User.Roles.SUPER_ADMIN
        super_admin.save()
        super_token, _ = Token.objects.get_or_create(user=super_admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {super_token.key}')

        before = School.objects.count()
        response = self.client.post(reverse('onboarding'), {
            'school_name': 'Duplicate School',
            'address': 'Minna',
            'subdomain': 'duplicate-school',
            'tier': 'Sprout',
            'admin_email': self.admin_a.email,
            'admin_name': 'Duplicate Admin',
            'admin_password': 'StrongPassword123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(School.objects.count(), before)

    def test_onboarding_rejects_invalid_and_reserved_subdomains(self):
        for subdomain in ('www', '-invalid', 'two--hyphens'):
            response = self.client.get(reverse('check-subdomain'), {'subdomain': subdomain})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertFalse(response.data['available'])

    def test_school_admin_cannot_login_until_super_admin_approves_school(self):
        school = School.objects.create(name='Pending', subdomain='pending-school', tier='Sprout')
        admin = User.objects.create_user(
            email='pending@example.com', password='StrongPassword123!',
            first_name='Pending', last_name='Admin', role=User.Roles.SCHOOL_ADMIN,
            school=school,
        )
        response = self.client.post(reverse('auth-login'), {
            'email': admin.email, 'password': 'StrongPassword123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        super_user = User.objects.create_superuser(
            email='approver@example.com', password='StrongPassword123!',
            first_name='Platform', last_name='Admin',
        )
        token = Token.objects.create(user=super_user)
        self.authenticate(token)
        response = self.client.post(reverse('approve-school', kwargs={'pk': school.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.credentials()
        response = self.client.post(reverse('auth-login'), {
            'email': admin.email, 'password': 'StrongPassword123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class RBACTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(name='School', subdomain='school-rbac', tier='Sprout', status=School.Status.ACTIVE)

        self.super = User.objects.create_superuser(
            email='super@example.com', password='superpass123',
            first_name='Super', last_name='User',
        )
        self.school_admin = User.objects.create_user(
            email='admin@rbac.example', password='pass123',
            first_name='Admin', last_name='User', role=User.Roles.SCHOOL_ADMIN,
            school=self.school, is_staff=True,
        )
        self.accountant = User.objects.create_user(
            email='accountant@rbac.example', password='pass123',
            first_name='Accountant', last_name='User', role=User.Roles.ACCOUNTANT,
            school=self.school,
        )
        self.student_user = User.objects.create_user(
            email='student@rbac.example', password='pass123',
            first_name='Student', last_name='User', role=User.Roles.STUDENT,
            school=self.school,
        )
        self.student = Student.objects.create(
            school=self.school, admission_number='R001',
            first_name='Student', last_name='User', user=self.student_user,
        )
        self.cls = Class.objects.create(school=self.school, name='Class 1')

        self.super_token, _ = Token.objects.get_or_create(user=self.super)
        self.school_admin_token, _ = Token.objects.get_or_create(user=self.school_admin)
        self.student_token, _ = Token.objects.get_or_create(user=self.student_user)
        self.accountant_token, _ = Token.objects.get_or_create(user=self.accountant)

    def test_demo_credentials_requires_authentication(self):
        response = self.client.get(reverse('demo-credentials'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_demo_credentials_rejects_school_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.school_admin_token.key}')
        response = self.client.get(reverse('demo-credentials'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_demo_credentials_omits_passwords_for_super_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.super_token.key}')
        response = self.client.get(reverse('demo-credentials'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('password', str(response.data).lower())

    def test_student_cannot_create_school_configuration(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.student_token.key}')
        response = self.client.post(reverse('class-list'), {'name': 'Unauthorized Class'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Class.objects.filter(name='Unauthorized Class').exists())

    def test_accountant_cannot_create_school_configuration(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.accountant_token.key}')
        response = self.client.post(reverse('class-list'), {'name': 'Finance Class'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Class.objects.filter(name='Finance Class').exists())

    def test_student_can_only_see_own_record(self):
        # A student can only see their own record.
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.student_token.key}')
        response = self.client.get(reverse('student-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data.get('results', response.data)]
        self.assertIn(self.student.pk, ids)
        self.assertEqual(len(ids), 1)

    def test_accountant_can_access_invoices(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.accountant_token.key}')
        response = self.client.get(reverse('invoice-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_super_admin_can_filter_by_school_id(self):
        other_school = School.objects.create(name='Other', subdomain='other-rbac', tier='Sprout')
        Class.objects.create(school=other_school, name='Other Class')

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.super_token.key}')
        response = self.client.get(reverse('class-list'), {'school_id': other_school.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item['name'] for item in response.data.get('results', response.data)]
        self.assertIn('Other Class', names)
        self.assertNotIn('Class 1', names)

    def test_super_admin_sees_all_schools_without_filter(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.super_token.key}')
        response = self.client.get(reverse('class-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item['name'] for item in response.data.get('results', response.data)]
        self.assertIn('Class 1', names)
