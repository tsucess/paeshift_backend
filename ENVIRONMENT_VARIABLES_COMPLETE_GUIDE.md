# 📚 Complete Environment Variables Guide

**Date**: 2025-10-21  
**Status**: ✅ COMPREHENSIVE GUIDE

---

## 🎯 Quick Answer to Your Question

### What Was Removed?
```
❌ rfm360-c455b2faa813.json (Google Cloud credentials file)
```

### Why?
```
It was committed to git - SECURITY RISK!
Credentials should be in .env files, not JSON files in repo
```

### What Should You Do?
```
✅ Use environment variables instead
✅ Store credentials in .env (local) or Render Dashboard (production)
✅ Never commit .env or credential files to git
```

---

## 📋 All Environment Variables You Need

### 1. Django Core Settings
```
DJANGO_SECRET_KEY=<generate-with-django>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-backend.onrender.com
```

### 2. Database
```
DATABASE_URL=postgresql://user:password@host:port/database
# OR individual fields:
DATABASE_NAME=paeshift
DATABASE_USER=postgres
DATABASE_PASSWORD=your_password
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

### 3. CORS (Frontend Communication)
```
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,https://your-frontend.onrender.com
```

### 4. AWS S3 (Media Storage)
```
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_STORAGE_BUCKET_NAME=paeshift-media
AWS_S3_REGION_NAME=us-west-2
AWS_S3_CUSTOM_DOMAIN=
AWS_S3_ENDPOINT_URL=
AWS_DEFAULT_ACL=public-read
AWS_LOCATION=media
```

### 5. Payment Processing - Paystack
```
PAYSTACK_SECRET_KEY=sk_test_xxxxxxxxxxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx
```

### 6. Payment Processing - Flutterwave
```
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-xxxxxxxxxxxxx
FLUTTERWAVE_PUBLIC_KEY=FLWPUBK_TEST-xxxxxxxxxxxxx
FLUTTERWAVE_WEBHOOK_HASH=your_webhook_hash
```

### 7. Email Configuration (Gmail)
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your_gmail_app_password
DEFAULT_FROM_EMAIL=Payshift <your-email@gmail.com>
OTP_EMAIL_SUBJECT=Verify Your Email - Payshift
OTP_EXPIRY_MINUTES=10
```

### 8. Redis (Caching)
```
REDIS_URL=redis://localhost:6379/0
```

### 9. Celery (Background Tasks)
```
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### 10. Sentry (Error Tracking)
```
SENTRY_DSN=https://xxxxx@sentry.io/project-id
```

### 11. Google Maps API
```
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

### 12. Google Cloud Credentials (NEW - Proper Way)
```
# Option 1: Path to credentials file
GOOGLE_CREDENTIALS_PATH=/path/to/google-credentials.json

# Option 2: Base64 encoded JSON
GOOGLE_CREDENTIALS_JSON=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...

# Option 3: Individual fields
GOOGLE_PROJECT_ID=rfm360
GOOGLE_PRIVATE_KEY_ID=c455b2faa813872a77b2ed05fcf4bbb0bd7bb6b4
GOOGLE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCG2b8TwHt0hajt\n...
GOOGLE_CLIENT_EMAIL=sachin-rfm360-io@rfm360.iam.gserviceaccount.com
GOOGLE_CLIENT_ID=113114003622799775514
```

---

## 🚀 Setup Instructions

### Local Development

**Step 1: Copy template**
```bash
cp .env.example .env
```

**Step 2: Edit .env with your values**
```bash
nano .env
# or use your favorite editor
```

**Step 3: Add to .gitignore** (already done)
```
.env
.env.local
google-credentials.json
*.json  # Credential files
```

**Step 4: Test**
```bash
python manage.py migrate
python manage.py runserver
```

### Production (Render)

**Step 1: Go to Render Dashboard**
```
https://render.com/dashboard
```

**Step 2: Select your Web Service**
```
Services → Your Backend Service
```

**Step 3: Go to Environment tab**
```
Settings → Environment
```

**Step 4: Add each variable**
```
DJANGO_SECRET_KEY=<generate-new-key>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-backend.onrender.com
DATABASE_URL=<from-render-postgres>
CORS_ALLOWED_ORIGINS=https://your-frontend.onrender.com
# ... and all others
```

**Step 5: Deploy**
```
Manual Deploy → Deploy latest commit
```

---

## 🔐 How to Get Each Credential

### Django Secret Key
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Database URL (Render PostgreSQL)
```
1. Create PostgreSQL on Render
2. Copy "Internal Database URL"
3. Format: postgresql://user:password@host:port/db
```

### AWS Credentials
```
1. Go to AWS IAM Console
2. Create new user or use existing
3. Create access key
4. Copy Access Key ID and Secret Access Key
```

### Paystack Keys
```
1. Go to https://dashboard.paystack.com
2. Settings → API Keys & Webhooks
3. Copy Secret Key and Public Key
```

### Flutterwave Keys
```
1. Go to https://dashboard.flutterwave.com
2. Settings → API Keys
3. Copy Secret Key and Public Key
```

### Gmail App Password
```
1. Go to https://myaccount.google.com/security
2. Enable 2-Factor Authentication
3. Go to "App passwords"
4. Generate password for "Mail"
5. Copy 16-character password
```

### Google Cloud Credentials
```
1. Go to Google Cloud Console
2. Service Accounts
3. Create or select service account
4. Create JSON key
5. Download and save locally
6. Encode as base64 or use path
```

### Google Maps API Key
```
1. Go to Google Cloud Console
2. APIs & Services → Credentials
3. Create API Key
4. Restrict to Maps API
5. Copy key
```

---

## 📝 .env.example Template

```
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-backend.onrender.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/paeshift

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://your-frontend.onrender.com

# AWS S3
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=us-west-2

# Paystack
PAYSTACK_SECRET_KEY=sk_test_xxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxx

# Flutterwave
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST-xxxxx
FLUTTERWAVE_PUBLIC_KEY=FLWPUBK_TEST-xxxxx

# Email
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Sentry
SENTRY_DSN=https://xxxxx@sentry.io/project-id

# Google Maps
GOOGLE_MAPS_API_KEY=your-api-key

# Google Cloud
GOOGLE_CREDENTIALS_JSON=<base64-encoded-json>
```

---

## ✅ Checklist

### Local Setup
- [ ] Copy `.env.example` to `.env`
- [ ] Edit `.env` with actual values
- [ ] Verify `.env` is in `.gitignore`
- [ ] Test with `python manage.py migrate`
- [ ] Test with `python manage.py runserver`

### Render Setup
- [ ] Create Web Service
- [ ] Go to Environment tab
- [ ] Add all variables
- [ ] Use actual values (not placeholders)
- [ ] Deploy and test

### Security
- [ ] Never commit `.env` file
- [ ] Never commit credential JSON files
- [ ] Use `.gitignore` for all secrets
- [ ] Rotate exposed credentials
- [ ] Use strong SECRET_KEY

---

## 🔒 Security Best Practices

1. **Never commit secrets**
   - `.env` → `.gitignore`
   - `*.json` → `.gitignore`
   - `*.key` → `.gitignore`

2. **Use different values per environment**
   - Local: test keys
   - Production: real keys

3. **Rotate exposed credentials**
   - If accidentally committed
   - Generate new keys
   - Update all services

4. **Use strong SECRET_KEY**
   - Generate with Django
   - Change for each environment
   - Never reuse

5. **Limit access**
   - Only share `.env.example`
   - Keep `.env` locally only
   - Use Render dashboard for production

---

## 📚 File Structure

```
paeshift-recover/
├── .env.example          ← Template (commit to git)
├── .env                  ← Actual values (NOT in git)
├── .gitignore            ← Prevents committing secrets
├── google-credentials.json ← Local only (NOT in git)
├── payshift/
│   ├── settings.py       ← Loads from environment
│   ├── wsgi.py
│   └── urls.py
└── manage.py
```

---

## ✨ Summary

| Item | Local | Production |
|------|-------|------------|
| **Template** | `.env.example` | `.env.example` |
| **Actual File** | `.env` | Render Dashboard |
| **In Git** | ❌ NO | ❌ NO |
| **Credentials** | From `.env` | From environment |
| **Rotation** | Edit `.env` | Edit Render dashboard |

---

**Status**: ✅ COMPLETE GUIDE  
**Next**: Set up `.env` locally and configure Render

---

*For more details, see `ENV_SETUP_GUIDE.md` and `WHAT_WAS_REMOVED_AND_WHY.md`*

