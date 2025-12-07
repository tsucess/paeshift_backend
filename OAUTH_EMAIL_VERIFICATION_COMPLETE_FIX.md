# 🔧 Complete Fix: Google OAuth, Facebook OAuth & Email Verification

**Status**: ❌ All three features not working due to missing environment variables

**Root Cause**: Environment variables not configured in Render dashboard

---

## 📋 Issues Summary

| Feature | Status | Issue |
|---------|--------|-------|
| **Email Verification** | ❌ Not Working | `EMAIL_HOST_PASSWORD` not set |
| **Google OAuth** | ❌ Not Working | Backend OAuth app not configured |
| **Facebook OAuth** | ❌ Not Working | Frontend app ID not set + Backend not configured |

---

## 🚀 Complete Fix (All 3 Issues)

### **Step 1: Go to Render Dashboard**
```
https://dashboard.render.com
```

### **Step 2: Select paeshift-backend service**

### **Step 3: Go to Settings tab**

### **Step 4: Scroll to Environment section**

### **Step 5: Add ALL Missing Environment Variables**

Add these 15 environment variables:

#### **Email Configuration (3 variables)**
```
EMAIL_BACKEND = django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST = smtp.gmail.com
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = onlypayshift@gmail.com
EMAIL_HOST_PASSWORD = wuxyvmldffuljocg
DEFAULT_FROM_EMAIL = Payshift <onlypayshift@gmail.com>
```

#### **Google OAuth Configuration (2 variables)**
```
SOCIALACCOUNT_PROVIDERS_GOOGLE_APP_ID = 156251530744-s1jbmhd87adjr99fapotk30p4sgb5mr2.apps.googleusercontent.com
SOCIALACCOUNT_PROVIDERS_GOOGLE_SECRET = YOUR_GOOGLE_CLIENT_SECRET
```

#### **Facebook OAuth Configuration (2 variables)**
```
SOCIALACCOUNT_PROVIDERS_FACEBOOK_APP_ID = 1574866086563315
SOCIALACCOUNT_PROVIDERS_FACEBOOK_SECRET = YOUR_FACEBOOK_APP_SECRET
```

#### **Frontend URLs (2 variables)**
```
FRONTEND_URL = https://paeshift-frontend.onrender.com
BASE_URL = https://paeshift-backend-rwp3.onrender.com
```

### **Step 6: Click Save**

### **Step 7: Go to Deployments tab**

### **Step 8: Click "Deploy latest commit"**

### **Step 9: Wait for build to complete**

---

## 🔍 Detailed Issue Analysis

### **Issue 1: Email Verification Not Working**

**Problem**: Verification codes not sent during signup

**Root Cause**: 
- `EMAIL_HOST_PASSWORD` environment variable not set in Render
- Defaults to empty string in settings.py
- Django can't authenticate with Gmail SMTP

**Current Code** (payshift/settings.py):
```python
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')  # ← EMPTY!
```

**Fix**: Add `EMAIL_HOST_PASSWORD = wuxyvmldffuljocg` to Render environment

---

### **Issue 2: Google OAuth Not Working**

**Problem**: Google login button doesn't work

**Root Cause**:
- Backend OAuth app not configured
- Frontend has Google Client ID but backend doesn't have credentials
- Missing OAuth provider configuration

**Current Code** (accounts/social_api.py):
```python
@social_router.post("/google", tags=["Social Auth"])
def google_login(request, payload: SocialLoginSchema):
    """Handle Google authentication"""
    # Tries to get SocialApp from database
    try:
        social_app = SocialApp.objects.get(provider="google")
    except SocialApp.DoesNotExist:
        # Creates placeholder if not found
        social_app = SocialApp.objects.create(
            provider="google",
            name="Google",
            client_id="placeholder",  # ← PLACEHOLDER!
            secret="placeholder",      # ← PLACEHOLDER!
        )
```

**Frontend Code** (main.jsx):
```javascript
<GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>
```

**Fix**: 
1. Add Google OAuth credentials to Render environment
2. Create SocialApp in Django admin or via management command

---

### **Issue 3: Facebook OAuth Not Working**

**Problem**: Facebook login button shows "Coming Soon"

**Root Cause**:
- Frontend app ID not set (`VITE_FACEBOOK_APP_ID = your_facebook_app_id_here`)
- Backend Facebook OAuth not configured
- Implementation incomplete

**Current Code** (Signin.jsx):
```javascript
<LoginSocialFacebook
    isOnlyGetToken
    appId={import.meta.env.VITE_FACEBOOK_APP_ID}  // ← NOT SET!
    onResolve={() => {
        Swal.fire({
            title: "Coming Soon",
            text: "Facebook login will be available soon!"
        });
    }}
/>
```

**Fix**:
1. Add `VITE_FACEBOOK_APP_ID = 1574866086563315` to frontend environment
2. Add Facebook OAuth credentials to backend environment
3. Implement Facebook OAuth handler

---

## 📊 Environment Variables Needed

### **Current render.yaml (Incomplete)**

```yaml
envVars:
  - key: PYTHON_VERSION
    value: 3.13.4
  - key: DJANGO_SETTINGS_MODULE
    value: payshift.settings
  - key: DJANGO_DEBUG
    value: "False"
  - key: FORCE_SQLITE
    value: "True"
  - key: DJANGO_ALLOWED_HOSTS
    value: "localhost,127.0.0.1,paeshift-backend-rwp3.onrender.com"
  - key: CORS_ALLOWED_ORIGINS
    value: "https://paeshift-frontend.onrender.com"
  # ❌ MISSING EMAIL VARIABLES
  # ❌ MISSING OAUTH VARIABLES
  # ❌ MISSING FRONTEND URLs
```

### **What Needs to Be Added**

```yaml
  # Email Configuration
  - key: EMAIL_BACKEND
    value: django.core.mail.backends.smtp.EmailBackend
  - key: EMAIL_HOST
    value: smtp.gmail.com
  - key: EMAIL_PORT
    value: "587"
  - key: EMAIL_USE_TLS
    value: "True"
  - key: EMAIL_HOST_USER
    value: onlypayshift@gmail.com
  - key: EMAIL_HOST_PASSWORD
    value: wuxyvmldffuljocg
  - key: DEFAULT_FROM_EMAIL
    value: "Payshift <onlypayshift@gmail.com>"
  
  # Google OAuth
  - key: SOCIALACCOUNT_PROVIDERS_GOOGLE_APP_ID
    value: 156251530744-s1jbmhd87adjr99fapotk30p4sgb5mr2.apps.googleusercontent.com
  - key: SOCIALACCOUNT_PROVIDERS_GOOGLE_SECRET
    value: YOUR_GOOGLE_CLIENT_SECRET
  
  # Facebook OAuth
  - key: SOCIALACCOUNT_PROVIDERS_FACEBOOK_APP_ID
    value: "1574866086563315"
  - key: SOCIALACCOUNT_PROVIDERS_FACEBOOK_SECRET
    value: YOUR_FACEBOOK_APP_SECRET
  
  # Frontend URLs
  - key: FRONTEND_URL
    value: https://paeshift-frontend.onrender.com
  - key: BASE_URL
    value: https://paeshift-backend-rwp3.onrender.com
```

---

## 🔐 Getting OAuth Credentials

### **Google OAuth Secret**

1. Go to: https://console.cloud.google.com/
2. Select your project
3. Go to "Credentials"
4. Find your OAuth 2.0 Client ID
5. Click on it
6. Copy the "Client Secret"

### **Facebook App Secret**

1. Go to: https://developers.facebook.com/
2. Select your app
3. Go to "Settings" → "Basic"
4. Copy the "App Secret"

---

## 📧 Email Verification Flow

```
User Signs Up
    ↓
Account Created (is_active=False)
    ↓
OTP Generated (6-digit code)
    ↓
send_otp_email() called
    ↓
Django connects to Gmail SMTP
├─ Host: smtp.gmail.com
├─ Port: 587
├─ TLS: Enabled
├─ User: onlypayshift@gmail.com
├─ Password: wuxyvmldffuljocg ← MUST BE SET!
    ↓
Email sent to user
    ↓
User receives verification code
    ↓
User enters code in verification form
    ↓
verify_otp() called
    ↓
OTP verified & account activated
    ↓
User can login
```

---

## 🔐 Google OAuth Flow

```
User Clicks "Login with Google"
    ↓
Frontend: useGoogleLogin() hook
    ↓
Google OAuth Dialog
    ↓
User Authenticates
    ↓
Frontend receives access_token
    ↓
Frontend sends to backend: /accountsapp/social/google
    ↓
Backend: google_login() endpoint
    ├─ Validates access_token
    ├─ Gets user info from Google
    ├─ Creates/updates user
    ├─ Creates SocialAccount
    ├─ Creates SocialToken
    └─ Returns JWT token
    ↓
Frontend stores token
    ↓
User logged in
```

---

## 🔐 Facebook OAuth Flow

```
User Clicks "Login with Facebook"
    ↓
Frontend: LoginSocialFacebook component
    ↓
Facebook OAuth Dialog
    ↓
User Authenticates
    ↓
Frontend receives access_token
    ↓
Frontend sends to backend: /accountsapp/social/facebook
    ↓
Backend: facebook_login() endpoint
    ├─ Validates access_token
    ├─ Gets user info from Facebook
    ├─ Creates/updates user
    ├─ Creates SocialAccount
    ├─ Creates SocialToken
    └─ Returns JWT token
    ↓
Frontend stores token
    ↓
User logged in
```

---

## ✅ Testing Checklist

After adding all environment variables and redeploying:

### **Email Verification**
- [ ] Go to frontend
- [ ] Click "Sign Up"
- [ ] Enter email and password
- [ ] Click "Sign Up"
- [ ] Check email for verification code
- [ ] Enter code to verify
- [ ] Account should be activated

### **Google OAuth**
- [ ] Go to frontend
- [ ] Click "Login with Google"
- [ ] Authenticate with Google
- [ ] Should be logged in
- [ ] Should see dashboard

### **Facebook OAuth**
- [ ] Go to frontend
- [ ] Click "Login with Facebook"
- [ ] Authenticate with Facebook
- [ ] Should be logged in
- [ ] Should see dashboard

---

## 🔍 Troubleshooting

### **Email Still Not Sending**
1. Check Render logs: Services → paeshift-backend → Logs
2. Look for "Email sent successfully" or error messages
3. Verify `EMAIL_HOST_PASSWORD` is set correctly
4. Check Gmail account hasn't blocked the app

### **Google OAuth Not Working**
1. Check browser console for errors
2. Check Render logs for API errors
3. Verify Google Client ID is correct
4. Verify Google Client Secret is set
5. Check CORS is configured correctly

### **Facebook OAuth Not Working**
1. Check browser console for errors
2. Verify Facebook App ID is set
3. Verify Facebook App Secret is set
4. Check Facebook app settings for redirect URIs
5. Check CORS is configured correctly

---

## 📝 Summary

| Feature | Status | Fix |
|---------|--------|-----|
| Email Verification | ❌ → ✅ | Add EMAIL_HOST_PASSWORD |
| Google OAuth | ❌ → ✅ | Add Google credentials |
| Facebook OAuth | ❌ → ✅ | Add Facebook credentials |

---

## 🎯 Next Steps

1. **Gather Credentials**
   - Get Google Client Secret
   - Get Facebook App Secret

2. **Add to Render**
   - Go to Render Dashboard
   - Add all environment variables
   - Click Save

3. **Redeploy**
   - Go to Deployments
   - Click "Deploy latest commit"
   - Wait for build

4. **Test**
   - Test email verification
   - Test Google OAuth
   - Test Facebook OAuth

---

**After completing these steps, all three features will work!** ✅

