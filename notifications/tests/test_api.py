"""
Tests for the notifications API.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
import json

from notifications.models import NotificationPreference

User = get_user_model()

class NotificationAPITestCase(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpassword123',
            first_name='Test',
            last_name='User'
        )
        
        # Create notification preferences for the user
        self.preferences = NotificationPreference.objects.create(user=self.user)
        
        # Set up the client
        self.client = Client()
        self.client.login(username='testuser', password='testpassword123')
        
    def test_get_notification_settings(self):
        """Test getting notification settings."""
        url = reverse('notifications_api:get_notification_settings')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Check that the response contains push and email preferences
        self.assertIn('push', data)
        self.assertIn('email', data)
        
    def test_update_single_preference(self):
        """Test updating a single notification preference."""
        url = reverse('notifications_api:update_single_preference')
        
        # Test updating a push preference
        payload = {
            'preference_type': 'push',
            'category': 'job_acceptance',
            'value': False
        }
        
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Check that the response indicates success
        self.assertEqual(data['status'], 'success')
        
        # Check that the preference was updated
        self.preferences.refresh_from_db()
        self.assertFalse(self.preferences.push_preferences['job_acceptance'])
        
        # Test updating an email preference
        payload = {
            'preference_type': 'email',
            'category': 'new_job_alert',
            'value': True
        }
        
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Check that the response indicates success
        self.assertEqual(data['status'], 'success')
        
        # Check that the preference was updated
        self.preferences.refresh_from_db()
        self.assertTrue(self.preferences.email_preferences['new_job_alert'])
        
    def test_update_single_preference_with_frontend_category(self):
        """Test updating a single notification preference with frontend category names."""
        url = reverse('notifications_api:update_single_preference')
        
        # Test updating a push preference with frontend category name
        payload = {
            'preference_type': 'push',
            'category': 'jobrequest',  # Frontend name for job_acceptance
            'value': False
        }
        
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Check that the response indicates success
        self.assertEqual(data['status'], 'success')
        
        # Check that the preference was updated
        self.preferences.refresh_from_db()
        self.assertFalse(self.preferences.push_preferences['job_acceptance'])
