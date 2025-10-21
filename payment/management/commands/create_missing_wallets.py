from decimal import Decimal
import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from payment.models import Wallet

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Creates wallets for users who do not have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user_id',
            type=int,
            help='Create wallet for a specific user ID',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode - no changes will be made'))
        
        if user_id:
            # Process a single user
            try:
                user = User.objects.get(id=user_id)
                self._process_user(user, dry_run)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User with ID {user_id} does not exist'))
        else:
            # Process all users
            users_without_wallets = []
            
            # First, identify users without wallets
            for user in User.objects.all():
                if not hasattr(user, 'wallet'):
                    users_without_wallets.append(user)
            
            # Report the count
            self.stdout.write(f'Found {len(users_without_wallets)} users without wallets')
            
            # Process each user
            for user in users_without_wallets:
                self._process_user(user, dry_run)
                
        self.stdout.write(self.style.SUCCESS('Wallet creation process completed'))
    
    def _process_user(self, user, dry_run):
        """Process a single user to create a wallet if needed"""
        if hasattr(user, 'wallet'):
            self.stdout.write(f'User {user.id} ({user.email}) already has a wallet')
            return
        
        self.stdout.write(f'Creating wallet for user {user.id} ({user.email})')
        
        if not dry_run:
            try:
                with transaction.atomic():
                    wallet = Wallet.objects.create(
                        user=user,
                        balance=Decimal('0.00')
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'Created wallet for user {user.id} ({user.email})')
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creating wallet for user {user.id}: {str(e)}')
                )
