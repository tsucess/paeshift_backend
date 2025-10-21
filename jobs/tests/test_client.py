# jobs/tests/untests/test_api.py jobs/tests/untests/test_applicant.py jobs/tests/untests/test_integration.py
from decimal import Decimal
from unittest.mock import patch

from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone
from ninja.testing import TestClient

from jobs.api import core_router as api  # Import core_router instead of api
from jobs.models import (Application, Job, JobIndustry, JobSubCategory,
                         UserLocation)

from .tests.base import PayshiftTestCase

# class AuthAPITests(TestCase):
#     def setUp(self):
#         self.factory = RequestFactory()
#         self.client = TestClient(api)
#         # Create a session-enabled test client
#         # self.session_client = self.client.get_client()
#         # self.session_client.handler._middleware = self._get_middleware()

#     def _get_middleware(self):
#         from django.contrib.sessions.middleware import SessionMiddleware
#         from django.contrib.auth.middleware import AuthenticationMiddleware
#         return [SessionMiddleware, AuthenticationMiddleware]

#     def _add_session_to_request(self, request):
#         """Helper method to add session to request"""
#         middleware = SessionMiddleware(lambda x: None)
#         middleware.process_request(request)
#         request.session.save()

#     def test_login_success(self):
#         request = self.factory.post('/api/jobs/login')
#         self._add_session_to_request(request)
#         response = self.client.post(
#             '/login',
#             json={
#                 'email': 'test@example.com',
#                 'password': 'testpass123'
#             }
#         )
#         # self.assertEqual(response.status_code, 200)


# class ApplicationModelTests(PayshiftTestCase):
#     def test_successful_application_creation(self):
#         """Test valid application creation through model"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )
#         self.assertEqual(application.job, self.active_job)
#         self.assertEqual(application.applicant, self.applicant)
#         self.assertEqual(application.status, 'pending')

#     def setUp(self):
#         """Initialize fresh test data for each test"""
#         # Create active job for each test
#         self.active_job = Job.objects.create(
#             client=self.employer,
#             title='Senior Django Developer',
#             industry=self.industry,
#             subcategory=self.subcategory,
#             applicants_needed=3,
#             date=timezone.now().date() + timezone.timedelta(days=14),
#             start_time='09:00:00',
#             end_time='17:00:00',
#             rate=Decimal('75.00'),
#             location='Remote',
#             is_active=True,
#             status=Job.Status.PENDING
#         )

#         # Create test client for API endpoints
#         self.client = TestClient(api)

#     # --- CORE APPLICATION FUNCTIONALITY TESTS ---
#     def test_successful_application_creation(self):
#         """Test valid application creation through model"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )

#         self.assertEqual(application.status, 'applied')
#         self.assertEqual(application.job, self.active_job)
#         self.assertEqual(application.applicant, self.applicant)
#         self.assertIsNotNone(application.applied_at)
#         self.assertFalse(application.is_shown_up)

#     def test_application_string_representation(self):
#         """Test application model string formatting"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )
#         expected_str = f"{self.applicant} - {self.active_job} (Applied)"
#         self.assertEqual(str(application), expected_str)

#     # --- APPLICATION STATUS TRANSITIONS ---
#     def test_application_status_flow(self):
#         """Test full lifecycle of an application status"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )

#         # Test shortlisting
#         application.shortlist()
#         self.assertEqual(application.status, 'shortlisted')

#         # Test acceptance
#         application.accept()
#         self.assertEqual(application.status, 'accepted')
#         self.active_job.refresh_from_db()
#         self.assertEqual(self.active_job.selected_applicant, self.applicant)

#         # Test rejection
#         application.reject()
#         self.assertEqual(application.status, 'rejected')

#     # --- VALIDATION & CONSTRAINTS ---
#     def test_duplicate_application_prevention(self):
#         """Test unique constraint for applications"""
#         Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )

#         with self.assertRaises(ValidationError):
#             duplicate = Application(
#                 job=self.active_job,
#                 applicant=self.applicant,
#                 employer=self.employer
#             )
#             duplicate.full_clean()

#     def test_application_to_inactive_job(self):
#         """Test applications to inactive job listings"""
#         inactive_job = Job.objects.create(
#             client=self.employer,
#             title='Inactive Position',
#             industry=self.tech_industry,
#             subcategory=self.webdev_subcategory,
#             applicants_needed=1,
#             date=timezone.now().date() + timezone.timedelta(days=14),
#             start_time='09:00:00',
#             end_time='17:00:00',
#             rate=Decimal('75.00'),
#             location='Remote',
#             is_active=False,
#             status=Job.Status.CANCELED
#         )

#         with self.assertRaises(ValidationError):
#             application = Application(
#                 job=inactive_job,
#                 applicant=self.applicant,
#                 employer=self.employer
#             )
#             application.full_clean()

#     # --- LOCATION TRACKING ---
#     def test_application_location_tracking(self):
#         """Test location data storage for applications"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer,
#             latitude=40.7128,
#             longitude=-74.0060
#         )

#         self.assertEqual(application.location_coordinates, (40.7128, -74.0060))
#         self.assertTrue(-90 <= application.latitude <= 90)
#         self.assertTrue(-180 <= application.longitude <= 180)

#     # --- API ENDPOINT TESTS ---
#     @patch('channels.layers.get_channel_layer')
#     def test_api_application_submission(self, mock_channel):
#         """Test application submission through API endpoint"""
#         mock_channel.return_value = get_channel_layer()

#         response = self.client.post('/signup', {
#             'email': 'duplicate@example.com',
#             'password': 'securepassword'
#         })
#         self.assertEqual(response.status_code, 422)  # Adjust this if the implementation is incorrect


#     def test_api_invalid_application(self):
#         """Test invalid application through API"""
#         response = self.client.post(
#             '/applications/apply/',
#             json={
#                 'applicant_id': 9999,
#                 'job_id': self.active_job.id
#             }
#         )

#         self.assertEqual(response.status_code, 404)
#         self.assertIn('User not found', response.json()['detail'])

#     # --- EDGE CASES ---
#     def test_application_to_completed_job(self):
#         """Test applications to already completed jobs"""
#         completed_job = Job.objects.create(
#             client=self.employer,
#             title='Completed Project',
#             industry=self.tech_industry,
#             subcategory=self.webdev_subcategory,
#             applicants_needed=1,
#             date=timezone.now().date() + timezone.timedelta(days=14),
#             start_time='09:00:00',
#             end_time='17:00:00',
#             rate=Decimal('75.00'),
#             location='Remote',
#             is_active=True,
#             status=Job.Status.COMPLETED
#         )

#         with self.assertRaises(ValidationError):
#             Application(
#                 job=completed_job,
#                 applicant=self.applicant,
#                 employer=self.employer
#             ).full_clean()

#     def test_application_rating_validation(self):
#         """Test rating validation constraints"""
#         valid_application = Application(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer,
#             rating=4.5
#         )
#         valid_application.full_clean()  # Should not raise

#         with self.assertRaises(ValidationError):
#             invalid_application = Application(
#                 job=self.active_job,
#                 applicant=self.applicant,
#                 employer=self.employer,
#                 rating=5.1
#             )
#             invalid_application.full_clean()

#     # --- PERFORMANCE METRICS ---
#     def test_application_timestamps(self):
#         """Test automatic timestamp generation"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )

#         self.assertIsNotNone(application.applied_at)
#         self.assertTrue(timezone.now() - application.applied_at < timezone.timedelta(seconds=1))

#     def tearDown(self):
#         """Cleanup after tests"""
#         Application.objects.all().delete()
#         Job.objects.all().delete()


#     def setUp(self):
#         # Change this to include username
#         self.test_user = User.objects.create_user(
#             username='test@example.com',  # Add username
#             email='test@example.com',
#             password='testpass123'
#         )
#         self.client = TestClient(api)

#     def test_login_success(self):
#         response = self.client.post(
#             '/login',
#             json={
#                 'email': 'test@example.com',
#                 'password': 'testpass123'
#             }
#         )
#         self.assertEqual(response.status_code, 200)

#     def test_login_invalid_credentials(self):
#         response = self.client.post(
#             '/login',
#             json={
#                 'email': 'test@example.com',
#                 'password': 'wrongpass'
#             }
#         )
#         self.assertEqual(response.status_code, 401)

#     def test_signup_success(self):
#         response = self.client.post(
#             '/signup',
#             json={
#                 'email': 'newuser@example.com',
#                 'password': 'newpass123',
#                 'first_name': 'New',
#                 'last_name': 'User',
#                 'role': 'applicant'
#             }
#         )
#         # self.assertEqual(response.status_code, 200)

#     def test_signup_duplicate_email(self):
#         # First create a user
#         User.objects.create_user(
#             username='existing@example.com',  # Add username
#             email='existing@example.com',
#             password='existingpass123'
#         )

#         # Try to create duplicate
#         response = self.client.post(
#             '/signup',
#             json={
#                 'email': 'existing@example.com',
#                 'password': 'newpass123',
#                 'first_name': 'Test',
#                 'last_name': 'User',
#                 'role': 'applicant'
#             }
#         )
#         # self.assertEqual(response.status_code, 400)

#     def test_whoami_authenticated(self):
#         # Login first
#         self.client.post(
#             '/login',
#             json={
#                 'email': 'test@example.com',
#                 'password': 'testpass123'
#             }
#         )
#         response = self.client.get(f'/whoami/{self.test_user.id}')
#         self.assertEqual(response.status_code, 200)

#     def test_whoami_unauthenticated(self):
#         response = self.client.get('/whoami/999')  # Non-existent user
#         self.assertEqual(response.status_code, 404)





# class AuthAPITests(TestCase):
#     def setUp(self):
#         self.factory = RequestFactory()
#         self.client = TestClient(api)
#         # Create a session-enabled test client
#         # self.session_client = self.client.get_client()
#         # self.session_client.handler._middleware = self._get_middleware()

#     def _get_middleware(self):
#         from django.contrib.sessions.middleware import SessionMiddleware
#         from django.contrib.auth.middleware import AuthenticationMiddleware
#         return [SessionMiddleware, AuthenticationMiddleware]

#     def _add_session_to_request(self, request):
#         """Helper method to add session to request"""
#         middleware = SessionMiddleware(lambda x: None)
#         middleware.process_request(request)
#         request.session.save()

#     def test_login_success(self):
#         request = self.factory.post('/api/jobs/login')
#         self._add_session_to_request(request)
#         response = self.client.post(
#             '/login',
#             json={
#                 'email': 'test@example.com',
#                 'password': 'testpass123'
#             }
#         )
#         # self.assertEqual(response.status_code, 200)


# class ApplicationModelTests(PayshiftTestCase):
#     def test_successful_application_creation(self):
#         """Test valid application creation through model"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )
#         self.assertEqual(application.job, self.active_job)
#         self.assertEqual(application.applicant, self.applicant)
#         self.assertEqual(application.status, 'pending')

#     def setUp(self):
#         """Initialize fresh test data for each test"""
#         # Create active job for each test
#         self.active_job = Job.objects.create(
#             client=self.employer,
#             title='Senior Django Developer',
#             industry=self.industry,
#             subcategory=self.subcategory,
#             applicants_needed=3,
#             date=timezone.now().date() + timezone.timedelta(days=14),
#             start_time='09:00:00',
#             end_time='17:00:00',
#             rate=Decimal('75.00'),
#             location='Remote',
#             is_active=True,
#             status=Job.Status.PENDING
#         )

#         # Create test client for API endpoints
#         self.client = TestClient(api)

#     # --- CORE APPLICATION FUNCTIONALITY TESTS ---
#     def test_successful_application_creation(self):
#         """Test valid application creation through model"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )

#         self.assertEqual(application.status, 'applied')
#         self.assertEqual(application.job, self.active_job)
#         self.assertEqual(application.applicant, self.applicant)
#         self.assertIsNotNone(application.applied_at)
#         self.assertFalse(application.is_shown_up)

#     def test_application_string_representation(self):
#         """Test application model string formatting"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )
#         expected_str = f"{self.applicant} - {self.active_job} (Applied)"
#         self.assertEqual(str(application), expected_str)

#     # --- APPLICATION STATUS TRANSITIONS ---
#     def test_application_status_flow(self):
#         """Test full lifecycle of an application status"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )

#         # Test shortlisting
#         application.shortlist()
#         self.assertEqual(application.status, 'shortlisted')

#         # Test acceptance
#         application.accept()
#         self.assertEqual(application.status, 'accepted')
#         self.active_job.refresh_from_db()
#         self.assertEqual(self.active_job.selected_applicant, self.applicant)

#         # Test rejection
#         application.reject()
#         self.assertEqual(application.status, 'rejected')

#     # --- VALIDATION & CONSTRAINTS ---
#     def test_duplicate_application_prevention(self):
#         """Test unique constraint for applications"""
#         Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )

#         with self.assertRaises(ValidationError):
#             duplicate = Application(
#                 job=self.active_job,
#                 applicant=self.applicant,
#                 employer=self.employer
#             )
#             duplicate.full_clean()

#     def test_application_to_inactive_job(self):
#         """Test applications to inactive job listings"""
#         inactive_job = Job.objects.create(
#             client=self.employer,
#             title='Inactive Position',
#             industry=self.tech_industry,
#             subcategory=self.webdev_subcategory,
#             applicants_needed=1,
#             date=timezone.now().date() + timezone.timedelta(days=14),
#             start_time='09:00:00',
#             end_time='17:00:00',
#             rate=Decimal('75.00'),
#             location='Remote',
#             is_active=False,
#             status=Job.Status.CANCELED
#         )

#         with self.assertRaises(ValidationError):
#             application = Application(
#                 job=inactive_job,
#                 applicant=self.applicant,
#                 employer=self.employer
#             )
#             application.full_clean()

#     # --- LOCATION TRACKING ---
#     def test_application_location_tracking(self):
#         """Test location data storage for applications"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer,
#             latitude=40.7128,
#             longitude=-74.0060
#         )

#         self.assertEqual(application.location_coordinates, (40.7128, -74.0060))
#         self.assertTrue(-90 <= application.latitude <= 90)
#         self.assertTrue(-180 <= application.longitude <= 180)

#     # --- API ENDPOINT TESTS ---
#     @patch('channels.layers.get_channel_layer')
#     def test_api_application_submission(self, mock_channel):
#         """Test application submission through API endpoint"""
#         mock_channel.return_value = get_channel_layer()

#         response = self.client.post('/signup', {
#             'email': 'duplicate@example.com',
#             'password': 'securepassword'
#         })
#         self.assertEqual(response.status_code, 422)  # Adjust this if the implementation is incorrect


#     def test_api_invalid_application(self):
#         """Test invalid application through API"""
#         response = self.client.post(
#             '/applications/apply/',
#             json={
#                 'applicant_id': 9999,
#                 'job_id': self.active_job.id
#             }
#         )

#         self.assertEqual(response.status_code, 404)
#         self.assertIn('User not found', response.json()['detail'])

#     # --- EDGE CASES ---
#     def test_application_to_completed_job(self):
#         """Test applications to already completed jobs"""
#         completed_job = Job.objects.create(
#             client=self.employer,
#             title='Completed Project',
#             industry=self.tech_industry,
#             subcategory=self.webdev_subcategory,
#             applicants_needed=1,
#             date=timezone.now().date() + timezone.timedelta(days=14),
#             start_time='09:00:00',
#             end_time='17:00:00',
#             rate=Decimal('75.00'),
#             location='Remote',
#             is_active=True,
#             status=Job.Status.COMPLETED
#         )

#         with self.assertRaises(ValidationError):
#             Application(
#                 job=completed_job,
#                 applicant=self.applicant,
#                 employer=self.employer
#             ).full_clean()

#     def test_application_rating_validation(self):
#         """Test rating validation constraints"""
#         valid_application = Application(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer,
#             rating=4.5
#         )
#         valid_application.full_clean()  # Should not raise

#         with self.assertRaises(ValidationError):
#             invalid_application = Application(
#                 job=self.active_job,
#                 applicant=self.applicant,
#                 employer=self.employer,
#                 rating=5.1
#             )
#             invalid_application.full_clean()

#     # --- PERFORMANCE METRICS ---
#     def test_application_timestamps(self):
#         """Test automatic timestamp generation"""
#         application = Application.objects.create(
#             job=self.active_job,
#             applicant=self.applicant,
#             employer=self.employer
#         )

#         self.assertIsNotNone(application.applied_at)
#         self.assertTrue(timezone.now() - application.applied_at < timezone.timedelta(seconds=1))

#     def tearDown(self):
#         """Cleanup after tests"""
#         Application.objects.all().delete()
#         Job.objects.all().delete()


#     def setUp(self):
#         # Change this to include username
#         self.test_user = User.objects.create_user(
#             username='test@example.com',  # Add username
#             email='test@example.com',
#             password='testpass123'
#         )
#         self.client = TestClient(api)

#     def test_login_success(self):
#         response = self.client.post(
#             '/login',
#             json={
#                 'email': 'test@example.com',
#                 'password': 'testpass123'
#             }
#         )
#         self.assertEqual(response.status_code, 200)

#     def test_login_invalid_credentials(self):
#         response = self.client.post(
#             '/login',
#             json={
#                 'email': 'test@example.com',
#                 'password': 'wrongpass'
#             }
#         )
#         self.assertEqual(response.status_code, 401)

#     def test_signup_success(self):
#         response = self.client.post(
#             '/signup',
#             json={
#                 'email': 'newuser@example.com',
#                 'password': 'newpass123',
#                 'first_name': 'New',
#                 'last_name': 'User',
#                 'role': 'applicant'
#             }
#         )
#         # self.assertEqual(response.status_code, 200)

#     def test_signup_duplicate_email(self):
#         # First create a user
#         User.objects.create_user(
#             username='existing@example.com',  # Add username
#             email='existing@example.com',
#             password='existingpass123'
#         )

#         # Try to create duplicate
#         response = self.client.post(
#             '/signup',
#             json={
#                 'email': 'existing@example.com',
#                 'password': 'newpass123',
#                 'first_name': 'Test',
#                 'last_name': 'User',
#                 'role': 'applicant'
#             }
#         )
#         # self.assertEqual(response.status_code, 400)

#     def test_whoami_authenticated(self):
#         # Login first
#         self.client.post(
#             '/login',
#             json={
#                 'email': 'test@example.com',
#                 'password': 'testpass123'
#             }
#         )
#         response = self.client.get(f'/whoami/{self.test_user.id}')
#         self.assertEqual(response.status_code, 200)

#     def test_whoami_unauthenticated(self):
#         response = self.client.get('/whoami/999')  # Non-existent user
#         self.assertEqual(response.status_code, 404)
