import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from payment.models import Wallet
from accounts.utils import get_user_response

User = get_user_model()

class Command(BaseCommand):
    help = 'Check wallet balance and whoami response for a user'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='User email')

    def handle(self, *args, **options):
        email = options['email']
        
        # Find the user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with email {email} not found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Found user: {user.username} (ID: {user.id})'))
        
        # Check wallet balance directly from the Wallet model
        try:
            wallet = Wallet.objects.get(user=user)
            self.stdout.write(self.style.SUCCESS(f'Wallet balance from Wallet model: {wallet.balance}'))
        except Wallet.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'No wallet found for user {user.username}'))
            return
        
        # Get whoami response
        try:
            user_response = get_user_response(user)
            whoami_balance = user_response.get('wallet_balance')
            self.stdout.write(self.style.SUCCESS(f'Wallet balance from whoami: {whoami_balance}'))
            
            # Check if there's a discrepancy
            if str(wallet.balance) != whoami_balance:
                self.stdout.write(self.style.ERROR(
                    f'DISCREPANCY DETECTED: Wallet model: {wallet.balance}, whoami: {whoami_balance}'
                ))
            else:
                self.stdout.write(self.style.SUCCESS('Wallet balance is consistent'))
                
            # Print the full whoami response for reference
            self.stdout.write(self.style.SUCCESS('Full whoami response:'))
            self.stdout.write(json.dumps(user_response, indent=2))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting whoami response: {str(e)}'))
