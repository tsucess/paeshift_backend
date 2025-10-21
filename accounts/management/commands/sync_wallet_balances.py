from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
import logging

from accounts.models import Profile
from payment.models import Wallet

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Synchronizes Profile.balance with Wallet.balance for all users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Sync only a specific user by ID',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        user_id = options.get('user_id')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode - no changes will be made'))
        
        # Get all profiles or filter by user_id
        profiles = Profile.objects.all()
        if user_id:
            profiles = profiles.filter(user_id=user_id)
            self.stdout.write(f'Syncing only user ID {user_id}')
        
        total_profiles = profiles.count()
        self.stdout.write(f'Found {total_profiles} profiles to process')
        
        updated_count = 0
        missing_wallet_count = 0
        
        for profile in profiles:
            try:
                # Get or create wallet
                wallet, created = Wallet.objects.get_or_create(
                    user=profile.user,
                    defaults={'balance': Decimal('0.00')}
                )
                
                if created:
                    self.stdout.write(f'Created new wallet for user {profile.user.id}')
                
                # Check if balances are different
                if profile.balance != wallet.balance:
                    self.stdout.write(
                        f'User {profile.user.id}: Profile balance {profile.balance} != '
                        f'Wallet balance {wallet.balance}'
                    )
                    
                    if not dry_run:
                        with transaction.atomic():
                            # Update profile balance to match wallet balance
                            profile.balance = wallet.balance
                            profile.save(update_fields=['balance'])
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'Updated profile balance for user {profile.user.id} '
                                    f'from {profile.balance} to {wallet.balance}'
                                )
                            )
                    updated_count += 1
                else:
                    self.stdout.write(f'User {profile.user.id}: Balances already match ({profile.balance})')
                    
            except Exception as e:
                missing_wallet_count += 1
                self.stderr.write(
                    self.style.ERROR(f'Error processing user {profile.user.id}: {str(e)}')
                )
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Processed {total_profiles} profiles'))
        self.stdout.write(f'Profiles needing balance updates: {updated_count}')
        self.stdout.write(f'Profiles with errors: {missing_wallet_count}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('This was a dry run - no changes were made. '
                                  'Run without --dry-run to apply changes.')
            )
