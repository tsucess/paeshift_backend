from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from jobs.models import Job, JobIndustry, JobSubCategory


class PayshiftTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create base users
        cls.applicant = User.objects.create_user(
            username="applicant@example.com",
            email="applicant@example.com",
            password="testpass123",
        )
        cls.employer = User.objects.create_user(
            username="employer@example.com",
            email="employer@example.com",
            password="testpass123",
        )

        # Create industry and subcategory
        cls.tech_industry = JobIndustry.objects.create(name="Technology")
        cls.webdev_subcategory = JobSubCategory.objects.create(
            name="Web Development", industry=cls.tech_industry
        )

    def setUp(self):
        self.active_job = Job.objects.create(
            client=self.employer,
            title="Active Job",
            start_time=datetime.time(9, 0),
            end_time=datetime.time(17, 0),
            rate=Decimal("50.00"),
            location="Remote",
            is_active=True,
        )


from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from jobs.models import Job, JobIndustry, JobSubCategory


class PayshiftTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create base users
        cls.applicant = User.objects.create_user(
            username="applicant@example.com",
            email="applicant@example.com",
            password="testpass123",
        )
        cls.employer = User.objects.create_user(
            username="employer@example.com",
            email="employer@example.com",
            password="testpass123",
        )

        # Create industry and subcategory
        cls.tech_industry = JobIndustry.objects.create(name="Technology")
        cls.webdev_subcategory = JobSubCategory.objects.create(
            name="Web Development", industry=cls.tech_industry
        )

    def setUp(self):
        self.active_job = Job.objects.create(
            client=self.employer,
            title="Active Job",
            start_time=datetime.time(9, 0),
            end_time=datetime.time(17, 0),
            rate=Decimal("50.00"),
            location="Remote",
            is_active=True,
        )
