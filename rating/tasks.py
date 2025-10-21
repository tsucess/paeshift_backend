"""
Celery tasks for the rating application.

This module contains asynchronous tasks related to ratings and reviews,
including sentiment analysis of review text.
"""

import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Review
from .sentiment import classify_sentiment

logger = logging.getLogger(__name__)

@shared_task(
    name="rating.tasks.analyze_review_sentiment",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def analyze_review_sentiment(review_id):
    """
    Analyze the sentiment of a review's feedback text.

    This task:
    1. Retrieves the review by ID
    2. Uses the RoBERTa model to classify the sentiment
    3. Updates the review with the sentiment classification
    4. Handles errors and retries gracefully

    Args:
        review_id (int): The ID of the review to analyze

    Returns:
        dict: Result information including review ID and sentiment
    """
    logger.info(f"Analyzing sentiment for review {review_id}")

    try:
        with transaction.atomic():
            # Get the review with a select_for_update to prevent race conditions
            review = Review.objects.select_for_update().get(id=review_id)

            # Skip if no feedback text
            if not review.feedback:
                logger.debug(f"Review {review_id} has no feedback text, setting neutral sentiment")
                review.sentiment = "neutral"
                review.save(update_fields=["sentiment"])
                return {"status": "success", "review_id": review_id, "sentiment": "neutral", "reason": "no_feedback"}

            # Analyze sentiment using our ML model
            sentiment = classify_sentiment(review.feedback)

            # Update the review
            review.sentiment = sentiment
            review.save(update_fields=["sentiment"])

            logger.info(f"Set sentiment for review {review_id} to {sentiment}")

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

            review.save(update_fields=["review"])

            return {
                "status": "success",
                "review_id": review_id,
                "sentiment": sentiment,
                "review_type": review.review
            }

    except Review.DoesNotExist:
        logger.warning(f"Review with ID {review_id} does not exist")
        return {"status": "error", "review_id": review_id, "error": "review_not_found"}
    except Exception as e:
        logger.error(f"Error analyzing sentiment for review {review_id}: {str(e)}")
        # This will trigger a retry based on the task configuration
        raise
