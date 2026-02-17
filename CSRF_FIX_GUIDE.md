# 🔐 CSRF Cookie Fix Guide

## Problem
Getting "CSRF cookie not set" error when trying to login to Django admin on Render.

## Root Cause
- CSRF cookies weren't being sent due to insecure cookie settings
- Frontend and backend on different domains require proper CORS and CSRF configuration
- Production (HTTPS) requires secure cookie settings

## Solution Applied

### 1. Updated Django Settings (`payshift/settings.py`)

**CSRF Configuration:**
```python
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '...')
CSRF_USE_SESSIONS = True
CSRF_COOKIE_SECURE = os.getenv('DJANGO_DEBUG', 'True').lower() == 'false'  # True in production
CSRF_COOKIE_HTTPONLY = False  # Allow JS to read CSRF token
CSRF_COOKIE_SAMESITE = 'Lax'  # Allow cross-origin CSRF cookies
```

**Session Configuration:**
```python
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = os.getenv('DJANGO_DEBUG', 'True').lower() == 'false'  # True in production
```

**CORS Configuration:**
```python
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]
```

### 2. Render Environment Variables

Set these in Render Dashboard → Settings → Environment:

| Variable | Value |
|----------|-------|
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,paeshift-backend-oeon.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://paeshift-backend-oeon.onrender.com,https://paeshift-frontend.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | `https://paeshift-frontend.onrender.com` |

## How It Works

1. **CSRF_COOKIE_SECURE = True** (in production)
   - Ensures CSRF cookie only sent over HTTPS
   - Required for Render's HTTPS domain

2. **CSRF_COOKIE_HTTPONLY = False**
   - Allows frontend JavaScript to read CSRF token
   - Necessary for AJAX requests

3. **CSRF_COOKIE_SAMESITE = 'Lax'**
   - Allows CSRF cookies in cross-origin requests
   - Balances security with functionality

4. **CORS_ALLOW_CREDENTIALS = True**
   - Allows cookies to be sent with cross-origin requests
   - Required for authentication

## Testing

1. Go to Django admin: `https://paeshift-backend-oeon.onrender.com/admin/`
2. Try to login
3. CSRF cookie should now be set
4. Login should succeed

## Files Modified

- ✅ `paeshift-recover/payshift/settings.py` - Updated CSRF and session settings
- ✅ `paeshift-recover/render.yaml` - Added CSRF_TRUSTED_ORIGINS
- ✅ `paeshift-recover/.env.example` - Added CSRF_TRUSTED_ORIGINS

## Next Steps

1. Commit and push changes
2. Render will auto-deploy
3. Test login at `/admin/`

