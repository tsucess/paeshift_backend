"""
Unit tests for rating API endpoints.
"""
import pytest
from django.contrib.auth import get_user_model
from ninja.testing import TestClient

from rating.api import rating_router
from rating.models import Review

User = get_user_model()


@pytest.mark.django_db
class TestRatingAPI:
    """Test suite for rating API endpoints."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(rating_router)

    def test_submit_rating_success(self, client_user, applicant_user, job):
        """Test successful rating submission."""
        payload = {
            'reviewer_id': client_user.id,
            'reviewed_id': applicant_user.id,
            'job_id': job.id,
            'rating': 5,
            'comment': 'Great work!'
        }
        response = self.client.post('/submit', json=payload)
        assert response.status_code == 201
        assert Review.objects.filter(
            reviewer=client_user,
            reviewed=applicant_user,
            job=job
        ).exists()

    def test_submit_rating_duplicate(self, review, client_user, applicant_user):
        """Test duplicate rating submission."""
        payload = {
            'reviewer_id': client_user.id,
            'reviewed_id': applicant_user.id,
            'job_id': review.job.id,
            'rating': 4,
            'comment': 'Updated comment'
        }
        response = self.client.post('/submit', json=payload)
        assert response.status_code == 409

    def test_submit_rating_invalid_rating(self, client_user, applicant_user, job):
        """Test rating with invalid rating value."""
        payload = {
            'reviewer_id': client_user.id,
            'reviewed_id': applicant_user.id,
            'job_id': job.id,
            'rating': 10,  # Invalid, should be 1-5
            'comment': 'Great work!'
        }
        response = self.client.post('/submit', json=payload)
        assert response.status_code == 400

    def test_submit_rating_self_rating(self, client_user, job):
        """Test self-rating (should fail)."""
        payload = {
            'reviewer_id': client_user.id,
            'reviewed_id': client_user.id,
            'job_id': job.id,
            'rating': 5,
            'comment': 'Self rating'
        }
        response = self.client.post('/submit', json=payload)
        assert response.status_code == 400

    def test_get_user_ratings(self, applicant_user, review):
        """Test getting user ratings."""
        response = self.client.get(f'/users/{applicant_user.id}/ratings')
        assert response.status_code == 200
        data = response.json()
        assert 'ratings' in data
        assert len(data['ratings']) > 0

    def test_get_user_average_rating(self, applicant_user, review):
        """Test getting user average rating."""
        response = self.client.get(f'/users/{applicant_user.id}/average-rating')
        assert response.status_code == 200
        data = response.json()
        assert 'average_rating' in data
        assert data['average_rating'] == 5.0

    def test_get_job_reviews(self, job, review):
        """Test getting job reviews."""
        response = self.client.get(f'/jobs/{job.id}/reviews')
        assert response.status_code == 200
        data = response.json()
        assert 'reviews' in data

    def test_update_rating_success(self, review, client_user):
        """Test updating a rating."""
        payload = {
            'rating': 4,
            'comment': 'Updated comment'
        }
        response = self.client.put(f'/{review.id}', json=payload)
        assert response.status_code == 200
        review.refresh_from_db()
        assert review.rating == 4

    def test_update_rating_unauthorized(self, review, applicant_user):
        """Test updating rating as non-reviewer."""
        payload = {
            'rating': 4,
            'comment': 'Updated comment'
        }
        response = self.client.put(f'/{review.id}', json=payload)
        assert response.status_code == 403

    def test_delete_rating_success(self, review, client_user):
        """Test deleting a rating."""
        payload = {'user_id': client_user.id}
        response = self.client.delete(f'/{review.id}', json=payload)
        assert response.status_code == 200
        assert not Review.objects.filter(id=review.id).exists()

    def test_get_leaderboard(self):
        """Test getting leaderboard."""
        response = self.client.get('/leaderboard')
        assert response.status_code == 200
        data = response.json()
        assert 'leaderboard' in data

    def test_get_user_feedback_count(self, applicant_user, review):
        """Test getting user feedback count."""
        response = self.client.get(f'/users/{applicant_user.id}/feedback-count')
        assert response.status_code == 200
        data = response.json()
        assert 'feedback_count' in data

    def test_submit_rating_nonexistent_user(self, client_user, job):
        """Test rating with nonexistent user."""
        payload = {
            'reviewer_id': client_user.id,
            'reviewed_id': 99999,
            'job_id': job.id,
            'rating': 5,
            'comment': 'Great work!'
        }
        response = self.client.post('/submit', json=payload)
        assert response.status_code == 404

    def test_submit_rating_nonexistent_job(self, client_user, applicant_user):
        """Test rating with nonexistent job."""
        payload = {
            'reviewer_id': client_user.id,
            'reviewed_id': applicant_user.id,
            'job_id': 99999,
            'rating': 5,
            'comment': 'Great work!'
        }
        response = self.client.post('/submit', json=payload)
        assert response.status_code == 404

