"""
Management command to create sample payments for a user.
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from payment.models import Payment
from jobs.models import Job

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample payments for a user'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username to create payments for')
        parser.add_argument('--count', type=int, default=10, help='Number of payments to create')

    def handle(self, *args, **options):
        username = options.get('username', 'fakoredeabbas')
        count = options.get('count', 10)
        
        self.stdout.write(self.style.SUCCESS(f'Creating {count} payments for user {username}'))
        
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
            
            # Get a list of potential recipients (excluding the target user)
            recipients = list(User.objects.exclude(username=username).values_list('id', flat=True))
            
            if not recipients:
                # Create some recipient users if none exist
                for i in range(5):
                    recipient = User.objects.create_user(
                        username=f'recipient{i}',
                        email=f'recipient{i}@example.com',
                        password='password123',
                        first_name=f'Recipient{i}',
                        last_name='User',
                        role='worker'
                    )
                    recipients.append(recipient.id)
                self.stdout.write(self.style.SUCCESS(f'Created {len(recipients)} recipient users'))
            
            # Sample payment descriptions
            payment_descriptions = [
                "Payment for emergency service",
                "Payment for weekend work",
                "Payment for consultation",
                "Payment for overtime hours",
                "Payment for regular shift"
            ]
            
            # Payment methods
            payment_methods = ["bank", "paystack"]
            
            # Payment statuses
            payment_statuses = ["completed", "pending", "failed"]
            status_weights = [0.6, 0.3, 0.1]  # 60% completed, 30% pending, 10% failed
            
            # Create the sample payments
            for i in range(count):
                # Generate a random payment code
                pay_code = f"PAY-{random.randint(100000, 999999)}"
                
                # Select a random recipient
                recipient_id = random.choice(recipients)
                recipient = User.objects.get(pk=recipient_id)
                
                # Generate a random amount between 5000 and 50000
                original_amount = Decimal(str(random.randint(5000, 50000)))
                
                # Calculate service fee (5% of original amount)
                service_fee = original_amount * Decimal('0.05')
                
                # Calculate final amount
                final_amount = original_amount - service_fee
                
                # Select a random payment method
                payment_method = random.choice(payment_methods)
                
                # Select a random status based on weights
                status = random.choices(payment_statuses, weights=status_weights)[0]
                
                # Select a random description
                description = random.choice(payment_descriptions)
                
                # Create a random date in the past (up to 30 days ago)
                days_ago = random.randint(0, 30)
                created_at = datetime.now() - timedelta(days=days_ago)
                
                # Create a job for this payment
                job = None
                try:
                    # Try to find an existing job
                    jobs = Job.objects.all()
                    if jobs.exists():
                        job = random.choice(jobs)
                    else:
                        # Create a new job if none exist
                        job = Job.objects.create(
                            title=description,
                            description=f"Job for {description.lower()}",
                            client=user,
                            worker=recipient,
                            status="completed",
                            budget=original_amount
                        )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error creating job: {str(e)}'))
                
                # Create the payment
                payment = Payment.objects.create(
                    pay_code=pay_code,
                    payer=user,
                    recipient=recipient,
                    original_amount=original_amount,
                    service_fee=service_fee,
                    final_amount=final_amount,
                    status=status,
                    payment_method=payment_method,
                    description=description,
                    job=job
                )
                
                # Set created_at date
                payment.created_at = created_at
                payment.save(update_fields=['created_at'])
                
                self.stdout.write(self.style.SUCCESS(
                    f'Created payment: {pay_code}, Amount: ₦{original_amount}, Status: {status}'
                ))
            
            self.stdout.write(self.style.SUCCESS(f'Successfully created {count} payments for user {username}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
