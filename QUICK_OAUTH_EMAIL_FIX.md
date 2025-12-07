# ⚡ Quick Fix: Google OAuth, Facebook OAuth & Email Verification

**All 3 features not working?** Missing environment variables!

---

## 🚀 What to Do (5 minutes)

### **1. Open Render Dashboard**
```
https://dashboard.render.com
```

### **2. Click paeshift-backend**

### **3. Go to Settings tab**

### **4. Scroll to Environment section**

### **5. Add These 15 Variables**

#### **Email (7 variables)**
```
EMAIL_BACKEND = django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST = smtp.gmail.com
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = onlypayshift@gmail.com
EMAIL_HOST_PASSWORD = wuxyvmldffuljocg
DEFAULT_FROM_EMAIL = Payshift <onlypayshift@gmail.com>
```

#### **Google OAuth (2 variables)**
```
SOCIALACCOUNT_PROVIDERS_GOOGLE_APP_ID = 156251530744-s1jbmhd87adjr99fapotk30p4sgb5mr2.apps.googleusercontent.com
SOCIALACCOUNT_PROVIDERS_GOOGLE_SECRET = YOUR_GOOGLE_CLIENT_SECRET
```

#### **Facebook OAuth (2 variables)**
```
SOCIALACCOUNT_PROVIDERS_FACEBOOK_APP_ID = 1574866086563315
SOCIALACCOUNT_PROVIDERS_FACEBOOK_SECRET = YOUR_FACEBOOK_APP_SECRET
```

#### **Frontend URLs (2 variables)**
```
FRONTEND_URL = https://paeshift-frontend.onrender.com
BASE_URL = https://paeshift-backend-rwp3.onrender.com
```

### **6. Click Save**

### **7. Go to Deployments tab**

### **8. Click "Deploy latest commit"**

### **9. Wait for build to complete**

### **10. Test All 3 Features**

---

## 📝 Where to Get Credentials

### **Google Client Secret**
1. Go to: https://console.cloud.google.com/
2. Select your project
3. Go to "Credentials"
4. Find your OAuth 2.0 Client ID
5. Click on it
6. Copy "Client Secret"

### **Facebook App Secret**
1. Go to: https://developers.facebook.com/
2. Select your app
3. Go to "Settings" → "Basic"
4. Copy "App Secret"

---

## ✅ What This Fixes

- ✅ Email verification codes sent
- ✅ Google OAuth login works
- ✅ Facebook OAuth login works
- ✅ Users can sign up and verify
- ✅ Users can login with social accounts

---

## 🧪 Test After Deployment

### **Email Verification**
- Sign up with email
- Check inbox for verification code
- Enter code to verify

### **Google OAuth**
- Click "Login with Google"
- Authenticate
- Should be logged in

### **Facebook OAuth**
- Click "Login with Facebook"
- Authenticate
- Should be logged in

---

## 🎉 Done!

All three features will now work! Users can:
- ✅ Sign up with email verification
- ✅ Login with Google
- ✅ Login with Facebook

---

**That's it! Just add the environment variables and redeploy.** ✅

