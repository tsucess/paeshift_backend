# Standard Library Imports
import json
import random
from decimal import Decimal
from datetime import timedelta

# Django Imports
from django.conf import settings
from django.contrib.auth.models import (AbstractBaseUser, BaseUserManager,
                                        PermissionsMixin)
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _



class OTP(models.Model):
    """
    One-Time Password model for various authentication and verification purposes.

    This model stores OTP codes sent to users for:
    - Account registration verification
    - Two-factor authentication (2FA)
    - Login from new devices
    - Password reset verification
    - Sensitive operations verification
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.IntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    metadata = models.TextField(blank=True, null=True, help_text="JSON metadata for the OTP")

    # Constants for OTP settings
    MAX_ATTEMPTS = 5
    EXPIRY_MINUTES = 5
    LOCKOUT_MINUTES = 15

    def is_valid(self):
        """Check if OTP is still valid (not expired and not too many attempts)"""
        # Check if already verified
        if self.is_verified:
            return False

        # Check if too many attempts
        if self.attempts >= self.MAX_ATTEMPTS:
            return False

        # Check if expired
        return timezone.now() <= self.created_at + timedelta(minutes=self.EXPIRY_MINUTES)

    def increment_attempts(self):
        """Increment the number of failed attempts"""
        self.attempts += 1
        self.save()
        return self.attempts >= self.MAX_ATTEMPTS

    def mark_as_verified(self):
        """Mark this OTP as successfully verified"""
        self.is_verified = True
        self.save()

    def get_metadata(self):
        """Get the metadata as a dictionary"""
        if not self.metadata:
            return {}
        try:
            return json.loads(self.metadata)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_metadata(self, metadata_dict):
        """Set the metadata from a dictionary"""
        if not isinstance(metadata_dict, dict):
            raise ValueError("Metadata must be a dictionary")
        self.metadata = json.dumps(metadata_dict)
        self.save()

    def get_otp_type(self):
        """Get the OTP type from metadata"""
        metadata = self.get_metadata()
        return metadata.get('type', 'unknown')

    @classmethod
    def is_user_locked_out(cls, user):
        """Check if user is locked out due to too many failed attempts"""
        recent_failed_otps = cls.objects.filter(
            user=user,
            attempts__gte=cls.MAX_ATTEMPTS,
            is_verified=False,
            created_at__gte=timezone.now() - timedelta(minutes=cls.LOCKOUT_MINUTES)
        ).exists()
        return recent_failed_otps

    @classmethod
    def cleanup_expired_otps(cls):
        """Delete expired OTPs"""
        expiry_time = timezone.now() - timedelta(minutes=cls.EXPIRY_MINUTES)
        return cls.objects.filter(created_at__lt=expiry_time).delete()

    class Meta:
        verbose_name = "OTP"
        verbose_name_plural = "OTPs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user_id', 'is_verified']),
        ]


class TemporaryOTP(models.Model):
    """
    Temporary OTP model for registration and other flows that don't have a user yet.

    This model stores OTP codes indexed by email instead of user ID, allowing
    OTP verification before user account creation.
    """
    email = models.EmailField(max_length=255, db_index=True)
    code = models.CharField(max_length=6)
    otp_type = models.CharField(
        max_length=50,
        choices=[
            ('registration', 'Registration'),
            ('password_reset', 'Password Reset'),
            ('login', 'Login'),
        ],
        default='registration'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.IntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    metadata = models.TextField(blank=True, null=True, help_text="JSON metadata for the OTP")

    # Constants for OTP settings
    MAX_ATTEMPTS = 5
    EXPIRY_MINUTES = 5

    def is_valid(self):
        """Check if OTP is still valid (not expired and not too many attempts)"""
        # Check if already verified
        if self.is_verified:
            return False

        # Check if too many attempts
        if self.attempts >= self.MAX_ATTEMPTS:
            return False

        # Check if expired
        return timezone.now() <= self.created_at + timedelta(minutes=self.EXPIRY_MINUTES)

    def increment_attempts(self):
        """Increment the number of failed attempts"""
        self.attempts += 1
        self.save()
        return self.attempts >= self.MAX_ATTEMPTS

    def mark_as_verified(self):
        """Mark this OTP as successfully verified"""
        self.is_verified = True
        self.save()

    def get_metadata(self):
        """Get the metadata as a dictionary"""
        if not self.metadata:
            return {}
        try:
            return json.loads(self.metadata)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_metadata(self, metadata_dict):
        """Set the metadata from a dictionary"""
        if not isinstance(metadata_dict, dict):
            raise ValueError("Metadata must be a dictionary")
        self.metadata = json.dumps(metadata_dict)
        self.save()

    @classmethod
    def cleanup_expired_otps(cls):
        """Delete expired OTPs"""
        expiry_time = timezone.now() - timedelta(minutes=cls.EXPIRY_MINUTES)
        return cls.objects.filter(created_at__lt=expiry_time).delete()

    class Meta:
        verbose_name = "Temporary OTP"
        verbose_name_plural = "Temporary OTPs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['email', 'otp_type']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['created_at']),
        ]


class CustomUserManager(BaseUserManager):
    """Custom user manager using email as primary identifier"""

    def create_user(self, email, password=None, username=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(
            email=email, username=username or email.split("@")[0], **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, username=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("first_name", "Admin")
        extra_fields.setdefault("last_name", "User")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        # FIX: only use keyword arguments to avoid conflict
        return self.create_user(email=email, password=password, username=username, **extra_fields)





class Role(models.Model):
    """User roles in the system"""

    name = models.CharField(
        _("role name"),
        max_length=50,
        unique=True,
        help_text=_("Name of the role")
    )

    description = models.TextField(
        _("description"),
        blank=True,
        help_text=_("Description of the role and its permissions")
    )

    # Default role types
    APPLICANT = "applicant"
    CLIENT = "client"
    ADMIN = "admin"

    # Timestamps
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Custom user model with email-based authentication with Redis caching"""

    # Redis caching configuration
    cache_enabled = True
    cache_exclude = ["password"]

    # Define role choices as class constants
    ROLE_APPLICANT = "applicant"
    ROLE_CLIENT = "client"
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = [
        (ROLE_APPLICANT, _("Applicant")),
        (ROLE_CLIENT, _("Client")),
        (ROLE_ADMIN, _("Admin")),
    ]

    role = models.CharField(
        _("role"),
        max_length=50,
        choices=ROLE_CHOICES,
        default=ROLE_CLIENT,
        help_text=_("User's role in the system")
    )

    email = models.EmailField(
        _("email address"),
        unique=True,
        help_text=_("Required. Valid email address for account verification"),
    )
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        help_text=_("Required. 150 characters or fewer"),
    )
    first_name = models.CharField(
        _("first name"), max_length=30, help_text=_("Enter your legal first name")
    )
    last_name = models.CharField(
        _("last name"), max_length=30, help_text=_("Enter your legal last name")
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Designates whether this user should be treated as active"),
    )
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site"),
    )
    date_joined = models.DateTimeField(_("date joined"), auto_now_add=True)
    location = models.CharField(max_length=6, blank=True, null=True)
    
    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "username"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['is_active']),
            models.Index(fields=['role']),
        ]

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()



    def __str__(self):
        return self.email





class Profile(models.Model):
    """Extended user profile with professional information"""

    # Redis caching is disabled to avoid conflicts with chatapp.Profile
    # We'll handle caching manually if needed
    cache_enabled = False

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="profile",
        help_text=_("The user this profile belongs to"),
    )

    # Profile Information
    # Use a CharField for role instead of ForeignKey to simplify the model
    role = models.CharField(
        _("role"),
        max_length=50,
        help_text=_("User's role in the system"),
    )

    # Security Settings
    has_2fa_enabled = models.BooleanField(
        _("2FA enabled"),
        default=False,
        help_text=_("Whether two-factor authentication is enabled for this user")
    )

    def to_dict(self):
        """
        Convert Profile to dictionary for caching.
        This method is used by Redis caching to serialize the model.
        """
        # Get wallet balance if available
        try:
            from payment.models import Wallet
            wallet = Wallet.objects.get(user=self.user)
            wallet_balance = str(wallet.balance)
        except Exception:
            wallet_balance = "0.00"

        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "phone_number": self.phone_number,
            "bio": self.bio,
            "location": self.location,
            "experience": self.experience,
            "education": self.education,
            "skills": self.skills,
            "balance": wallet_balance,  # Use wallet balance instead of profile balance
            "manual_rating": str(self.manual_rating) if self.manual_rating else None,
            "badges": self.badges,
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    phone_number = models.CharField(
        _("phone number"),
        max_length=15,
        blank=True,
        null=True,
        help_text=_("Your primary phone number"),
    )
    # profile_pic = models.For(
    #     _("profile picture"),
    #     upload_to="profile_pics/",
    #     null=True,
    #     blank=True,
    #     help_text=_("Upload a clear profile photo"),
    # )
    
    bio = models.TextField(
        _("biography"), blank=True, null=True, help_text=_("Tell others about yourself")
    )
    location = models.CharField(
        _("location"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Your current city/country"),
    )

    # Professional Information
    experience = models.TextField(
        _("work experience"),
        blank=True,
        null=True,
        help_text=_("Describe your professional experience"),
    )
    education = models.TextField(
        _("education"),
        blank=True,
        null=True,
        help_text=_("List your educational background"),
    )
    skills = models.TextField(
        _("skills"),
        blank=True,
        null=True,
        help_text=_("List your key skills (comma separated)"),
    )

    # Financial Information
    balance = models.DecimalField(
        _("account balance"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text=_("Current available balance in account"),
    )

    # Rating Information
    manual_rating = models.DecimalField(
        _("manual rating"),
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)],
        help_text=_("Manually assigned rating (1.0-5.0)"),
    )
    badges = models.JSONField(
        _("badges"), default=list, blank=True, help_text=_("Earned achievement badges")
    )

    # Timestamps
    joined_at = models.DateTimeField(_("profile created"), auto_now_add=True)
    updated_at = models.DateTimeField(_("last updated"), auto_now=True)


    # Account Details
    # account_details = models.JSONField(
    #     default=dict, blank=True, null=True, help_text=_('Bank or account details')
    # )

    account_details = models.JSONField(
        _("account details"),
        default=dict,
        blank=True,
        null=True,
        help_text=_("Stores user's bank account info (bank name, account number, etc.)")
    )

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")
        ordering = ["-joined_at"]
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['role']),
            models.Index(fields=['joined_at']),
        ]

    def __str__(self):
        return _("%(username)s's profile") % {"username": self.user.username}

    @property
    def rating(self):
        """Calculate weighted average rating from reviews"""
        try:
            from rating.models import Review

            if (avg_rating := Review.get_average_rating(self.user)) and avg_rating > 0:
                return float(avg_rating)
        except (ImportError, Review.DoesNotExist):
            pass
        return float(self.manual_rating) if self.manual_rating else 0.0

    @rating.setter
    def rating(self, value):
        """Validate and set manual rating"""
        if value is not None:
            value = Decimal(str(value)).quantize(Decimal("0.1"))
            if not (1.0 <= float(value) <= 5.0):
                raise ValidationError(_("Rating must be between 1.0 and 5.0"))
            self.manual_rating = value

    def add_to_balance(self, amount):
        """Credit amount to user's wallet balance"""
        from payment.models import Wallet
        wallet, created = Wallet.objects.get_or_create(
            user=self.user,
            defaults={"balance": Decimal("0.00")}
        )
        wallet.add_funds(amount)
        return True

    def deduct_from_balance(self, amount):
        """Debit amount from wallet if sufficient funds exist"""
        from payment.models import Wallet
        try:
            wallet = Wallet.objects.get(user=self.user)
            return wallet.deduct_funds(amount)
        except Wallet.DoesNotExist:
            return False


class GoogleAuthSession(models.Model):
    """Stores Google authentication session data"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="google_auth_sessions",
    )

    # Google Auth Data
    access_token = models.TextField(
        _("access token"),
        help_text=_("Google OAuth access token")
    )
    refresh_token = models.TextField(
        _("refresh token"),
        blank=True,
        null=True,
        help_text=_("Google OAuth refresh token (if available)")
    )
    token_expiry = models.DateTimeField(
        _("token expiry"),
        blank=True,
        null=True,
        help_text=_("When the access token expires")
    )

    # Google User Info
    google_user_id = models.CharField(
        _("Google user ID"),
        max_length=255,
        help_text=_("Unique ID from Google")
    )
    google_email = models.EmailField(
        _("Google email"),
        help_text=_("Email address from Google account")
    )
    profile_data = models.JSONField(
        _("profile data"),
        default=dict,
        blank=True,
        help_text=_("Additional profile data from Google")
    )
    scopes = models.JSONField(
        _("OAuth scopes"),
        default=list,
        blank=True,
        help_text=_("OAuth scopes granted to this session")
    )

    # Session Info
    is_active = models.BooleanField(
        _("is active"),
        default=True,
        help_text=_("Whether this session is currently active")
    )
    last_used = models.DateTimeField(
        _("last used"),
        auto_now=True,
        help_text=_("When this session was last used")
    )
    created_at = models.DateTimeField(
        _("created at"),
        auto_now_add=True,
        help_text=_("When this session was created")
    )
    ip_address = models.GenericIPAddressField(
        _("IP address"),
        blank=True,
        null=True,
        help_text=_("IP address used for this session")
    )
    user_agent = models.TextField(
        _("user agent"),
        blank=True,
        null=True,
        help_text=_("Browser/device information")
    )

    class Meta:
        verbose_name = _("Google auth session")
        verbose_name_plural = _("Google auth sessions")
        ordering = ["-last_used"]

    def __str__(self):
        return f"{self.user.email}'s Google session ({self.created_at.strftime('%Y-%m-%d')})"

    def to_dict(self):
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "access_token": self.access_token,
            "google_user_id": self.google_user_id,
            "google_email": self.google_email,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }

    @classmethod
    def create_session(cls, user, access_token, google_user_id, google_email,
                      profile_data=None, refresh_token=None, token_expiry=None,
                      ip_address=None, user_agent=None, scopes=None):
        """Create a new Google auth session"""
        return cls.objects.create(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            google_user_id=google_user_id,
            google_email=google_email,
            profile_data=profile_data or {},
            ip_address=ip_address,
            user_agent=user_agent,
            scopes=scopes or []
        )

    @classmethod
    def get_active_session(cls, user):
        """Get the most recently used active session for a user"""
        return cls.objects.filter(user=user, is_active=True).order_by('-last_used').first()


class TrustedDevice(models.Model):
    """
    Stores information about trusted devices for users.

    A trusted device is one that has been verified with OTP and
    doesn't require re-verification for a certain period.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="trusted_devices",
    )
    device_id = models.CharField(
        _("device ID"),
        max_length=255,
        help_text=_("Unique identifier for the device")
    )
    device_name = models.CharField(
        _("device name"),
        max_length=255,
        help_text=_("User-friendly name of the device")
    )
    device_type = models.CharField(
        _("device type"),
        max_length=50,
        default="unknown",
        help_text=_("Type of device (e.g., mobile, desktop)")
    )
    ip_address = models.GenericIPAddressField(
        _("IP address"),
        blank=True,
        null=True,
        help_text=_("IP address used during verification")
    )
    user_agent = models.TextField(
        _("user agent"),
        blank=True,
        null=True,
        help_text=_("User agent string from the device")
    )
    last_used_at = models.DateTimeField(
        _("last used at"),
        auto_now=True,
        help_text=_("When this device was last used")
    )
    verified_at = models.DateTimeField(
        _("verified at"),
        auto_now_add=True,
        help_text=_("When this device was verified")
    )
    expires_at = models.DateTimeField(
        _("expires at"),
        help_text=_("When the trust for this device expires")
    )
    is_active = models.BooleanField(
        _("is active"),
        default=True,
        help_text=_("Whether this device is currently trusted")
    )

    class Meta:
        verbose_name = _("trusted device")
        verbose_name_plural = _("trusted devices")
        ordering = ["-last_used_at"]
        unique_together = ["user", "device_id"]

    def __str__(self):
        return f"{self.user.username}'s {self.device_name}"

    def is_expired(self):
        """Check if the trust for this device has expired"""
        return timezone.now() > self.expires_at

    @classmethod
    def create_trusted_device(cls, user, device_info, days_valid=30):
        """Create a new trusted device"""
        expires_at = timezone.now() + timedelta(days=days_valid)

        device, created = cls.objects.update_or_create(
            user=user,
            device_id=device_info.get('device_id'),
            defaults={
                'device_name': device_info.get('device_name', 'Unknown Device'),
                'device_type': device_info.get('device_type', 'unknown'),
                'ip_address': device_info.get('ip_address'),
                'user_agent': device_info.get('user_agent'),
                'expires_at': expires_at,
                'is_active': True,
            }
        )

        return device

    @classmethod
    def is_device_trusted(cls, user, device_id):
        """Check if a device is trusted for a user"""
        try:
            device = cls.objects.get(
                user=user,
                device_id=device_id,
                is_active=True
            )

            # Check if expired
            if device.is_expired():
                device.is_active = False
                device.save()
                return False

            # Update last used timestamp
            device.save()  # This triggers auto_now on last_used_at
            return True

        except cls.DoesNotExist:
            return False

class UserActivityLog(models.Model):
    """Tracks user activities and sessions with Redis caching"""

    # Redis caching configuration
    cache_enabled = True
    cache_related = ["user"]
    cache_exclude = []

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    activity_type = models.CharField(
        _("activity type"), max_length=50, help_text=_("Type of activity performed")
    )
    ip_address = models.GenericIPAddressField(_("IP address"), blank=True, null=True)
    created_at = models.DateTimeField(_("occurred at"), auto_now_add=True)

    class Meta:
        verbose_name = _("activity log")
        verbose_name_plural = _("activity logs")
        ordering = ["-created_at"]

    def __str__(self):
        return _("%(user)s's %(activity)s at %(time)s") % {
            "user": self.user.username,
            "activity": self.activity_type,
            "time": self.created_at.strftime("%Y-%m-%d %H:%M"),
        }

    def to_dict(self):
        """
        Convert UserActivityLog to dictionary for caching.

        This method is used by RedisCachedModelMixin to serialize the model
        for Redis caching.
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_username": self.user.username if self.user else None,
            "activity_type": self.activity_type,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProfilePicture(models.Model):
    """
    Model to store profile pictures uploaded by users.
    Each picture is linked to a Profile and stores upload metadata.
    """
    profile = models.ForeignKey(
        'Profile',
        on_delete=models.CASCADE,
        related_name='pictures',
        help_text=_('Profile this picture belongs to'),
    )
    image = models.ImageField(
        _('profile picture'),
        upload_to='profile_pics/',
        help_text=_('Uploaded profile picture'),
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, help_text=_('Is this the current profile picture?'))
    # Optionally, you can add a field to mark the type or purpose of the picture
    # type = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = _('profile picture')
        verbose_name_plural = _('profile pictures')
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.profile.user.username}'s picture ({self.uploaded_at})"

    @property
    def url(self):
        return self.image.url if self.image else None
