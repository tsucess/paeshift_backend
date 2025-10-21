# # tests/test_base.py
# from django.test import TestCase
# from django.contrib.auth import get_user_model
# from ninja.testing import TestClient
# from jobs.models import Job, JobIndustry, JobSubCategory, Profile, Application, SavedJob, Review, Dispute
# from jobs.api import router
# # jobs/tests.py
# from jobs.models import Job, JobIndustry, JobSubCategory, Profile, Application, SavedJob  # Removed Review, Dispute
# User = get_user_model()
# jobs/tests.py
#         self.job = Job.objects.create(
#             client=self.employer,
#             title='Test Job',
#             industry=self.industry,
#             subcategory=self.subcategory,
#             applicants_needed=2,
#             date='2023-12-31',
#             start_time='09:00',
#             end_time='17:00',
#             rate=50.00,
#             location='Test Location',
#             latitude=40.7128,
#             longitude=-74.0060
#         )
# jobs/tests.py
from django.test import TestCase

from jobs.models import (  # Removed Review, Dispute; import your models
    Application, Job, JobIndustry, JobSubCategory, Profile, SavedJob)

# class PaeShiftTestBase(TestCase):
#     def setUp(self):
#         self.client = TestClient(router)
#         self.user = User.objects.create_user(
#             username='testuser',
#             email='test@example.com',
#             password='testpass123',
#             first_name='Test',
#             last_name='User'
#         )
#         self.profile = Profile.objects.create(user=self.user, role='worker')

#         self.employer = User.objects.create_user(
#             username='employer',
#             email='employer@example.com',
#             password='employerpass123',
#             first_name='Employer',
#             last_name='User'
#         )
#         self.employer_profile = Profile.objects.create(user=self.employer, role='employer')

#         self.industry = JobIndustry.objects.create(name='Technology')
#         self.subcategory = JobSubCategory.objects.create(name='Web Development', industry=self.industry)


class ModelTests(TestCase):
    def test_job_creation(self):
        job = Job.objects.create(title="Test Job")
        self.assertEqual(str(job), "Test Job")

    def test_industry_creation(self):
        industry = JobIndustry.objects.create(name="Tech")
        self.assertEqual(industry.name, "Tech")


# # tests/test_auth.py
# from django.urls import reverse
# from rest_framework_simplejwt.tokens import RefreshToken
# from .test_base import PaeShiftTestBase

# class AuthenticationTests(PaeShiftTestBase):
#     def test_user_signup(self):
#         response = self.client.post('/signup', json={
#             'email': 'newuser@example.com',
#             'password': 'newpass123',
#             'first_name': 'New',
#             'last_name': 'User',
#             'role': 'worker'
#         })
#         self.assertEqual(response.status_code, 200)
#         self.assertTrue(User.objects.filter(email='newuser@example.com').exists())

#     def test_user_login(self):
#         response = self.client.post('/login', json={
#             'email': 'test@example.com',
#             'password': 'testpass123'
#         })
#         self.assertEqual(response.status_code, 200)
#         self.assertIn('access_token', response.json())
#         self.assertIn('refresh_token', response.json())

#     def test_invalid_login(self):
#         response = self.client.post('/login', json={
#             'email': 'test@example.com',
#             'password': 'wrongpassword'
#         })
#         self.assertEqual(response.status_code, 401)
#         self.assertEqual(response.json()['error'], 'Invalid credentials')

#     def test_password_reset(self):
#         # First request reset link
#         response = self.client.post('/reset-password', json={
#             'email': 'test@example.com'
#         })
#         self.assertEqual(response.status_code, 200)

#         # Then actually reset password (would need token simulation)
#         token = default_token_generator.make_token(self.user)
#         uid = urlsafe_base64_encode(force_bytes(self.user.pk))

#         response = self.client.post(f'/reset-password-confirm/{uid}/{token}/', json={
#             'new_password': 'newsecurepass123'
#         })
#         self.assertEqual(response.status_code, 200)

#         # Verify new password works
#         self.assertTrue(self.client.login(email='test@example.com', password='newsecurepass123'))

# # tests/test_jobs.py
# from decimal import Decimal
# from datetime import datetime, timedelta
# from django.utils import timezone
# from .test_base import PaeShiftTestBase

# class JobTests(PaeShiftTestBase):
#     def test_create_job(self):
#         self.client.force_login(self.employer)
#         response = self.client.post('/create-job', json={
#             'title': 'New Job',
#             'industry': self.industry.id,
#             'subcategory': self.subcategory.id,
#             'applicants_needed': 3,
#             'job_type': 'full_time',
#             'shift_type': 'morning',
#             'date': '2023-12-25',
#             'start_time': '08:00',
#             'end_time': '16:00',
#             'rate': '75.50',
#             'location': 'New Location'
#         })
#         self.assertEqual(response.status_code, 201)
#         self.assertEqual(Job.objects.count(), 2)

#         job_data = response.json()
#         self.assertEqual(job_data['duration'], '8.0')

#     def test_get_job_detail(self):
#         response = self.client.get(f'/{self.job.id}')
#         self.assertEqual(response.status_code, 200)
#         data = response.json()
#         self.assertEqual(data['title'], 'Test Job')
#         self.assertEqual(data['client_username'], 'employer')

#     def test_job_cancellation(self):
#         self.client.force_login(self.employer)
#         response = self.client.put(f'/job/cancel/{self.job.id}/')
#         self.assertEqual(response.status_code, 200)

#         self.job.refresh_from_db()
#         self.assertEqual(self.job.status, 'cancelled')

#     def test_job_deletion(self):
#         self.client.force_login(self.employer)
#         response = self.client.delete(f'/job/delete/{self.job.id}')
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(Job.objects.count(), 0)

#     def test_serialize_job(self):
#         from jobs.api import serialize_job
#         serialized = serialize_job(self.job)

#         self.assertEqual(serialized['title'], 'Test Job')
#         self.assertEqual(serialized['client_username'], 'employer')
#         self.assertEqual(serialized['applicants_count'], 0)
#         self.assertTrue('is_this_week' in serialized)


# # tests/test_matching.py
# from django.contrib.gis.geos import Point
# from .test_base import PaeShiftTestBase

# class ApplicantMatchingTests(PaeShiftTestBase):
#     def setUp(self):
#         super().setUp()
#         # Create test applicants with different locations
#         self.applicant1 = User.objects.create_user(
#             username='applicant1',
#             email='applicant1@example.com',
#             password='testpass123'
#         )
#         self.profile1 = Profile.objects.create(
#             user=self.applicant1,
#             role='worker',
#             industry=self.industry,
#             subcategory=self.subcategory,
#             last_location=Point(-74.0060, 40.7128)  # Same as job location
#         )

#         self.applicant2 = User.objects.create_user(
#             username='applicant2',
#             email='applicant2@example.com',
#             password='testpass123'
#         )
#         self.profile2 = Profile.objects.create(
#             user=self.applicant2,
#             role='worker',
#             industry=self.industry,
#             subcategory=self.subcategory,
#             last_location=Point(-74.5, 40.8)  # ~50km away
#         )

#     def test_find_best_applicants(self):
#         from jobs.api import find_best_applicants
#         best_applicants = find_best_applicants(self.job)

#         self.assertEqual(len(best_applicants), 2)
#         # Applicant1 should be first since they're closer
#         self.assertEqual(best_applicants[0].user.username, 'applicant1')

#     def test_haversine_calculation(self):
#         from jobs.api import haversine
#         # Distance between NYC and Philadelphia ~150km
#         distance = haversine(40.7128, -74.0060, 39.9526, -75.1652)
#         self.assertAlmostEqual(distance, 150, delta=5)

#     def test_calculate_distance_score(self):
#         from jobs.api import calculate_distance_score
#         score = calculate_distance_score(
#             40.7128, -74.0060,  # Job location (NYC)
#             40.7306, -73.9352,  # User location (Brooklyn)
#             50  # Max distance
#         )
#         self.assertGreater(score, 0.8)  # Should be close

# # tests/test_applications.py
# from .test_base import PaeShiftTestBase

# class ApplicationTests(PaeShiftTestBase):
#     def test_apply_for_job(self):
#         self.client.force_login(self.user)
#         response = self.client.post('/apply-job/', json={
#             'user_id': self.user.id,
#             'job_id': self.job.id
#         })
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(Application.objects.count(), 1)

#         application = Application.objects.first()
#         self.assertEqual(application.status, 'applied')

#     def test_get_applied_jobs(self):
#         # First create an application
#         Application.objects.create(
#             job=self.job,
#             applicant=self.user,
#             employer=self.employer,
#             status='applied'
#         )

#         self.client.force_login(self.user)
#         response = self.client.get(f'/applicantjobs/{self.user.id}')
#         self.assertEqual(response.status_code, 200)

#         data = response.json()
#         self.assertEqual(len(data['jobs_applied']), 1)
#         self.assertEqual(data['jobs_applied'][0]['id'], self.job.id)

#     def test_save_job(self):
#         self.client.force_login(self.user)
#         response = self.client.post('/save-job/add/', json={
#             'user_id': self.user.id,
#             'job_id': self.job.id
#         })
#         self.assertEqual(response.status_code, 200)
#         self.assertTrue(SavedJob.objects.filter(user=self.user, job=self.job).exists())

#     def test_unsave_job(self):
#         SavedJob.objects.create(user=self.user, job=self.job)
#         self.client.force_login(self.user)
#         response = self.client.delete('/unsave-job/', json={
#             'user_id': self.user.id,
#             'job_id': self.job.id
#         })
#         self.assertEqual(response.status_code, 200)
#         self.assertFalse(SavedJob.objects.filter(user=self.user, job=self.job).exists())

# # tests/test_reviews.py
# from .test_base import PaeShiftTestBase

# class ReviewTests(PaeShiftTestBase):
#     def test_create_review(self):
#         self.client.force_login(self.employer)
#         response = self.client.post(
#             f'/ratings/reviewer_{self.employer.id}/reviewed_{self.user.id}/',
#             json={
#                 'rating': 5,
#                 'feedback': 'Excellent work!',
#                 'job': self.job.id
#             }
#         )
#         self.assertEqual(response.status_code, 201)
#         self.assertEqual(Review.objects.count(), 1)

#         review = Review.objects.first()
#         self.assertEqual(review.rating, 5)
#         self.assertEqual(review.feedback, 'Excellent work!')

#     def test_get_user_ratings(self):
#         Review.objects.create(
#             reviewer=self.employer,
#             reviewed=self.user,
#             rating=4,
#             feedback='Good work',
#             job=self.job
#         )

#         response = self.client.get(f'/ratings/{self.user.id}')
#         self.assertEqual(response.status_code, 200)

#         data = response.json()
#         self.assertEqual(data['username'], 'testuser')
#         self.assertEqual(data['average_rating'], 4.0)
#         self.assertEqual(len(data['ratings']), 1)

#     def test_get_applicant_reviews(self):
#         Review.objects.create(
#             reviewer=self.employer,
#             reviewed=self.user,
#             rating=5,
#             feedback='Perfect!',
#             job=self.job
#         )

#         self.client.force_login(self.user)
#         response = self.client.post('/jobs/reviews', json={
#             'applicant_id': self.user.id
#         })
#         self.assertEqual(response.status_code, 200)

#         data = response.json()
#         self.assertEqual(data['average_rating'], 5.0)
#         self.assertEqual(len(data['reviews']), 1)


# # tests/test_shifts.py
# from django.utils import timezone
# from .test_base import PaeShiftTestBase

# class ShiftTests(PaeShiftTestBase):
#     def test_shift_lifecycle(self):
#         # First create an application and accept it
#         application = Application.objects.create(
#             job=self.job,
#             applicant=self.user,
#             employer=self.employer,
#             status='accepted'
#         )

#         self.client.force_login(self.employer)

#         # Start shift
#         response = self.client.post(f'/start-shift/{self.job.id}')
#         self.assertEqual(response.status_code, 200)
#         self.job.refresh_from_db()
#         self.assertTrue(self.job.is_shift_ongoing)

#         # End shift
#         response = self.client.post(f'/end-shift/{self.job.id}')
#         self.assertEqual(response.status_code, 200)
#         self.job.refresh_from_db()
#         self.assertFalse(self.job.is_shift_ongoing)
#         self.assertEqual(self.job.status, 'completed')

#     def test_shift_scheduling(self):
#         self.client.force_login(self.employer)
#         response = self.client.post(f'/jobs/{self.job.id}/shifts', json={
#             'shiftType': 'night',
#             'startTime': '20:00',
#             'endTime': '04:00'
#         })
#         self.assertEqual(response.status_code, 200)

#         # In a real implementation, we'd verify the shift was created
#         self.assertEqual(response.json()['shift']['shiftType'], 'night')


# # tests/test_disputes.py
# from .test_base import PaeShiftTestBase

# class DisputeTests(PaeShiftTestBase):
#     def test_create_dispute(self):
#         self.client.force_login(self.user)
#         response = self.client.post('/jobs/disputes', json={
#             'job_id': self.job.id,
#             'user_id': self.user.id,
#             'title': 'Payment issue',
#             'description': 'Not paid for completed work'
#         })
#         self.assertEqual(response.status_code, 201)
#         self.assertEqual(Dispute.objects.count(), 1)

#         dispute = Dispute.objects.first()
#         self.assertEqual(dispute.title, 'Payment issue')
#         self.assertEqual(dispute.status, 'open')

#     def test_list_job_disputes(self):
#         Dispute.objects.create(
#             job=self.job,
#             created_by=self.user,
#             title='Test Dispute',
#             description='Test description'
#         )

#         response = self.client.get(f'/jobs/{self.job.id}/disputes')
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(len(response.json()), 1)
#         self.assertEqual(response.json()[0]['title'], 'Test Dispute')

#     def test_update_dispute(self):
#         dispute = Dispute.objects.create(
#             job=self.job,
#             created_by=self.user,
#             title='Test Dispute',
#             description='Test description'
#         )

#         self.client.force_login(self.user)
#         response = self.client.put(f'/disputes/{dispute.id}', json={
#             'status': 'resolved'
#         })
#         self.assertEqual(response.status_code, 200)

#         dispute.refresh_from_db()
#         self.assertEqual(dispute.status, 'resolved')


# # tests/test_missed_functions.py
# from django.test import TestCase
# from django.contrib.auth import get_user_model
# from ninja.testing import TestClient
# from jobs.models import JobIndustry, JobSubCategory, Profile, Application
# from jobs.api import router

# User = get_user_model()

# class MissedFunctionTests(TestCase):
#     def setUp(self):
#         self.client = TestClient(router)
#         self.user = User.objects.create_user(
#             email='test@example.com',
#             password='testpass123',
#             first_name='Test',
#             last_name='User'
#         )
#         self.profile = Profile.objects.create(user=self.user)

#         self.industry = JobIndustry.objects.create(name='Construction')
#         self.subcategory = JobSubCategory.objects.create(
#             name='Carpentry',
#             industry=self.industry
#         )

#     # --------------------------
#     # Core Helper Function Tests
#     # --------------------------
#     def test_authenticated_user_or_error(self):
#         from jobs.api import authenticated_user_or_error

#         # Unauthenticated request
#         class MockRequest:
#             user = User()
#             user.is_authenticated = False

#         user, error = authenticated_user_or_error(MockRequest())
#         self.assertIsNone(user)
#         self.assertEqual(error.status_code, 401)

#         # Authenticated request
#         MockRequest.user.is_authenticated = True
#         user, error = authenticated_user_or_error(MockRequest())
#         self.assertEqual(user, MockRequest.user)
#         self.assertIsNone(error)

#     def test_get_related_object(self):
#         from jobs.api import get_related_object

#         # Valid industry
#         obj, error = get_related_object(JobIndustry, 'id', self.industry.id)
#         self.assertEqual(obj, self.industry)
#         self.assertIsNone(error)

#         # Invalid industry
#         obj, error = get_related_object(JobIndustry, 'id', 999)
#         self.assertIsNone(obj)
#         self.assertEqual(error.status_code, 400)

#     def test_calculate_distance_score_edge_cases(self):
#         from jobs.api import calculate_distance_score

#         # Test missing coordinates
#         score = calculate_distance_score(None, None, 40.7128, -74.0060)
#         self.assertEqual(score, 0)

#         # Test exact location match
#         score = calculate_distance_score(
#             40.7128, -74.0060,
#             40.7128, -74.0060,
#             max_distance_km=50
#         )
#         self.assertEqual(score, 1.0)

#         # Test beyond max distance
#         score = calculate_distance_score(
#             40.7128, -74.0060,  # NYC
#             51.5074, -0.1278,    # London
#             max_distance_km=50
#         )
#         self.assertEqual(score, 0)

#     # ----------------------------
#     # Authentication Endpoint Tests
#     # ----------------------------
#     def test_whoami_endpoint(self):
#         self.client.force_login(self.user)
#         response = self.client.get(f'/whoami/{self.user.id}')

#         self.assertEqual(response.status_code, 200)
#         data = response.json()
#         self.assertEqual(data['user_id'], self.user.id)
#         self.assertEqual(data['first_name'], 'Test')
#         self.assertEqual(data['last_name'], 'User')
#         self.assertIn('job_stats', data)

#     def test_get_logged_in_user(self):
#         # Authenticated
#         self.client.force_login(self.user)
#         response = self.client.get('/authenticate')
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(response.json()['email'], 'test@example.com')

#         # Unauthenticated
#         self.client.logout()
#         response = self.client.get('/authenticate')
#         self.assertEqual(response.status_code, 401)

#     def test_update_profile(self):
#         self.client.force_login(self.user)
#         response = self.client.put('/profile', json={
#             'user_id': self.user.id,
#             'first_name': 'Updated',
#             'last_name': 'Name',
#             'email': 'updated@example.com'
#         })

#         self.assertEqual(response.status_code, 200)
#         self.user.refresh_from_db()
#         self.assertEqual(self.user.first_name, 'Updated')
#         self.assertEqual(self.user.email, 'updated@example.com')

#     def test_email_password_reset(self):
#         response = self.client.post('/reset-password', json={
#             'email': 'test@example.com'
#         })
#         self.assertEqual(response.status_code, 200)
#         self.assertIn('message', response.json())

#     # ----------------------
#     # Job Endpoint Tests
#     # ----------------------
#     def test_get_job_industries(self):
#         response = self.client.get('/job-industries/')
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(len(response.json()), 1)
#         self.assertEqual(response.json()[0]['name'], 'Construction')

#     def test_get_job_subcategories(self):
#         response = self.client.get('/job-subcategories/')
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(len(response.json()), 1)
#         self.assertEqual(response.json()[0]['name'], 'Carpentry')

#     def test_get_client_jobs(self):
#         job = Job.objects.create(
#             client=self.user,
#             title='Test Job',
#             industry=self.industry,
#             subcategory=self.subcategory
#         )

#         response = self.client.get(f'/clientjobs/{self.user.id}')
#         self.assertEqual(response.status_code, 200)
#         data = response.json()
#         self.assertEqual(len(data['jobs']), 1)
#         self.assertEqual(data['jobs'][0]['title'], 'Test Job')

#     def test_get_applicants_worked_with(self):
#         # Create completed job with applicant
#         job = Job.objects.create(
#             client=self.user,
#             title='Completed Job',
#             status='completed'
#         )
#         applicant = User.objects.create_user(email='worker@example.com')
#         Application.objects.create(
#             job=job,
#             applicant=applicant,
#             status='accepted'
#         )

#         response = self.client.get(f'/client/workers/list/{self.user.id}/')
#         self.assertEqual(response.status_code, 200)
#         data = response.json()
#         self.assertEqual(len(data['applicants']), 1)
#         self.assertEqual(data['applicants'][0]['email'], 'worker@example.com')

#     # --------------------------
#     # Utility Function Tests
#     # --------------------------
#     def test_fetch_all_users(self):
#         from jobs.api import fetch_all_users
#         users = fetch_all_users()
#         self.assertEqual(len(users), 1)
#         self.assertEqual(users[0]['email'], 'test@example.com')

#     def test_get_nearby_applicants(self):
#         from jobs.api import get_nearby_applicants

#         # Create job with location
#         job = Job.objects.create(
#             client=self.user,
#             latitude=40.7128,
#             longitude=-74.0060,  # NYC
#             location='{"latitude": 40.7128, "longitude": -74.0060}'
#         )

#         # Create nearby applicant
#         applicant = User.objects.create_user(email='nearby@example.com')
#         Application.objects.create(
#             job=job,
#             applicant=applicant,
#             latitude=40.7128,
#             longitude=-74.0060
#         )

#         nearby = get_nearby_applicants(job)
#         self.assertEqual(len(nearby), 1)
#         self.assertEqual(nearby[0]['applicant_id'], applicant.id)

#     def test_get_industry_or_subcategory(self):
#         from jobs.api import get_industry_or_subcategory

#         # Test ID lookup
#         result = get_industry_or_subcategory(JobIndustry, str(self.industry.id))
#         self.assertEqual(result, self.industry)

#         # Test name lookup
#         result = get_industry_or_subcategory(JobIndustry, 'Construction')
#         self.assertEqual(result, self.industry)

#         # Test invalid lookup
#         with self.assertRaises(Exception):
#             get_industry_or_subcategory(JobIndustry, 'Invalid')
