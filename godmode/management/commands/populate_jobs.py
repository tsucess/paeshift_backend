import random
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Profile
from jobs.models import Application, Job, JobIndustry, JobSubCategory

User = get_user_model()


class Command(BaseCommand):
    help = "Populates the database with sample jobs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=30, help="Number of jobs to create"
        )
        parser.add_argument(
            "--create-users", action="store_true", help="Create sample users"
        )
        parser.add_argument(
            "--create-applications",
            action="store_true",
            help="Create sample job applications",
        )

    def handle(self, *args, **options):
        count = options["count"]
        create_users = options["create_users"]
        create_applications = options["create_applications"]

        # Create sample users
        users = (
            self._create_sample_users()
            if create_users
            else [self._get_or_create_admin()]
        )

        # Get all industries and subcategories
        industries = list(JobIndustry.objects.all())
        if not industries:
            self.stdout.write(
                self.style.ERROR("No industries found. Please create industries first.")
            )
            return

        # Create industries and subcategories if none exist
        if len(industries) < 3:
            industries = self._create_sample_industries()

        # Sample job titles by industry with more variety
        job_titles = self._get_job_titles_by_industry()

        # Sample locations with more variety
        locations = self._get_sample_locations()

        # Job types and shift types
        job_types = [choice[0] for choice in Job.JobType.choices]
        shift_types = [choice[0] for choice in Job.ShiftType.choices]

        # Job statuses for more realistic data - use only valid statuses from the model
        job_statuses = [choice[0] for choice in Job.Status.choices]

        # Payment statuses - use only valid statuses from the model
        payment_statuses = [choice[0] for choice in Job.PaymentStatus.choices]

        # Create jobs with more diverse data
        jobs_created = 0
        created_jobs = []

        for i in range(count):
            try:
                # Select random industry and related subcategory
                industry = random.choice(industries)
                subcategories = list(JobSubCategory.objects.filter(industry=industry))

                if not subcategories:
                    self.stdout.write(
                        self.style.WARNING(
                            f"No subcategories found for industry: {industry.name}"
                        )
                    )
                    continue

                subcategory = random.choice(subcategories)

                # Select random client
                client = random.choice(users)

                # Generate random date (mix of past, present, and future)
                days_offset = random.randint(-60, 60)  # -60 to +60 days from today
                job_date = timezone.now().date() + timedelta(days=days_offset)

                # Generate random times
                start_hour = random.randint(6, 18)  # 6 AM to 6 PM
                start_minute = random.choice([0, 15, 30, 45])
                start_time = datetime.strptime(
                    f"{start_hour}:{start_minute}", "%H:%M"
                ).time()

                # End time 1-12 hours after start time
                duration_hours = random.randint(1, 12)
                end_hour = (start_hour + duration_hours) % 24
                end_time = datetime.strptime(
                    f"{end_hour}:{start_minute}", "%H:%M"
                ).time()

                # Determine status based on date
                if job_date < timezone.now().date():
                    # Past jobs are more likely to be completed
                    if "completed" in job_statuses:
                        status = "completed"
                    else:
                        status = random.choice(job_statuses)

                    # Past jobs are more likely to be paid
                    if "paid" in payment_statuses:
                        payment_status = "paid"
                    else:
                        payment_status = random.choice(payment_statuses)
                elif job_date == timezone.now().date():
                    # Today's jobs are more likely to be accepted
                    if "accepted" in job_statuses:
                        status = "accepted"
                    else:
                        status = random.choice(job_statuses)

                    # Today's jobs might be pending payment
                    payment_status = random.choice(payment_statuses)
                else:
                    # Future jobs are more likely to be pending
                    if "pending" in job_statuses:
                        status = "pending"
                    else:
                        status = random.choice(job_statuses)

                    # Future jobs are likely pending payment
                    if "pending" in payment_statuses:
                        payment_status = "pending"
                    else:
                        payment_status = random.choice(payment_statuses)

                # Generate a more detailed description
                description = self._generate_job_description(
                    industry.name, subcategory.name
                )

                # Create job with more detailed data - skip geocoding to avoid API rate limits
                job = Job(
                    client=client,
                    created_by=client,
                    title=random.choice(
                        job_titles.get(industry.name, ["Job Position"])
                    ),
                    description=description,
                    industry=industry,
                    subcategory=subcategory,
                    applicants_needed=random.randint(1, 10),
                    job_type=random.choice(job_types),
                    shift_type=random.choice(shift_types),
                    date=job_date,
                    start_time=start_time,
                    end_time=end_time,
                    rate=Decimal(
                        str(
                            random.randint(15, 75)
                            + random.choice([0, 0.25, 0.5, 0.75, 0.99])
                        )
                    ).quantize(Decimal("0.01")),
                    location=random.choice(locations),
                    payment_status=payment_status,
                    status=status,
                    # Set default coordinates to avoid validation errors
                    latitude=Decimal("0.000000"),
                    longitude=Decimal("0.000000"),
                )

                # Calculate service fee and total amount for all jobs
                # Use the model's method to ensure consistent calculation
                job.calculate_service_fee_and_total()

                # Save with geocoding skipped to avoid API rate limits
                job.save(skip_geocoding=True)

                created_jobs.append(job)
                jobs_created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created job {i+1}/{count}: {job.title} (ID: {job.id}, Status: {job.status})"
                    )
                )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error creating job {i+1}: {str(e)}")
                )

        # Create applications if requested
        if create_applications and created_jobs:
            self._create_sample_applications(created_jobs, users)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully created {jobs_created} jobs")
        )

    def _get_or_create_admin(self):
        """Get or create the admin user"""
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "first_name": "Admin",
                "last_name": "User",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Created admin user: {admin_user.username}")
            )
        return admin_user

    def _create_sample_users(self):
        """Create sample users with different roles"""
        admin = self._get_or_create_admin()
        users = [admin]

        # Sample user data
        sample_users = [
            {
                "username": "client1",
                "email": "client1@example.com",
                "first_name": "John",
                "last_name": "Smith",
                "password": "password123",
                "is_client": True,
            },
            {
                "username": "client2",
                "email": "client2@example.com",
                "first_name": "Sarah",
                "last_name": "Johnson",
                "password": "password123",
                "is_client": True,
            },
            {
                "username": "worker1",
                "email": "worker1@example.com",
                "first_name": "Michael",
                "last_name": "Brown",
                "password": "password123",
                "is_worker": True,
            },
            {
                "username": "worker2",
                "email": "worker2@example.com",
                "first_name": "Emily",
                "last_name": "Davis",
                "password": "password123",
                "is_worker": True,
            },
            {
                "username": "worker3",
                "email": "worker3@example.com",
                "first_name": "David",
                "last_name": "Wilson",
                "password": "password123",
                "is_worker": True,
            },
        ]

        for user_data in sample_users:
            try:
                is_client = user_data.pop("is_client", False)
                is_worker = user_data.pop("is_worker", False)

                user, created = User.objects.get_or_create(
                    username=user_data["username"], defaults=user_data
                )

                if created:
                    user.set_password(user_data["password"])
                    user.save()

                    # Create or update profile
                    profile, _ = Profile.objects.get_or_create(user=user)
                    profile.is_client = is_client
                    profile.is_worker = is_worker
                    profile.save()

                    self.stdout.write(
                        self.style.SUCCESS(f"Created user: {user.username}")
                    )

                users.append(user)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error creating user {user_data["username"]}: {str(e)}'
                    )
                )

        return users

    def _create_sample_industries(self):
        """Create sample industries and subcategories if none exist"""
        industries = []

        # Sample industry data
        industry_data = [
            {
                "name": "Electrical",
                "subcategories": [
                    "Residential Wiring",
                    "Commercial Electrical",
                    "Lighting Installation",
                    "Power Systems",
                    "Appliance Repair",
                ],
            },
            {
                "name": "Plumbing",
                "subcategories": [
                    "Residential Plumbing",
                    "Commercial Plumbing",
                    "Pipe Fitting",
                    "Drain Cleaning",
                    "Water Heater Installation",
                ],
            },
            {
                "name": "Construction",
                "subcategories": [
                    "Carpentry",
                    "Masonry",
                    "Drywall",
                    "Painting",
                    "Tiling",
                ],
            },
            {
                "name": "General",
                "subcategories": [
                    "Handyman Services",
                    "Cleaning",
                    "Moving",
                    "Landscaping",
                    "Maintenance",
                ],
            },
        ]

        for industry_info in industry_data:
            try:
                industry, created = JobIndustry.objects.get_or_create(
                    name=industry_info["name"]
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created industry: {industry.name}")
                    )

                industries.append(industry)

                # Create subcategories
                for subcategory_name in industry_info["subcategories"]:
                    subcategory, created = JobSubCategory.objects.get_or_create(
                        name=subcategory_name, industry=industry
                    )
                    if created:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Created subcategory: {subcategory.name} (Industry: {industry.name})"
                            )
                        )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error creating industry {industry_info["name"]}: {str(e)}'
                    )
                )

        return industries

    def _get_job_titles_by_industry(self):
        """Get sample job titles by industry with more variety"""
        return {
            "Electrical": [
                "Electrician Needed for Wiring Project",
                "Emergency Electrical Repair Technician",
                "Residential Electrician for Home Renovation",
                "Commercial Electrical Maintenance Specialist",
                "Solar Panel Installation Helper",
                "Lighting Fixture Installation Expert",
                "Electrical System Troubleshooter",
                "Smart Home Wiring Specialist",
                "Electrical Safety Inspector",
                "Generator Installation Technician",
            ],
            "Plumbing": [
                "Plumber Needed for Bathroom Renovation",
                "Emergency Pipe Repair Specialist",
                "Kitchen Sink Installation Expert",
                "Water Heater Replacement Technician",
                "Drainage System Maintenance Worker",
                "Toilet Repair and Installation Specialist",
                "Sewer Line Cleaning Professional",
                "Faucet and Fixture Installation Expert",
                "Pipe Insulation Specialist",
                "Plumbing System Inspector",
            ],
            "Construction": [
                "General Construction Worker Needed",
                "Drywall Installation Specialist",
                "Concrete Foundation Helper",
                "Roofing Assistant Required",
                "Framing Carpenter for Residential Project",
                "Tile Installation Expert",
                "Painting and Finishing Specialist",
                "Demolition Crew Member",
                "Insulation Installation Technician",
                "Window and Door Installation Helper",
            ],
            "General": [
                "Handyman for Various Home Repairs",
                "General Maintenance Worker",
                "Property Maintenance Assistant",
                "Home Improvement Helper",
                "Facility Maintenance Technician",
                "Moving Assistant Needed",
                "Furniture Assembly Specialist",
                "Lawn Care and Landscaping Helper",
                "Cleaning Service Professional",
                "Pressure Washing Expert",
            ],
        }

    def _get_sample_locations(self):
        """Get sample locations with more variety"""
        return [
            "123 Main St, New York, NY 10001",
            "456 Oak Avenue, Los Angeles, CA 90001",
            "789 Pine Road, Chicago, IL 60601",
            "101 Maple Drive, Houston, TX 77001",
            "202 Cedar Lane, Phoenix, AZ 85001",
            "303 Elm Street, Philadelphia, PA 19101",
            "404 Birch Boulevard, San Antonio, TX 78201",
            "505 Willow Way, San Diego, CA 92101",
            "606 Spruce Circle, Dallas, TX 75201",
            "707 Redwood Road, San Jose, CA 95101",
            "808 Aspen Avenue, Austin, TX 78701",
            "909 Cypress Street, Jacksonville, FL 32201",
            "1010 Magnolia Boulevard, San Francisco, CA 94101",
            "1111 Sycamore Lane, Columbus, OH 43201",
            "1212 Juniper Drive, Fort Worth, TX 76101",
            "1313 Hemlock Court, Charlotte, NC 28201",
            "1414 Poplar Path, Seattle, WA 98101",
            "1515 Walnut Way, Denver, CO 80201",
            "1616 Chestnut Road, Boston, MA 02101",
            "1717 Beech Street, Nashville, TN 37201",
        ]

    def _generate_job_description(self, industry, subcategory):
        """Generate a realistic job description based on industry and subcategory"""
        descriptions = {
            "Electrical": {
                "base": "Looking for a qualified electrician to help with {task}. Must have experience with {requirement} and bring own {tools}. {additional}",
                "tasks": [
                    "installing new lighting fixtures",
                    "rewiring a home",
                    "troubleshooting electrical issues",
                    "upgrading an electrical panel",
                    "installing ceiling fans",
                ],
                "requirements": [
                    "residential wiring",
                    "commercial electrical systems",
                    "low voltage systems",
                    "electrical code compliance",
                    "smart home technology",
                ],
                "tools": [
                    "basic hand tools",
                    "testing equipment",
                    "power tools",
                    "safety equipment",
                    "ladders",
                ],
                "additional": [
                    "Safety certification preferred.",
                    "Must be punctual and professional.",
                    "This is an urgent job that needs immediate attention.",
                    "Long-term opportunity for the right candidate.",
                    "Weekend availability required.",
                ],
            },
            "Plumbing": {
                "base": "Need a plumber to {task}. Experience with {requirement} is essential. Please bring {tools}. {additional}",
                "tasks": [
                    "fix a leaking pipe",
                    "install a new water heater",
                    "unclog drains",
                    "replace bathroom fixtures",
                    "repair a toilet",
                ],
                "requirements": [
                    "residential plumbing",
                    "commercial plumbing systems",
                    "pipe fitting",
                    "water heater installation",
                    "drain cleaning",
                ],
                "tools": [
                    "pipe wrenches",
                    "plungers and augers",
                    "pipe cutters",
                    "soldering equipment",
                    "leak detection tools",
                ],
                "additional": [
                    "Emergency response needed.",
                    "Clean work habits required.",
                    "Must be able to work in tight spaces.",
                    "Knowledge of local plumbing codes preferred.",
                    "This is a multi-day project.",
                ],
            },
            "Construction": {
                "base": "Construction worker needed to help {task}. Should have experience with {requirement}. {tools} will be provided. {additional}",
                "tasks": [
                    "frame a new addition",
                    "install drywall",
                    "pour concrete",
                    "build a deck",
                    "install flooring",
                ],
                "requirements": [
                    "carpentry",
                    "masonry",
                    "drywall installation",
                    "roofing",
                    "tile setting",
                ],
                "tools": [
                    "Power tools",
                    "Hand tools",
                    "Safety equipment",
                    "Measuring tools",
                    "Ladders and scaffolding",
                ],
                "additional": [
                    "Heavy lifting required.",
                    "Must follow safety protocols.",
                    "Experience with blueprint reading a plus.",
                    "Transportation to job site required.",
                    "Potential for ongoing work.",
                ],
            },
            "General": {
                "base": "Looking for help with {task}. Experience with {requirement} preferred. Please bring {tools} if possible. {additional}",
                "tasks": [
                    "general home repairs",
                    "moving furniture",
                    "yard maintenance",
                    "cleaning services",
                    "painting rooms",
                ],
                "requirements": [
                    "basic handyman skills",
                    "heavy lifting",
                    "cleaning techniques",
                    "painting and finishing",
                    "lawn care",
                ],
                "tools": [
                    "basic hand tools",
                    "cleaning supplies",
                    "gardening equipment",
                    "painting supplies",
                    "moving equipment",
                ],
                "additional": [
                    "Reliable transportation needed.",
                    "Must be detail-oriented.",
                    "Flexible hours available.",
                    "Great opportunity for someone looking for part-time work.",
                    "Multiple days of work available.",
                ],
            },
        }

        # Use the industry template or default to General
        template = descriptions.get(industry, descriptions["General"])

        # Fill in the template with random selections
        return template["base"].format(
            task=random.choice(template["tasks"]),
            requirement=random.choice(template["requirements"]),
            tools=random.choice(template["tools"]),
            additional=random.choice(template["additional"]),
        )

    def _create_sample_applications(self, jobs, users):
        """Create sample job applications"""
        # Filter for worker users
        workers = [
            user
            for user in users
            if hasattr(user, "profile") and getattr(user.profile, "is_worker", False)
        ]

        if not workers:
            self.stdout.write(
                self.style.WARNING(
                    "No worker users found. Skipping application creation."
                )
            )
            return

        applications_created = 0

        # Application statuses
        statuses = ["pending", "accepted", "rejected", "withdrawn"]

        for job in jobs:
            # Determine how many applications to create for this job
            num_applications = min(
                random.randint(0, 5),  # Random number of applications
                len(workers),  # Can't have more applications than workers
                job.applicants_needed * 2,  # Roughly twice the needed applicants
            )

            if num_applications == 0:
                continue

            # Select random workers for this job
            selected_workers = random.sample(workers, num_applications)

            for worker in selected_workers:
                try:
                    # Determine application status based on job status
                    if job.status == "completed":
                        # Completed jobs are more likely to have accepted applications
                        status = random.choices(statuses, weights=[0.1, 0.7, 0.1, 0.1])[
                            0
                        ]
                    elif job.status == "in_progress":
                        # In-progress jobs should have some accepted applications
                        status = random.choices(statuses, weights=[0.2, 0.6, 0.1, 0.1])[
                            0
                        ]
                    elif job.status == "cancelled":
                        # Cancelled jobs are more likely to have rejected/withdrawn applications
                        status = random.choices(statuses, weights=[0.2, 0.1, 0.4, 0.3])[
                            0
                        ]
                    else:
                        # Pending jobs are more likely to have pending applications
                        status = random.choices(statuses, weights=[0.7, 0.1, 0.1, 0.1])[
                            0
                        ]

                    # Check the Application model fields
                    application_fields = {
                        "job": job,
                        "applicant": worker,
                        "status": status,
                        "industry": job.industry,
                    }

                    # Add cover_letter only if the field exists in the model
                    from django.db import models

                    if any(
                        f.name == "cover_letter" for f in Application._meta.get_fields()
                    ):
                        application_fields[
                            "cover_letter"
                        ] = f"I am interested in this {job.industry.name} position and have relevant experience in {job.subcategory.name if job.subcategory else 'this field'}."

                    # Create the application
                    application = Application.objects.create(**application_fields)

                    applications_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created application for job {job.id} by {worker.username} (Status: {status})"
                        )
                    )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error creating application for job {job.id} by {worker.username}: {str(e)}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {applications_created} applications"
            )
        )
