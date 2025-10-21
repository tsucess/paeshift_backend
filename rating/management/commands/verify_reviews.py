"""
Management command to verify the reviews API without making HTTP requests.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rating.models import Review
from rating.api import get_reviews_for_user, get_reviews_by_user

User = get_user_model()

class Command(BaseCommand):
    help = 'Verify the reviews API without making HTTP requests'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Verifying reviews API...'))
        
        # Create test users if they don't exist
        try:
            user1, created1 = User.objects.get_or_create(
                username='testuser1',
                defaults={
                    'email': 'testuser1@example.com',
                    'first_name': 'Test',
                    'last_name': 'User1',
                    'role': 'client'
                }
            )
            if created1:
                user1.set_password('testpassword123')
                user1.save()
                self.stdout.write(self.style.SUCCESS(f'Created user {user1.username}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Found existing user {user1.username}'))
            
            user2, created2 = User.objects.get_or_create(
                username='testuser2',
                defaults={
                    'email': 'testuser2@example.com',
                    'first_name': 'Test',
                    'last_name': 'User2',
                    'role': 'worker'
                }
            )
            if created2:
                user2.set_password('testpassword123')
                user2.save()
                self.stdout.write(self.style.SUCCESS(f'Created user {user2.username}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Found existing user {user2.username}'))
            
            # Create a review if it doesn't exist
            review, created = Review.objects.get_or_create(
                reviewer=user1,
                reviewed=user2,
                defaults={
                    'rating': 4.5,
                    'feedback': 'Great work!'
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created review from {user1.username} to {user2.username}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Found existing review from {user1.username} to {user2.username}'))
            
            # Create a request factory
            factory = RequestFactory()
            
            # Test get_reviews_for_user
            self.stdout.write(self.style.SUCCESS('Testing get_reviews_for_user...'))
            request = factory.get(f'/rating/ratings/reviewed_{user2.id}/')
            request.user = user1
            
            try:
                response = get_reviews_for_user(request, user2.id)
                self.stdout.write(self.style.SUCCESS('Function call successful!'))
                
                # Check the response
                if hasattr(response, 'content'):
                    import json
                    data = json.loads(response.content)
                    
                    # Check that the response contains the expected data
                    if data.get('status') == 'success':
                        self.stdout.write(self.style.SUCCESS('Response status is success'))
                    else:
                        self.stdout.write(self.style.ERROR(f'Response status is not success: {data.get("status")}'))
                    
                    if data.get('data', {}).get('user_id') == user2.id:
                        self.stdout.write(self.style.SUCCESS('User ID matches'))
                    else:
                        self.stdout.write(self.style.ERROR(f'User ID does not match: {data.get("data", {}).get("user_id")} != {user2.id}'))
                    
                    if data.get('data', {}).get('username') == user2.username:
                        self.stdout.write(self.style.SUCCESS('Username matches'))
                    else:
                        self.stdout.write(self.style.ERROR(f'Username does not match: {data.get("data", {}).get("username")} != {user2.username}'))
                    
                    if data.get('data', {}).get('full_name') == f'{user2.first_name} {user2.last_name}':
                        self.stdout.write(self.style.SUCCESS('Full name matches'))
                    else:
                        self.stdout.write(self.style.ERROR(f'Full name does not match: {data.get("data", {}).get("full_name")} != {user2.first_name} {user2.last_name}'))
                    
                    reviews = data.get('data', {}).get('reviews', [])
                    if len(reviews) == 1:
                        self.stdout.write(self.style.SUCCESS('Found 1 review'))
                    else:
                        self.stdout.write(self.style.ERROR(f'Found {len(reviews)} reviews, expected 1'))
                    
                    if reviews:
                        review_data = reviews[0]
                        if review_data.get('reviewer_id') == user1.id:
                            self.stdout.write(self.style.SUCCESS('Reviewer ID matches'))
                        else:
                            self.stdout.write(self.style.ERROR(f'Reviewer ID does not match: {review_data.get("reviewer_id")} != {user1.id}'))
                        
                        if review_data.get('reviewer_name') == f'{user1.first_name} {user1.last_name}':
                            self.stdout.write(self.style.SUCCESS('Reviewer name matches'))
                        else:
                            self.stdout.write(self.style.ERROR(f'Reviewer name does not match: {review_data.get("reviewer_name")} != {user1.first_name} {user1.last_name}'))
                        
                        if float(review_data.get('rating')) == 4.5:
                            self.stdout.write(self.style.SUCCESS('Rating matches'))
                        else:
                            self.stdout.write(self.style.ERROR(f'Rating does not match: {review_data.get("rating")} != 4.5'))
                        
                        if review_data.get('feedback') == 'Great work!':
                            self.stdout.write(self.style.SUCCESS('Feedback matches'))
                        else:
                            self.stdout.write(self.style.ERROR(f'Feedback does not match: {review_data.get("feedback")} != Great work!'))
                else:
                    self.stdout.write(self.style.ERROR('Response does not have content attribute'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error calling get_reviews_for_user: {str(e)}'))
            
            self.stdout.write(self.style.SUCCESS('Verification complete!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
