"""
Management command to analyze sentiment for existing reviews.

This command processes all reviews that don't have sentiment analysis yet,
or can reprocess all reviews if requested.
"""

import logging
from django.core.management.base import BaseCommand
from django.db.models import Q
from tqdm import tqdm

from rating.models import Review
from rating.tasks import analyze_review_sentiment

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Analyze sentiment for existing reviews"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Process all reviews, even those that already have sentiment",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of reviews to process in each batch",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Process synchronously instead of using Celery",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            help="Process only reviews for a specific user (as reviewer or reviewed)",
        )

    def handle(self, *args, **options):
        process_all = options["all"]
        batch_size = options["batch_size"]
        sync = options["sync"]
        user_id = options.get("user_id")

        # Build the query
        if process_all:
            query = Q()
            self.stdout.write("Processing all reviews")
        else:
            query = Q(sentiment__isnull=True) | Q(sentiment="")
            self.stdout.write("Processing only reviews without sentiment")

        # Add user filter if specified
        if user_id:
            query &= Q(reviewer_id=user_id) | Q(reviewed_id=user_id)
            self.stdout.write(f"Filtering for user ID: {user_id}")

        # Get the reviews
        reviews = Review.objects.filter(query)
        total = reviews.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No reviews to process"))
            return

        self.stdout.write(f"Found {total} reviews to process")

        # Process in batches
        processed = 0
        with tqdm(total=total, desc="Processing reviews") as progress_bar:
            for i in range(0, total, batch_size):
                batch = reviews[i : i + batch_size]
                for review in batch:
                    if sync:
                        # Process synchronously
                        try:
                            from rating.sentiment import classify_sentiment

                            if review.feedback:
                                sentiment = classify_sentiment(review.feedback)
                                review.sentiment = sentiment
                                
                                # Set review type based on sentiment and rating
                                if sentiment == "positive" and float(review.rating) >= 4.0:
                                    review.review = "excellent"
                                elif sentiment == "positive" and float(review.rating) >= 3.0:
                                    review.review = "good"
                                elif sentiment == "neutral":
                                    review.review = "average"
                                elif sentiment == "negative" and float(review.rating) >= 2.0:
                                    review.review = "poor"
                                else:
                                    review.review = "bad"
                                    
                                review.save(update_fields=["sentiment", "review"])
                                self.stdout.write(
                                    f"Review {review.id}: {sentiment} ({review.review})"
                                )
                            else:
                                review.sentiment = "neutral"
                                review.review = "average"
                                review.save(update_fields=["sentiment", "review"])
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Error processing review {review.id}: {str(e)}"
                                )
                            )
                    else:
                        # Process asynchronously with Celery
                        analyze_review_sentiment.delay(review.id)

                    processed += 1
                    progress_bar.update(1)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed {processed} reviews"
                + (" synchronously" if sync else " asynchronously")
            )
        )
