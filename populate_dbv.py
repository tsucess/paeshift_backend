#!/usr/bin/env python
"""
Enhanced database population script for Payshift.

This script populates the database with sample data for testing and development.
It provides command-line arguments for flexibility and better error handling.

Usage:
    python populate_dbv2.py [options]

Options:
    --users N         Number of users to create (default: 10)
    --jobs N          Number of jobs to create (default: 20)
    --applications N  Number of applications to create per job (default: 3)
    --only-users      Create only users and profiles
    --only-jobs       Create only jobs (requires existing users)
    --only-apps       Create only applications (requires existing jobs and users)
    --reset           Reset existing data before creating new data
    --verbose         Show detailed output
"""

import os
import sys
import random
import argparse
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payshift.settings')
django.setup()

# Import models
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import Profile, Role
from jobs.models import Job, JobIndustry, JobSubCategory, Application

User = get_user_model()

class DatabasePopulator:
    """Class to handle database population with enhanced features"""

    def __init__(self, args):
        self.args = args
        self.users_count = args.users
        self.jobs_count = args.jobs
        self.applications_per_job = args.applications
        self.verbose = args.verbose
        self.reset = args.reset

        # Track created objects
        self.roles = {}
        self.users = []
        self.industries = []
        self.jobs = []
        self.applications = []

    def log(self, message, level="INFO"):
        """Log messages based on verbosity level"""
        if self.verbose or level != "INFO":
            prefix = f"[{level}]" if level != "INFO" else ""
            print(f"{prefix} {message}")

    def create_default_roles(self):
        """Create default roles if they don't exist"""
        self.log("Creating default roles...")

        default_roles = {
            "client": "Client role for posting jobs",
            "applicant": "Applicant role for applying to jobs",
            "admin": "Administrator role with full access"
        }

        for role_name, description in default_roles.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={"description": description}
            )
            if created:
                self.log(f"Created role: {role.name}")
            else:
                self.log(f"Role already exists: {role.name}")
            self.roles[role_name] = role

        return self.roles

    def create_users(self):
        """Create sample users with different roles"""
        self.log(f"Creating {self.users_count} users...")

        # Create default roles first
        self.create_default_roles()

        # Disable signals temporarily to avoid cascading issues
        original_receivers = post_save.receivers
        post_save.receivers = []

        try:
            # Create admin user
            admin, created = User.objects.get_or_create(
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
                admin.set_password("admin123")
                admin.save()
                self.log(f"Created admin user: {admin.username}")
            else:
                self.log(f"Admin user already exists")

            # Create admin profile separately
            try:
                admin_profile, created = Profile.objects.get_or_create(
                    user=admin,
                    defaults={
                        "role": "admin",
                        "badges": []  # Initialize badges as empty list
                    }
                )
                if created:
                    self.log(f"Created admin profile for user: {admin.username}")
                else:
                    self.log(f"Admin profile already exists")
            except Exception as e:
                self.log(f"Error creating admin profile: {str(e)}", "ERROR")

            self.users.append(admin)

            # Generate random users
            first_names = ["John", "Sarah", "Michael", "Emily", "David", "Jessica", "James", "Jennifer", "Robert", "Lisa"]
            last_names = ["Smith", "Johnson", "Brown", "Davis", "Wilson", "Miller", "Moore", "Taylor", "Anderson", "Thomas"]
            roles = ["client", "applicant"]

            for i in range(self.users_count):
                role_name = random.choice(roles)
                first_name = random.choice(first_names)
                last_name = random.choice(last_names)
                username = f"{role_name.lower()}{i+1}"
                email = f"{username}@example.com"

                try:
                    # Check if user exists first
                    if User.objects.filter(username=username).exists():
                        user = User.objects.get(username=username)
                        self.log(f"User already exists: {username}")
                    else:
                        # Create user with explicit save to avoid signal issues
                        user = User(
                            username=username,
                            email=email,
                            first_name=first_name,
                            last_name=last_name,
                        )
                        user.set_password("password123")
                        user.save()
                        self.log(f"Created user: {username}")

                    # Create profile separately
                    try:
                        if Profile.objects.filter(user=user).exists():
                            self.log(f"Profile already exists for user: {username}")
                        else:
                            profile = Profile(
                                user=user,
                                role=role_name,
                                badges=[]  # Initialize badges as empty list
                            )
                            profile.save()
                            self.log(f"Created profile for user: {username}")
                    except Exception as profile_error:
                        self.log(f"Error creating profile for {username}: {str(profile_error)}", "ERROR")

                    self.users.append(user)
                except Exception as e:
                    self.log(f"Error creating user {username}: {str(e)}", "ERROR")
        finally:
            # Restore signals
            post_save.receivers = original_receivers

        return self.users

    def create_industries(self):
        """Create sample industries and subcategories"""
        self.log("Creating industries and subcategories...")

        industries_data = [
            {
                "name": "Electrical",
                "subcategories": ["Wiring", "Lighting", "Repairs", "Installation"]
            },
            {
                "name": "Plumbing",
                "subcategories": ["Pipes", "Fixtures", "Drainage", "Water Heaters"]
            },
            {
                "name": "Construction",
                "subcategories": ["Carpentry", "Masonry", "Drywall", "Painting"]
            },
            {
                "name": "Moving",
                "subcategories": ["Residential", "Commercial", "Packing", "Loading"]
            },
            {
                "name": "Cleaning",
                "subcategories": ["Residential", "Commercial", "Deep Cleaning", "Windows"]
            }
        ]

        for industry_data in industries_data:
            try:
                industry, created = JobIndustry.objects.get_or_create(
                    name=industry_data["name"]
                )

                if created:
                    self.log(f"Created industry: {industry.name}")
                else:
                    self.log(f"Industry already exists: {industry.name}")

                # Create subcategories
                for subcategory_name in industry_data["subcategories"]:
                    subcategory, subcategory_created = JobSubCategory.objects.get_or_create(
                        industry=industry,
                        name=subcategory_name
                    )

                    if subcategory_created:
                        self.log(f"Created subcategory: {subcategory.name} in {industry.name}")
                    else:
                        self.log(f"Subcategory already exists: {subcategory.name} in {industry.name}")

                self.industries.append(industry)
            except Exception as e:
                self.log(f"Error creating industry {industry_data['name']}: {str(e)}", "ERROR")

        return self.industries

    def create_jobs(self):
        """Create sample jobs"""
        self.log(f"Creating {self.jobs_count} jobs...")

        # Disable signals completely to avoid geocoding and job matching
        original_receivers = post_save.receivers
        post_save.receivers = []

        try:
            # Get client users
            clients = [user for user in self.users if hasattr(user, 'profile') and user.profile.role == 'client']
            if not clients:
                clients = [self.users[0]]  # Use admin if no clients
                self.log("No client users found. Using admin user as client.", "WARNING")

            # Get industries and subcategories
            industries = list(JobIndustry.objects.all())
            if not industries:
                self.log("No industries found. Creating industries...", "WARNING")
                industries = self.create_industries()

            # Sample job titles and locations
            job_titles = [
                "Electrician Needed for Wiring Project",
                "Emergency Electrical Repair Technician",
                "Plumber Needed for Bathroom Renovation",
                "Kitchen Sink Installation Expert",
                "General Construction Worker Needed",
                "Drywall Installation Specialist",
                "Handyman for Various Home Repairs",
                "Moving Assistant Needed",
                "Painter for Interior Work",
                "Landscaping and Yard Cleanup",
            ]

            locations = [
                "123 Main St, New York, NY 10001",
                "456 Oak Avenue, Los Angeles, CA 90001",
                "789 Pine Road, Chicago, IL 60601",
                "101 Maple Drive, Houston, TX 77001",
                "202 Cedar Lane, Phoenix, AZ 85001",
            ]

            for i in range(self.jobs_count):
                try:
                    # Select random client
                    client = random.choice(clients)

                    # Select random industry and subcategory
                    industry = random.choice(industries)
                    subcategories = list(JobSubCategory.objects.filter(industry=industry))
                    if not subcategories:
                        self.log(f"No subcategories found for industry {industry.name}. Skipping job creation.", "WARNING")
                        continue
                    subcategory = random.choice(subcategories)

                    # Generate random dates
                    days_offset = random.randint(-30, 30)  # Jobs in the past and future
                    job_date = timezone.now().date() + timedelta(days=days_offset)

                    # Set times
                    start_time = datetime.strptime(f"{random.randint(8, 17)}:00", "%H:%M").time()
                    hours_duration = random.randint(1, 8)
                    end_hour = min(start_time.hour + hours_duration, 23)
                    end_time = datetime.strptime(f"{end_hour}:00", "%H:%M").time()

                    # Set status based on date - using correct status values
                    if job_date < timezone.now().date():
                        status = random.choice(["completed", "canceled"])  # Note: 'canceled' not 'cancelled'
                        payment_status = "paid" if status == "completed" else "refunded"
                    elif job_date == timezone.now().date():
                        status = random.choice(["ongoing", "pending"])
                        payment_status = "pending"
                    else:
                        status = "pending"
                        payment_status = "pending"

                    # Create job with all required fields
                    try:
                        # Create the job directly
                        job = Job(
                            client=client,
                            created_by=client,
                            title=random.choice(job_titles),
                            description=f"This is a sample job in {industry.name} - {subcategory.name}",
                            industry=industry,
                            subcategory=subcategory,
                            applicants_needed=random.randint(1, 5),
                            job_type=random.choice(["single_day", "multiple_days"]),
                            shift_type=random.choice(["morning", "afternoon", "evening"]),
                            date=job_date,
                            start_time=start_time,
                            end_time=end_time,
                            rate=Decimal(str(random.randint(15, 75))),
                            location=random.choice(locations),
                            payment_status=payment_status,
                            status=status,
                            # Pre-set coordinates to avoid geocoding
                            latitude=Decimal("40.712776"),
                            longitude=Decimal("-74.005974"),
                            # Add any other required fields
                            is_active=True,
                            total_amount=Decimal(str(random.randint(50, 500))),
                        )

                        # Save the job directly
                        job.save()

                        self.jobs.append(job)
                        self.log(f"Created job {i+1}/{self.jobs_count}: {job.title} (ID: {job.id}, Status: {job.status})")
                    except Exception as job_error:
                        self.log(f"Error creating job object: {str(job_error)}", "ERROR")
                        continue

                except Exception as e:
                    self.log(f"Error creating job {i+1}: {str(e)}", "ERROR")
        finally:
            # Restore signals
            post_save.receivers = original_receivers

        return self.jobs

    def create_applications(self):
        """Create sample job applications"""
        self.log("Creating applications...")

        # Get applicant users
        applicants = [user for user in self.users if hasattr(user, 'profile') and user.profile.role == 'applicant']
        if not applicants:
            self.log("No applicant users found. Skipping application creation.", "WARNING")
            return []

        # Get jobs
        jobs = self.jobs if self.jobs else list(Job.objects.all())
        if not jobs:
            self.log("No jobs found. Skipping application creation.", "WARNING")
            return []

        for job in jobs:
            # Determine how many applications to create for this job
            num_applications = min(
                self.applications_per_job,  # Specified number of applications
                len(applicants),  # Can't have more applications than applicants
                job.applicants_needed * 2,  # Roughly twice the needed applicants
            )

            # Select random applicants for this job
            selected_applicants = random.sample(applicants, num_applications)

            for applicant in selected_applicants:
                try:
                    # Determine application status based on job status
                    # Using correct status values from Application.Status
                    if job.status == "completed":
                        status = random.choice(["Accepted", "Rejected"])
                    elif job.status == "ongoing":
                        status = "Accepted"
                    elif job.status == "canceled":  # Note: 'canceled' not 'cancelled'
                        status = random.choice(["Rejected", "Withdrawn"])
                    else:
                        status = "Pending"

                    # Check if application already exists
                    existing_app = Application.objects.filter(job=job, applicant=applicant).first()
                    if existing_app:
                        self.log(f"Application already exists for job {job.id} by {applicant.username}", "INFO")
                        self.applications.append(existing_app)
                        continue

                    # Create application with signal disabling
                    try:
                        # Disable signals temporarily

                        # Store the original receivers
                        receivers = post_save.receivers
                        post_save.receivers = []

                        # Create application
                        application = Application.objects.create(
                            job=job,
                            applicant=applicant,
                            status=status,
                        )

                        # Restore the original receivers
                        post_save.receivers = receivers
                    except Exception as app_error:
                        self.log(f"Error creating application: {str(app_error)}", "ERROR")
                        continue

                    self.applications.append(application)
                    self.log(f"Created application for job {job.id} by {applicant.username} (Status: {status})")

                except Exception as e:
                    self.log(f"Error creating application for job {job.id} by {applicant.username}: {str(e)}", "ERROR")

        return self.applications

    def reset_data(self):
        """Reset existing data if requested"""
        if not self.reset:
            return

        self.log("Resetting existing data...", "WARNING")

        try:
            # Only delete data that we're going to recreate
            if self.args.only_apps or not self.args.only_users and not self.args.only_jobs:
                self.log("Deleting existing applications...")
                Application.objects.all().delete()

            if self.args.only_jobs or not self.args.only_users and not self.args.only_apps:
                self.log("Deleting existing jobs...")
                Job.objects.all().delete()

            if self.args.only_users or not self.args.only_jobs and not self.args.only_apps:
                # Don't delete the admin user
                self.log("Deleting non-admin users...")
                User.objects.filter(is_superuser=False).delete()

            self.log("Data reset complete.")
        except Exception as e:
            self.log(f"Error resetting data: {str(e)}", "ERROR")

    def run(self):
        """Run the database population process"""
        self.log("Starting database population...")

        # Reset data if requested
        self.reset_data()

        # Create data based on options - without using a single large transaction
        # This avoids issues with geocoding and other operations that might cause transaction errors

        try:
            # Create users first
            if self.args.only_users or not (self.args.only_jobs or self.args.only_apps):
                self.create_users()
                self.log("Users created successfully")
        except Exception as e:
            self.log(f"Error creating users: {str(e)}", "ERROR")

        try:
            # Then create jobs
            if self.args.only_jobs or not (self.args.only_users or self.args.only_apps):
                if not self.users:
                    self.users = list(User.objects.all())
                self.create_jobs()
                self.log("Jobs created successfully")
        except Exception as e:
            self.log(f"Error creating jobs: {str(e)}", "ERROR")

        try:
            # Finally create applications
            if self.args.only_apps or not (self.args.only_users or self.args.only_jobs):
                if not self.users:
                    self.users = list(User.objects.all())
                if not self.jobs:
                    self.jobs = list(Job.objects.all())
                self.create_applications()
                self.log("Applications created successfully")
        except Exception as e:
            self.log(f"Error creating applications: {str(e)}", "ERROR")

        # Print summary
        self.log("\nDatabase population completed!")
        self.log(f"Created/Found {len(self.roles)} roles")
        self.log(f"Created/Found {len(self.users)} users")
        self.log(f"Created/Found {len(self.industries)} industries")
        self.log(f"Created/Found {len(self.jobs)} jobs")
        self.log(f"Created/Found {len(self.applications)} applications")

        return {
            'roles': self.roles,
            'users': self.users,
            'industries': self.industries,
            'jobs': self.jobs,
            'applications': self.applications
        }


def main():
    """Main function to parse arguments and run the populator"""
    parser = argparse.ArgumentParser(description="Populate the database with sample data")

    parser.add_argument("--users", type=int, default=10, help="Number of users to create (default: 10)")
    parser.add_argument("--jobs", type=int, default=20, help="Number of jobs to create (default: 20)")
    parser.add_argument("--applications", type=int, default=3, help="Number of applications per job (default: 3)")

    parser.add_argument("--only-users", action="store_true", help="Create only users and profiles")
    parser.add_argument("--only-jobs", action="store_true", help="Create only jobs (requires existing users)")
    parser.add_argument("--only-apps", action="store_true", help="Create only applications (requires existing jobs and users)")

    parser.add_argument("--reset", action="store_true", help="Reset existing data before creating new data")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")

    args = parser.parse_args()

    # Run the populator
    populator = DatabasePopulator(args)
    populator.run()


if __name__ == "__main__":
    main()
