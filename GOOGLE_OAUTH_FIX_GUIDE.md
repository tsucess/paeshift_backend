# Google OAuth Redirect URI Mismatch - Fix Guide

## Error: `Error 400: redirect_uri_mismatch`

This error occurs when the redirect URI your app is using doesn't match what's configured in Google Cloud Console.

---

## Root Cause

Your frontend uses `@react-oauth/google` which uses the **implicit flow** (no redirect needed), but your backend might be configured for the **authorization code flow** (which requires a redirect URI).

---

## Solution Steps

### Step 1: Go to Google Cloud Console

1. Visit: https://console.cloud.google.com/
2. Select your project: **paeshift**
3. Go to: **APIs & Services** → **Credentials**
4. Find your OAuth 2.0 Client ID (should be: `156251530744-s1jbmhd87adjr99fapotk30p4sgb5mr2.apps.googleusercontent.com`)

### Step 2: Check Authorized Redirect URIs

Click on your OAuth 2.0 Client ID to edit it. You should see a section called **"Authorized redirect URIs"**.

### Step 3: Add/Update Redirect URIs

Add these URIs (adjust based on your environment):

**For Local Development:**
```
http://localhost:5173
http://localhost:5173/signin
http://localhost:8000/accounts/google/login/callback/
http://localhost:8000/accounts/allauth/google/callback/
```

**For Production (Render):**
```
https://your-frontend-url.onrender.com
https://your-frontend-url.onrender.com/signin
https://your-backend-url.onrender.com/accounts/google/login/callback/
https://your-backend-url.onrender.com/accounts/allauth/google/callback/
```

### Step 4: Save Changes

Click **Save** in Google Cloud Console.

### Step 5: Update Django Settings

Add to `paeshift-recover/payshift/settings.py`:

```python
# Google OAuth Configuration
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'APP': {
            'client_id': os.getenv('GOOGLE_OAUTH_CLIENT_ID', '156251530744-s1jbmhd87adjr99fapotk30p4sgb5mr2.apps.googleusercontent.com'),
            'secret': os.getenv('GOOGLE_OAUTH_SECRET', ''),
            'key': 'google'
        }
    }
}
```

### Step 6: Test

1. Clear browser cache/cookies
2. Try Google login again
3. Check browser console for errors

---

## Common Issues

| Issue | Solution |
|-------|----------|
| Still getting redirect_uri_mismatch | Clear Google Cloud cache, wait 5 minutes, try again |
| Frontend works but backend fails | Add backend redirect URIs to Google Cloud Console |
| Token validation fails | Ensure GOOGLE_OAUTH_SECRET is set correctly |

---

## Frontend Configuration

Your frontend is correctly configured in `.env`:
```
VITE_GOOGLE_CLIENT_ID=156251530744-s1jbmhd87adjr99fapotk30p4sgb5mr2.apps.googleusercontent.com
```

This uses the implicit flow (no redirect needed on frontend).

