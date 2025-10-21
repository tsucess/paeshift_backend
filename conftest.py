"""
Global pytest configuration and fixtures for Paeshift project.
"""
import os
import django
from decimal import Decimal
from datetime import datetime, timedelta

import pytest
import factory
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from faker import Faker

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payshift.settings')
django.setup()

from accounts.models import Profile
from jobs.models import Job, JobIndustry, JobSubCategory, Application, SavedJob
from payment.models import Payment, Wallet, Transaction
from rating.models import Review

User = get_user_model()
fake = Faker()


# ============================================================================
# FACTORIES
# ============================================================================

class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating test users."""
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.Sequence(lambda n: f'user{n}@example.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            obj.set_password(extracted)
        else:
            obj.set_password('testpass123')
        obj.save()


class ProfileFactory(factory.django.DjangoModelFactory):
    """Factory for creating user profiles."""
    class Meta:
        model = Profile

    user = factory.SubFactory(UserFactory)
    role = factory.Faker('random_element', elements=['client', 'applicant'])
    bio = factory.Faker('text', max_nb_chars=200)
    location = factory.Faker('city')
    phone_number = factory.Faker('phone_number')
    experience = factory.Faker('text', max_nb_chars=200)
    education = factory.Faker('text', max_nb_chars=200)
    skills = 'Python, Django, React'
    balance = Decimal('1000.00')
    badges = []


class JobIndustryFactory(factory.django.DjangoModelFactory):
    """Factory for creating job industries."""
    class Meta:
        model = JobIndustry

    name = factory.Sequence(lambda n: f'Industry {n}')


class JobSubCategoryFactory(factory.django.DjangoModelFactory):
    """Factory for creating job subcategories."""
    class Meta:
        model = JobSubCategory

    name = factory.Sequence(lambda n: f'Subcategory {n}')
    industry = factory.SubFactory(JobIndustryFactory)


class JobFactory(factory.django.DjangoModelFactory):
    """Factory for creating jobs."""
    class Meta:
        model = Job

    client = factory.SubFactory(UserFactory)
    created_by = factory.SelfAttribute('client')  # Same as client
    title = factory.Faker('job')
    industry = factory.SubFactory(JobIndustryFactory)
    subcategory = factory.SubFactory(JobSubCategoryFactory)
    applicants_needed = 2
    job_type = 'full_time'
    shift_type = 'day'
    date = factory.LazyFunction(lambda: (timezone.now() + timedelta(days=7)).date())
    start_time = datetime.strptime('09:00', '%H:%M').time()
    end_time = datetime.strptime('17:00', '%H:%M').time()
    rate = Decimal('25.00')
    location = factory.Faker('address')
    latitude = Decimal('40.7128')
    longitude = Decimal('-74.0060')
    is_active = True
    status = 'pending'


class ApplicationFactory(factory.django.DjangoModelFactory):
    """Factory for creating job applications."""
    class Meta:
        model = Application

    job = factory.SubFactory(JobFactory)
    applicant = factory.SubFactory(UserFactory)
    status = 'Applied'


class PaymentFactory(factory.django.DjangoModelFactory):
    """Factory for creating payments."""
    class Meta:
        model = Payment

    payer = factory.SubFactory(UserFactory)
    recipient = factory.SubFactory(UserFactory)
    job = factory.SubFactory(JobFactory)
    original_amount = Decimal('100.00')
    service_fee = Decimal('10.00')
    final_amount = Decimal('110.00')
    status = 'pending'
    payment_method = 'paystack'


class ReviewFactory(factory.django.DjangoModelFactory):
    """Factory for creating reviews."""
    class Meta:
        model = Review

    reviewer = factory.SubFactory(UserFactory)
    reviewed = factory.SubFactory(UserFactory)
    job = factory.SubFactory(JobFactory)
    rating = Decimal('4.5')
    feedback = factory.Faker('text', max_nb_chars=200)
    is_verified = True


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def client():
    """Django test client."""
    return Client()


@pytest.fixture
def user():
    """Create a test user."""
    return UserFactory(password='testpass123')


@pytest.fixture
def client_user():
    """Create a test client user."""
    user = UserFactory(password='testpass123')
    # Profile is created automatically by signal, just update the role
    profile = Profile.objects.get(user=user)
    profile.role = 'client'
    profile.save()
    return user


@pytest.fixture
def applicant_user():
    """Create a test applicant user."""
    user = UserFactory(password='testpass123')
    # Profile is created automatically by signal, just update the role
    profile = Profile.objects.get(user=user)
    profile.role = 'applicant'
    profile.save()
    return user


@pytest.fixture
def job_industry():
    """Create a test job industry."""
    return JobIndustryFactory()


@pytest.fixture
def job_subcategory(job_industry):
    """Create a test job subcategory."""
    return JobSubCategoryFactory(industry=job_industry)


@pytest.fixture
def job(client_user, job_industry, job_subcategory):
    """Create a test job."""
    return JobFactory(
        client=client_user,
        industry=job_industry,
        subcategory=job_subcategory
    )


@pytest.fixture
def application(job, applicant_user):
    """Create a test application."""
    return ApplicationFactory(
        job=job,
        applicant=applicant_user,
        employer=job.client
    )


@pytest.fixture
def payment(client_user, applicant_user, job):
    """Create a test payment."""
    return PaymentFactory(
        payer=client_user,
        recipient=applicant_user,
        job=job
    )


@pytest.fixture
def review(client_user, applicant_user, job):
    """Create a test review."""
    return ReviewFactory(
        reviewer=client_user,
        reviewed=applicant_user,
        job=job
    )


@pytest.fixture
def authenticated_client(client, user):
    """Create an authenticated test client."""
    client.force_login(user)
    return client

