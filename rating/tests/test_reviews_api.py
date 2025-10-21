"""
Tests for the reviews API.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
import json

from rating.models import Review

User = get_user_model()

class ReviewAPITestCase(TestCase):
    def setUp(self):
        # Create test users
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='testuser1@example.com',
            password='testpassword123',
            first_name='Test',
            last_name='User1'
        )
        
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='testuser2@example.com',
            password='testpassword123',
            first_name='Test',
            last_name='User2'
        )
        
        # Create a review
        self.review = Review.objects.create(
            reviewer=self.user1,
            reviewed=self.user2,
            rating=4.5,
            feedback="Great work!"
        )
        
        # Set up the client
        self.client = Client()
        self.client.login(username='testuser1', password='testpassword123')
    
    def test_get_reviews_for_user(self):
        """Test getting reviews for a user."""
        url = f'/rating/ratings/reviewed_{self.user2.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Check that the response contains the expected data
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data']['user_id'], self.user2.id)
        self.assertEqual(data['data']['username'], self.user2.username)
        self.assertEqual(data['data']['full_name'], 'Test User2')
        self.assertEqual(len(data['data']['reviews']), 1)
        
        # Check the review data
        review_data = data['data']['reviews'][0]
        self.assertEqual(review_data['reviewer_id'], self.user1.id)
        self.assertEqual(review_data['reviewer_name'], 'Test User1')
        self.assertEqual(float(review_data['rating']), 4.5)
        self.assertEqual(review_data['feedback'], 'Great work!')
    
    def test_get_reviews_by_user(self):
        """Test getting reviews given by a user."""
        url = f'/rating/ratings/reviewer_{self.user1.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Check that the response contains the expected data
        self.assertEqual(data['user_id'], self.user1.id)
        self.assertEqual(data['username'], self.user1.username)
        self.assertEqual(data['full_name'], 'Test User1')
        self.assertEqual(data['total_reviews_given'], 1)
        self.assertEqual(len(data['reviews']), 1)
        
        # Check the review data
        review_data = data['reviews'][0]
        self.assertEqual(review_data['reviewed']['id'], self.user2.id)
        self.assertEqual(review_data['reviewed']['username'], self.user2.username)
        self.assertEqual(review_data['reviewed']['name'], 'Test User2')
        self.assertEqual(float(review_data['rating']), 4.5)
        self.assertEqual(review_data['feedback'], 'Great work!')
