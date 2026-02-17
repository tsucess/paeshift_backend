#!/usr/bin/env python
"""
Test script to verify the complete OTP verification flow
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payshift.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import TemporaryOTP

User = get_user_model()

print("\n" + "="*80)
print("VERIFICATION FLOW TEST")
print("="*80)

# Check all users
print("\n[1] Checking all users in database:")
users = User.objects.all()
print(f"Total users: {users.count()}")
for user in users:
    print(f"  - {user.email}: is_active={user.is_active}, id={user.id}")

# Check all temporary OTPs
print("\n[2] Checking all TemporaryOTP records:")
otps = TemporaryOTP.objects.all()
print(f"Total OTPs: {otps.count()}")
for otp in otps:
    print(f"  - Email: {otp.email}, Type: {otp.otp_type}, is_verified: {otp.is_verified}, id={otp.id}")

# Check for inactive users
print("\n[3] Checking inactive users (should be activated after OTP verification):")
inactive_users = User.objects.filter(is_active=False)
print(f"Inactive users: {inactive_users.count()}")
for user in inactive_users:
    print(f"  - {user.email}: id={user.id}")

print("\n" + "="*80)
print("END OF TEST")
print("="*80 + "\n")

