"""
Management command to create sample reviews for a user.
"""
import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rating.models import Review

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample reviews for a user'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username to create reviews for')
        parser.add_argument('--count', type=int, default=10, help='Number of reviews to create')

    def handle(self, *args, **options):
        username = options.get('username', 'fakoredeabbas')
        count = options.get('count', 10)
        
        self.stdout.write(self.style.SUCCESS(f'Creating {count} reviews for user {username}'))
        
        try:
            # Try to find the user
            try:
                user = User.objects.get(username=username)
                self.stdout.write(self.style.SUCCESS(f'Found user {username} with ID: {user.id}'))
            except User.DoesNotExist:
                # Create the user if not found
                user = User.objects.create_user(
                    username=username,
                    email=f'{username}@gmail.com',
                    password='password123',
                    first_name='Fakorede',
                    last_name='Abbas',
                    role='client'
                )
                self.stdout.write(self.style.SUCCESS(f'Created user {username} with ID: {user.id}'))
            
            # Get a list of potential reviewers (excluding the target user)
            reviewers = list(User.objects.exclude(username=username).values_list('id', flat=True))
            
            if not reviewers:
                # Create some reviewer users if none exist
                for i in range(5):
                    reviewer = User.objects.create_user(
                        username=f'reviewer{i}',
                        email=f'reviewer{i}@example.com',
                        password='password123',
                        first_name=f'Reviewer{i}',
                        last_name='User',
                        role='worker'
                    )
                    reviewers.append(reviewer.id)
                self.stdout.write(self.style.SUCCESS(f'Created {len(reviewers)} reviewer users'))
            
            # Sample feedback templates
            positive_feedback = [
                "Great work! Very professional and delivered on time.",
                "Excellent communication and quality of work. Would hire again!",
                "A pleasure to work with. Very responsive and professional.",
                "Exceeded expectations. Highly recommended!",
                "Outstanding service and attention to detail.",
                "Very reliable and efficient. Will definitely work with again.",
                "Top-notch professional. Delivered exactly what was promised.",
                "Fantastic experience working together. Very skilled and knowledgeable."
            ]
            
            neutral_feedback = [
                "Satisfactory work. Met the requirements.",
                "Decent job. Could improve on communication.",
                "Acceptable quality. Delivered on time.",
                "Average experience. Some aspects could be better.",
                "Okay service. Nothing exceptional but got the job done."
            ]
            
            negative_feedback = [
                "Disappointed with the quality of work.",
                "Poor communication and missed deadlines.",
                "Did not meet expectations. Would not recommend.",
                "Difficult to work with. Many revisions needed.",
                "Unsatisfactory experience overall."
            ]
            
            # Create reviews for the user
            for i in range(count):
                # Select a random reviewer
                reviewer_id = random.choice(reviewers)
                reviewer = User.objects.get(pk=reviewer_id)
                
                # Determine rating and feedback based on distribution
                # 60% positive (4-5), 30% neutral (3), 10% negative (1-2)
                rating_category = random.choices(
                    ["positive", "neutral", "negative"],
                    weights=[0.6, 0.3, 0.1]
                )[0]
                
                if rating_category == "positive":
                    rating = random.uniform(4.0, 5.0)
                    feedback = random.choice(positive_feedback)
                elif rating_category == "neutral":
                    rating = random.uniform(2.8, 3.9)
                    feedback = random.choice(neutral_feedback)
                else:
                    rating = random.uniform(1.0, 2.7)
                    feedback = random.choice(negative_feedback)
                
                # Round rating to 1 decimal place
                rating = round(rating, 1)
                
                # Create the review with a random date in the past (up to 60 days ago)
                days_ago = random.randint(0, 60)
                
                # Check if a review already exists
                existing_review = Review.objects.filter(reviewer=reviewer, reviewed=user).first()
                if existing_review:
                    # Update the existing review
                    existing_review.rating = rating
                    existing_review.feedback = feedback
                    existing_review.created_at = datetime.now() - timedelta(days=days_ago)
                    existing_review.save()
                    self.stdout.write(self.style.SUCCESS(f'Updated review: {reviewer.username} -> {user.username}, Rating: {rating}'))
                else:
                    # Create a new review
                    review = Review.objects.create(
                        reviewer=reviewer,
                        reviewed=user,
                        rating=rating,
                        feedback=feedback
                    )
                    
                    # Set created_at date
                    review.created_at = datetime.now() - timedelta(days=days_ago)
                    review.save(update_fields=['created_at'])
                    
                    self.stdout.write(self.style.SUCCESS(f'Created review: {reviewer.username} -> {user.username}, Rating: {rating}'))
            
            self.stdout.write(self.style.SUCCESS(f'Successfully created/updated reviews for user {user.username}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
