#!/usr/bin/env python
"""
Delete all users from the database for testing purposes
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payshift.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Profile, OTP, UserActivityLog
from django.db import transaction

User = get_user_model()

def delete_all_users():
    """Delete all users and related data from the database"""
    
    print("🗑️ DELETING ALL USERS FROM DATABASE")
    print("=" * 50)
    
    try:
        with transaction.atomic():
            # Get counts before deletion
            user_count = User.objects.count()
            profile_count = Profile.objects.count()
            otp_count = OTP.objects.count()
            activity_count = UserActivityLog.objects.count()
            
            print(f"📊 Current counts:")
            print(f"   👥 Users: {user_count}")
            print(f"   📋 Profiles: {profile_count}")
            print(f"   🔐 OTPs: {otp_count}")
            print(f"   📝 Activity logs: {activity_count}")
            
            if user_count == 0:
                print("\n✅ No users to delete - database is already clean!")
                return
            
            # Delete related data first
            print(f"\n🗑️ Deleting related data...")
            
            # Delete OTPs
            deleted_otps = OTP.objects.all().delete()
            print(f"   🔐 Deleted {deleted_otps[0]} OTP records")
            
            # Delete Activity logs
            deleted_activities = UserActivityLog.objects.all().delete()
            print(f"   📝 Deleted {deleted_activities[0]} activity log records")
            
            # Delete Profiles
            deleted_profiles = Profile.objects.all().delete()
            print(f"   📋 Deleted {deleted_profiles[0]} profile records")
            
            # Delete Users (this will cascade to related models)
            deleted_users = User.objects.all().delete()
            print(f"   👥 Deleted {deleted_users[0]} user records")
            
            print(f"\n🎉 SUCCESS! All users and related data deleted!")
            print(f"✅ Database is now clean for fresh testing")
            
    except Exception as e:
        print(f"\n❌ ERROR deleting users: {str(e)}")
        return False
    
    return True

def verify_deletion():
    """Verify that all users have been deleted"""
    
    print(f"\n🔍 VERIFYING DELETION")
    print("-" * 30)
    
    user_count = User.objects.count()
    profile_count = Profile.objects.count()
    otp_count = OTP.objects.count()
    activity_count = UserActivityLog.objects.count()
    
    print(f"📊 Final counts:")
    print(f"   👥 Users: {user_count}")
    print(f"   📋 Profiles: {profile_count}")
    print(f"   🔐 OTPs: {otp_count}")
    print(f"   📝 Activity logs: {activity_count}")
    
    if user_count == 0 and profile_count == 0 and otp_count == 0:
        print(f"\n✅ VERIFICATION PASSED - All user data deleted!")
        return True
    else:
        print(f"\n❌ VERIFICATION FAILED - Some data still exists!")
        return False

def create_superuser_option():
    """Ask if user wants to create a new superuser"""
    
    print(f"\n🔧 CREATE NEW SUPERUSER?")
    print("-" * 30)
    
    create_super = input("Do you want to create a new superuser? (y/n): ").lower().strip()
    
    if create_super == 'y' or create_super == 'yes':
        print(f"\n👤 Creating superuser...")
        
        try:
            # Create superuser
            superuser = User.objects.create_superuser(
                email='admin@paeshift.com',
                password='admin123',
                first_name='Admin',
                last_name='User'
            )
            
            print(f"✅ Superuser created successfully!")
            print(f"📧 Email: admin@paeshift.com")
            print(f"🔐 Password: admin123")
            print(f"🌐 Login at: http://localhost:8000/admin/")
            
        except Exception as e:
            print(f"❌ Error creating superuser: {str(e)}")

def main():
    """Main function"""
    
    print("🗑️ USER DELETION SCRIPT")
    print("=" * 70)
    
    # Confirm deletion
    confirm = input("⚠️ This will DELETE ALL USERS! Are you sure? (type 'DELETE' to confirm): ")
    
    if confirm != 'DELETE':
        print("❌ Deletion cancelled - users are safe!")
        return
    
    # Delete all users
    success = delete_all_users()
    
    if success:
        # Verify deletion
        verify_deletion()
        
        # Option to create superuser
        create_superuser_option()
        
        print(f"\n🎯 READY FOR FRESH TESTING!")
        print(f"✅ You can now test signup → OTP → dashboard flow")
        print(f"🧪 All test emails will work as new users")
    else:
        print(f"\n❌ Deletion failed - check the errors above")

if __name__ == "__main__":
    main()
