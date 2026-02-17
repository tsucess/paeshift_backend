"""
Management command to test email configuration
"""
from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test email configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            'email',
            type=str,
            help='Email address to send test email to'
        )

    def handle(self, *args, **options):
        email = options['email']
        
        self.stdout.write(self.style.SUCCESS('🧪 Testing Email Configuration'))
        self.stdout.write('=' * 60)
        
        # Print configuration
        self.stdout.write(f'\n📧 Email Configuration:')
        self.stdout.write(f'  EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'  EMAIL_HOST: {settings.EMAIL_HOST}')
        self.stdout.write(f'  EMAIL_PORT: {settings.EMAIL_PORT}')
        self.stdout.write(f'  EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}')
        self.stdout.write(f'  EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}')
        self.stdout.write(f'  DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
        
        # Check if they match
        if settings.EMAIL_HOST_USER != settings.DEFAULT_FROM_EMAIL.split('<')[-1].rstrip('>'):
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  WARNING: EMAIL_HOST_USER and DEFAULT_FROM_EMAIL do not match!'
            ))
            self.stdout.write(f'  EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}')
            self.stdout.write(f'  DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Email configuration looks good!'
            ))
        
        # Try to send test email
        self.stdout.write(f'\n📤 Sending test email to: {email}')
        
        try:
            msg = EmailMultiAlternatives(
                subject='Test Email - Paeshift',
                body='This is a test email from Paeshift.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email]
            )
            
            html_message = '''
            <html>
                <body>
                    <h2>Test Email</h2>
                    <p>This is a test email from Paeshift.</p>
                    <p>If you received this, your email configuration is working!</p>
                </body>
            </html>
            '''
            
            msg.attach_alternative(html_message, "text/html")
            
            result = msg.send(fail_silently=False)
            
            if result > 0:
                self.stdout.write(self.style.SUCCESS(
                    f'\n✅ Test email sent successfully!'
                ))
                self.stdout.write(f'  Recipient: {email}')
                self.stdout.write(f'  From: {settings.DEFAULT_FROM_EMAIL}')
            else:
                self.stdout.write(self.style.ERROR(
                    f'\n❌ Email send returned 0 (no emails sent)'
                ))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'\n❌ Failed to send test email: {str(e)}'
            ))
            import traceback
            self.stdout.write(self.style.ERROR(
                f'\n📋 Traceback:\n{traceback.format_exc()}'
            ))
        
        self.stdout.write('\n' + '=' * 60)

