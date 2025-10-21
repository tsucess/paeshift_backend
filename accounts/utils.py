import logging
import random
import functools
from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Avg, Count
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import CustomUser as User, Profile
# TEMPORARILY COMMENTED OUT FOR SYSTEMATIC TESTING - apps not yet added
# from jobs.models import Application, Job
# from rating.models import Review
# from payment.models import Wallet  # COMMENTED OUT - payment app causes issues

logger = logging.getLogger(__name__)

def get_wallet_balance(user):
    """Get user's wallet balance - SIMPLIFIED for systematic testing"""
    # TEMPORARILY RETURN 0 - payment app causes issues
    # try:
    #     wallet = Wallet.objects.get(user=user)
    #     return wallet.balance
    # except Wallet.DoesNotExist:
    return Decimal("0.00")


def generate_otp():
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))


def send_otp_email(user, otp_code):
    """Send OTP via email with beautiful HTML template"""
    try:
        logger.info(f"📧 Starting email send process for {user.email} with OTP: {otp_code}")
        subject = "Verify Your Email - Payshift"

        # HTML email template
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verify Your Email - Payshift</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f4f4f4; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; padding: 20px 0; border-bottom: 2px solid #007bff; }}
                .logo {{ font-size: 28px; font-weight: bold; color: #007bff; }}
                .content {{ padding: 30px 0; text-align: center; }}
                .otp-code {{ font-size: 36px; font-weight: bold; color: #007bff; background-color: #f8f9fa; padding: 20px; border-radius: 8px; letter-spacing: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px 0; border-top: 1px solid #eee; color: #666; font-size: 14px; }}
                .warning {{ background-color: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">Payshift</div>
                    <p>Verify Your Email Address</p>
                </div>

                <div class="content">
                    <h2>Hello {user.first_name or user.username}!</h2>
                    <p>Welcome to Payshift! To complete your registration, please verify your email address using the code below:</p>

                    <div class="otp-code">{otp_code}</div>

                    <p>Enter this code on the verification page to activate your account.</p>

                    <div class="warning">
                        <strong>⏰ This code will expire in 10 minutes</strong><br>
                        If you didn't create an account with Payshift, please ignore this email.
                    </div>
                </div>

                <div class="footer">
                    <p>Best regards,<br>The Payshift Team</p>
                    <p><small>This is an automated message, please do not reply to this email.</small></p>
                </div>
            </div>
        </body>
        </html>
        """

        # Plain text fallback
        plain_message = f"""
        Hello {user.first_name or user.username},

        Welcome to Payshift! To complete your registration, please verify your email address.

        Your verification code is: {otp_code}

        Enter this code on the verification page to activate your account.

        This code will expire in 10 minutes.

        If you didn't create an account with Payshift, please ignore this email.

        Best regards,
        The Payshift Team
        """

        from django.core.mail import EmailMultiAlternatives
        from django.conf import settings

        logger.info(f"📬 Email backend: {settings.EMAIL_BACKEND}")
        logger.info(f"📬 From email: {settings.DEFAULT_FROM_EMAIL}")
        logger.info(f"📬 To email: {user.email}")
        logger.info(f"📬 SMTP Host: {settings.EMAIL_HOST}")
        logger.info(f"📬 SMTP Port: {settings.EMAIL_PORT}")
        logger.info(f"📬 SMTP User: {settings.EMAIL_HOST_USER}")
        logger.info(f"📬 SMTP Password: {'*' * len(settings.EMAIL_HOST_PASSWORD)} (length: {len(settings.EMAIL_HOST_PASSWORD)})")
        logger.info(f"📬 SMTP TLS: {settings.EMAIL_USE_TLS}")

        msg = EmailMultiAlternatives(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )
        msg.attach_alternative(html_message, "text/html")

        logger.info(f"📤 Sending email message...")
        msg.send()
        logger.info(f"✅ Email sent successfully!")

        logger.info(f"📧 OTP email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send OTP email to {user.email}: {str(e)}")
        import traceback
        logger.error(f"📋 Email error traceback: {traceback.format_exc()}")
        return False


def send_otp_sms(user, otp_code):
    """Send OTP via SMS - placeholder implementation"""
    # TODO: Implement SMS sending using Twilio or similar service
    logger.info(f"SMS OTP would be sent to {getattr(user, 'phone_number', 'N/A')}: {otp_code}")
    return True


def rate_limit_otp_requests(func):
    """Decorator to rate limit OTP requests"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        # Get user identifier (IP or user ID)
        if request.user.is_authenticated:
            identifier = f"otp_rate_limit_user_{request.user.id}"
        else:
            identifier = f"otp_rate_limit_ip_{request.META.get('REMOTE_ADDR', 'unknown')}"
        
        # Check rate limit
        current_requests = cache.get(identifier, 0)
        max_requests = getattr(settings, 'OTP_RATE_LIMIT', 5)
        window_seconds = getattr(settings, 'OTP_RATE_WINDOW', 3600)  # 1 hour
        
        if current_requests >= max_requests:
            return JsonResponse({
                'error': f'Too many OTP requests. Please try again later.'
            }, status=429)
        
        # Increment counter
        cache.set(identifier, current_requests + 1, window_seconds)
        
        return func(request, *args, **kwargs)
    return wrapper


def require_role(allowed_roles):
    """Decorator to require specific user roles"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({'error': 'Authentication required'}, status=401)
            
            user_role = getattr(request.user, 'role', None)
            if user_role not in allowed_roles:
                return JsonResponse({
                    'error': f'Access denied. Required roles: {", ".join(allowed_roles)}'
                }, status=403)
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_user_response(user) -> dict:
    """
    Simplified helper function for user response during systematic testing
    """
    profile, _ = Profile.objects.get_or_create(user=user)

    # Safely get profile pic URL from ProfilePicture model
    from accounts.models import ProfilePicture
    active_pic = ProfilePicture.objects.filter(profile=profile, is_active=True).first()
    pic_url = active_pic.image.url if active_pic and active_pic.image else ""

    # Explicitly convert all values to primitive types to avoid Django lazy objects
    response = {
        "user_id": int(user.id),
        "username": str(user.username),
        "email": str(user.email),
        "first_name": str(user.first_name),
        "last_name": str(user.last_name),
        "location": str(getattr(profile, 'location', None) or getattr(user, 'location', None) or ""),
        "bio": str(getattr(profile, 'bio', None) or ""),
        "phone_number": str(getattr(profile, 'phone_number', None) or ""),
        "role": str(getattr(profile, 'role', 'client')),
        "wallet_balance": str(get_wallet_balance(user)),
        "badges": list(getattr(profile, 'badges', []) or []),
        "profile_pic_url": str(pic_url),
        # Simplified stats for systematic testing
        "rating": float(5.0),
        "review_count": int(0),
        "user_reviews": [],
        "job_stats": {
            "total_jobs_posted": int(0),
            "total_workers_engaged": int(0),
            "total_completed_jobs": int(0),
            "total_cancelled_jobs": int(0),
        },
        "activity_stats": {
            "total_applied_jobs": int(0),
            "total_employers_worked_with": int(0),
        }
    }

    # Handle None values for optional fields
    if response["location"] == "None":
        response["location"] = None
    if response["bio"] == "None":
        response["bio"] = None
    if response["phone_number"] == "None":
        response["phone_number"] = None

    return response
