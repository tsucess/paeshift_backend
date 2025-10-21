#!/usr/bin/env python
"""
Comprehensive email diagnosis script
"""
import os
import django
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payshift.settings')
django.setup()

from django.conf import settings

def test_smtp_connection():
    """Test SMTP connection step by step"""
    print("🔍 STEP 1: Testing SMTP Connection")
    print("=" * 50)
    
    # Current settings
    host = settings.EMAIL_HOST
    port = settings.EMAIL_PORT
    username = settings.EMAIL_HOST_USER
    password = settings.EMAIL_HOST_PASSWORD
    use_tls = settings.EMAIL_USE_TLS
    
    print(f"📧 Host: {host}")
    print(f"📧 Port: {port}")
    print(f"📧 Username: {username}")
    print(f"📧 Password: {'*' * len(password)} (length: {len(password)})")
    print(f"📧 Use TLS: {use_tls}")
    
    try:
        print("\n🔌 Connecting to SMTP server...")
        server = smtplib.SMTP(host, port)
        print("✅ Connected to SMTP server")
        
        print("🔒 Starting TLS...")
        server.starttls()
        print("✅ TLS started")
        
        print("🔑 Attempting login...")
        server.login(username, password)
        print("✅ Login successful!")
        
        server.quit()
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_different_passwords():
    """Test different password formats"""
    print("\n🔍 STEP 2: Testing Different Password Formats")
    print("=" * 50)
    
    passwords_to_try = [
        "tiwpauxhjnrzpnf",  # No spaces
        "tiwp auxh jnrz pnf",  # With spaces
        "tiwp-auxh-jnrz-pnf",  # With dashes
    ]
    
    host = settings.EMAIL_HOST
    port = settings.EMAIL_PORT
    username = settings.EMAIL_HOST_USER
    
    for i, password in enumerate(passwords_to_try, 1):
        print(f"\n🧪 Test {i}: Password format '{password}'")
        try:
            server = smtplib.SMTP(host, port)
            server.starttls()
            server.login(username, password)
            print("✅ Login successful with this format!")
            server.quit()
            return password
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    return None

def test_onlypayshift_account():
    """Test with onlypayshift@gmail.com account"""
    print("\n🔍 STEP 3: Testing onlypayshift@gmail.com Account")
    print("=" * 50)
    
    # Try with the onlypayshift account
    username = "onlypayshift@gmail.com"
    
    # Common app passwords that might work
    possible_passwords = [
        "tiwpauxhjnrzpnf",
        "tiwp auxh jnrz pnf",
        # Add more if you have them
    ]
    
    host = settings.EMAIL_HOST
    port = settings.EMAIL_PORT
    
    for password in possible_passwords:
        print(f"\n🧪 Testing onlypayshift@gmail.com with password: {'*' * len(password)}")
        try:
            server = smtplib.SMTP(host, port)
            server.starttls()
            server.login(username, password)
            print("✅ Login successful with onlypayshift account!")
            server.quit()
            return username, password
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    return None, None

def send_test_email(username, password):
    """Send a test email"""
    print("\n🔍 STEP 4: Sending Test Email")
    print("=" * 50)
    
    try:
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        server.starttls()
        server.login(username, password)
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = username
        msg['To'] = "akoladeabbas@gmail.com"
        msg['Subject'] = "🔐 Test OTP - Payshift Signup"
        
        body = """
Hello!

Your verification code for Payshift account registration is: 123456

This code will expire in 5 minutes.

If you did not request this code, please ignore this email.

Best regards,
Payshift Team
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        print("📤 Sending test email...")
        server.send_message(msg)
        server.quit()
        
        print("✅ Test email sent successfully!")
        print("🔔 Please check akoladeabbas@gmail.com for the test email")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send test email: {e}")
        return False

def main():
    """Main diagnosis function"""
    print("🚀 Gmail SMTP Diagnosis Starting...")
    print("=" * 60)
    
    # Step 1: Test current connection
    if test_smtp_connection():
        print("\n🎉 Current settings work! Proceeding to send test email...")
        if send_test_email(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD):
            return
    
    # Step 2: Test different password formats
    working_password = test_different_passwords()
    if working_password:
        print(f"\n🎉 Found working password format: {working_password}")
        if send_test_email(settings.EMAIL_HOST_USER, working_password):
            return
    
    # Step 3: Test onlypayshift account
    working_username, working_password = test_onlypayshift_account()
    if working_username and working_password:
        print(f"\n🎉 Found working credentials: {working_username}")
        if send_test_email(working_username, working_password):
            return
    
    # If all fails
    print("\n❌ All tests failed. Recommendations:")
    print("1. Generate a new Gmail app password")
    print("2. Ensure 2FA is enabled on the Gmail account")
    print("3. Check Gmail security settings")
    print("4. Try using a different email service")

if __name__ == "__main__":
    main()
