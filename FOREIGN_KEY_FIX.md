# Foreign Key Constraint Fix for User Deletion

## Problem
When attempting to delete a CustomUser from the Django admin, you were getting:
```
django.db.utils.IntegrityError: FOREIGN KEY constraint failed
```

## Root Cause
SQLite enforces foreign key constraints, and the CustomUser model has multiple related models with foreign key relationships:
- **Profile** (OneToOneField with CASCADE)
- **GoogleAuthSession** (ForeignKey with CASCADE)
- **OTP** (ForeignKey with CASCADE)
- **Notification** (ForeignKey with CASCADE)
- **NotificationPreference** (OneToOneField with CASCADE)
- **Application** (ForeignKey with CASCADE)
- **SavedJob** (ForeignKey with CASCADE)
- **Job** (ForeignKey for created_by and selected_applicant with CASCADE)
- **Payment** (ForeignKey with CASCADE - payer and recipient)
- **Review** (ForeignKey with CASCADE - reviewer and reviewed)
- **Feedback** (ForeignKey with SET_NULL)
- **Message** (ForeignKey with CASCADE)
- **LocationHistory** (ForeignKey with CASCADE)
- **UserActivity** (ForeignKey with CASCADE)
- **UserReward** (ForeignKey with CASCADE)
- **UserPoints** (ForeignKey with CASCADE)
- **Ranking** (ForeignKey with CASCADE)
- **MFASecret** (OneToOneField with CASCADE)
- **UserSession** (ForeignKey with CASCADE - from allauth)

Django's default deletion mechanism sometimes fails with SQLite when there are complex cascading relationships.

## Solution
Added a custom admin action `delete_users_with_cascade` in `accounts/admin.py` that:

1. **Explicitly deletes related objects in the correct order** before deleting the user
2. **Uses database transactions** to ensure atomicity
3. **Handles import errors gracefully** for optional apps
4. **Provides user feedback** on successful deletion

## Changes Made

### Updated `accounts/admin.py`
- Added `delete_users_with_cascade` custom action
- Registered the action in `CustomUserAdmin.actions`
- Deletes related data in this order:
  1. Notifications
  2. Job applications, saved jobs, and jobs created by/assigned to user
  3. Payments
  4. Reviews and feedback
  5. Chat messages and location history
  6. Gamification data (activities, rewards, points)
  7. Godmode data (rankings, MFA secrets)
  8. Allauth user sessions
  9. Google auth sessions
  10. OTP records
  11. Profile
  12. User

## How to Use

### Method 1: Using the Custom Admin Action (Recommended)
1. Go to Django Admin: `http://localhost:8000/admin/accounts/customuser/`
2. Select one or more users to delete
3. From the "Action" dropdown, select **"Delete selected users and all related data"**
4. Click "Go" and confirm

### Method 2: Deleting Individual Users
1. Go to Django Admin: `http://localhost:8000/admin/accounts/customuser/`
2. Click on a user to open their detail page
3. Click the "Delete" button at the bottom
4. Confirm the deletion

Both methods will now properly handle deletion of all related data.

## Technical Details

### What Was Changed

1. **Enhanced `delete_users_with_cascade` action** - Now handles all 19 related models
2. **Overridden `delete_model` method** - Ensures cascade deletion works for both bulk and individual deletions
3. **Removed default delete action** - Prevents Django's default delete from being used

### Deletion Order (Critical for SQLite)
The deletion happens in this specific order to avoid foreign key constraint violations:
1. Notifications and preferences
2. Job applications, saved jobs, and jobs
3. Payments
4. Reviews and feedback
5. Chat messages and location history
6. Gamification data
7. Godmode data
8. Allauth sessions
9. Google auth sessions
10. OTP records
11. User profile
12. User account

## Benefits
- ✅ Proper cascading deletion
- ✅ Works with SQLite foreign key constraints
- ✅ Atomic transactions (all-or-nothing)
- ✅ Clear user feedback
- ✅ Handles optional apps gracefully
- ✅ No database configuration changes needed
- ✅ Comprehensive coverage of all 19 related models
- ✅ Works for both bulk and individual deletions

## Troubleshooting

### If you still get "FOREIGN KEY constraint failed"
1. **Clear browser cache** - The admin interface may be cached
2. **Restart Django server** - Changes to admin.py require a server restart
3. **Check the action dropdown** - Make sure you're using the custom action, not the default delete

### If deletion is slow
- This is normal for users with many related records
- The deletion is atomic, so it's all-or-nothing
- Be patient and don't refresh the page

