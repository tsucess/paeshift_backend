# 🔐 Environment Variables Setup Guide

**Status**: ✅ CORRECT APPROACH  
**Date**: 2025-10-21

---

## ✅ You're Absolutely Right!

Credentials **should be in `.env` files**, NOT committed as JSON files. The issue we fixed was exactly that - a JSON credential file was accidentally committed to git.

---

## 📋 Proper Environment Variable Setup

### Local Development

**1. Create `.env` file** (NEVER commit this)
```bash
cp .env.example .env
```

**2. Edit `.env` with your actual values**
```
DJANGO_SECRET_KEY=your-actual-secret-key
DJANGO_DEBUG=True
DATABASE_URL=postgresql://user:password@localhost:5432/paeshift
PAYSTACK_SECRET_KEY=sk_test_xxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxx
# ... etc
```

**3. Add to `.gitignore`** (already done)
```
.env
.env.local
.env.*.local
```

### Production (Render)

**1. Set environment variables in Render Dashboard**
- Go to Service → Environment
- Add each variable individually
- Render will inject them at runtime

**2. Never commit `.env` to git**
- Use `.env.example` as template
- Render reads from dashboard, not from files

---

## 🔑 Environment Variable Names

### Django Core
```
DJANGO_SECRET_KEY          # Generate with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
DJANGO_DEBUG               # False in production
DJANGO_ALLOWED_HOSTS       # your-backend.onrender.com
```

### Database
```
DATABASE_URL               # postgresql://user:password@host:port/db
```

### CORS
```
CORS_ALLOWED_ORIGINS       # https://your-frontend.onrender.com
```

### AWS S3 (Media Storage)
```
AWS_ACCESS_KEY_ID          # From AWS IAM
AWS_SECRET_ACCESS_KEY      # From AWS IAM
AWS_STORAGE_BUCKET_NAME    # Your S3 bucket name
AWS_S3_REGION_NAME         # us-west-2, etc
```

### Payment Processing
```
PAYSTACK_SECRET_KEY        # From Paystack dashboard
PAYSTACK_PUBLIC_KEY        # From Paystack dashboard
FLUTTERWAVE_SECRET_KEY     # From Flutterwave dashboard
FLUTTERWAVE_PUBLIC_KEY     # From Flutterwave dashboard
```

### Email (Gmail)
```
EMAIL_HOST_USER            # your-email@gmail.com
EMAIL_HOST_PASSWORD        # Gmail app password (NOT your regular password)
```

### Redis (Optional)
```
REDIS_URL                  # redis://host:port/db
```

### Celery (Optional)
```
CELERY_BROKER_URL          # redis://host:port/1
CELERY_RESULT_BACKEND      # redis://host:port/2
```

### Sentry (Optional)
```
SENTRY_DSN                 # From Sentry dashboard
```

### Google Maps (Optional)
```
GOOGLE_MAPS_API_KEY        # From Google Cloud Console
```

---

## 🚀 Setup Steps

### Step 1: Local Development
```bash
# Copy template
cp .env.example .env

# Edit with your values
nano .env  # or use your editor

# Test it works
python manage.py migrate
python manage.py runserver
```

### Step 2: Render Deployment
```bash
# 1. Go to Render Dashboard
# 2. Select your Web Service
# 3. Go to "Environment" tab
# 4. Add each variable from .env.example

# Variables to add:
DJANGO_SECRET_KEY=<generate-new-key>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-backend.onrender.com
DATABASE_URL=<from-render-postgres>
CORS_ALLOWED_ORIGINS=https://your-frontend.onrender.com
# ... and all others
```

### Step 3: Verify
```bash
# In Render Shell:
python manage.py shell
import os
print(os.getenv('DJANGO_SECRET_KEY'))  # Should print your key
```

---

## 📝 What NOT to Do

❌ **DON'T** commit `.env` file
```bash
# This is already in .gitignore, but never do:
git add .env
git commit -m "Add env file"
```

❌ **DON'T** commit credential JSON files
```bash
# This is what we fixed:
# godmode/report/static/rfm360-c455b2faa813.json  ← WRONG!
```

❌ **DON'T** hardcode secrets in code
```python
# WRONG:
SECRET_KEY = "sk_test_xxxxx"
DATABASE_PASSWORD = "mypassword"

# RIGHT:
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
```

---

## ✅ What TO Do

✅ **DO** use `.env.example` as template
```bash
# .env.example is committed to git
# It shows what variables are needed
# But with placeholder values
```

✅ **DO** use environment variables in code
```python
import os
from dotenv import load_dotenv

load_dotenv()  # Load from .env file

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'
DATABASE_URL = os.getenv('DATABASE_URL')
```

✅ **DO** set variables in Render Dashboard
```
Service → Environment → Add Variable
```

✅ **DO** use `.gitignore` to prevent commits
```
.env
.env.local
.env.*.local
*.json  # Credential files
*.key
*.pem
```

---

## 🔄 Workflow Summary

### Local Development
```
.env.example (in git) → Copy to .env (not in git) → Edit with real values → Use locally
```

### Production (Render)
```
.env.example (reference) → Set in Render Dashboard → Render injects at runtime
```

### Never in Git
```
.env (local)
*.json (credentials)
*.key (private keys)
*.pem (certificates)
```

---

## 🎯 For Google Cloud Credentials

If you need Google Cloud credentials (like the one we removed):

### ❌ WRONG WAY (What we fixed)
```
godmode/report/static/rfm360-c455b2faa813.json  ← Committed to git (SECURITY RISK!)
```

### ✅ RIGHT WAY
```
# 1. Download JSON from Google Cloud Console
# 2. Save locally as: google-credentials.json (in .gitignore)
# 3. Set environment variable:
GOOGLE_CREDENTIALS_PATH=/path/to/google-credentials.json

# 4. Or encode as base64 and use env var:
GOOGLE_CREDENTIALS_JSON=<base64-encoded-json>

# 5. In code:
import json
import base64
import os

if os.getenv('GOOGLE_CREDENTIALS_JSON'):
    creds_json = base64.b64decode(os.getenv('GOOGLE_CREDENTIALS_JSON'))
    creds = json.loads(creds_json)
else:
    creds = json.load(open(os.getenv('GOOGLE_CREDENTIALS_PATH')))
```

---

## 📋 Checklist

### Local Setup
- [ ] Copy `.env.example` to `.env`
- [ ] Edit `.env` with your values
- [ ] Verify `.env` is in `.gitignore`
- [ ] Test with `python manage.py migrate`

### Render Setup
- [ ] Create Web Service on Render
- [ ] Go to Environment tab
- [ ] Add all variables from `.env.example`
- [ ] Use actual values (not placeholders)
- [ ] Deploy and test

### Security
- [ ] Never commit `.env` file
- [ ] Never commit credential JSON files
- [ ] Use `.gitignore` for all secrets
- [ ] Rotate exposed credentials
- [ ] Use strong SECRET_KEY

---

## 🔐 Security Best Practices

1. **Use `.env.example` as template**
   - Shows what variables are needed
   - Uses placeholder values
   - Safe to commit to git

2. **Never commit actual `.env` file**
   - Contains real credentials
   - Add to `.gitignore`
   - Keep locally only

3. **Use environment variables everywhere**
   - In local development: from `.env` file
   - In production: from Render dashboard
   - In code: `os.getenv('VARIABLE_NAME')`

4. **Rotate exposed credentials**
   - If accidentally committed
   - Generate new keys
   - Update all services

5. **Use strong SECRET_KEY**
   - Generate with Django utility
   - Change for each environment
   - Never reuse across projects

---

## 📚 Django Settings Example

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Django Settings
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost').split(',')

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DATABASE_NAME', 'paeshift'),
        'USER': os.getenv('DATABASE_USER', 'postgres'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD', ''),
        'HOST': os.getenv('DATABASE_HOST', 'localhost'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}

# Or use DATABASE_URL
import dj_database_url
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600
    )
}

# CORS
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')

# AWS S3
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
```

---

## ✨ Summary

| Aspect | Local | Production |
|--------|-------|------------|
| **Template** | `.env.example` | `.env.example` |
| **Actual File** | `.env` (local only) | Render Dashboard |
| **In Git** | ❌ NO | ❌ NO |
| **Committed** | ❌ NO | ❌ NO |
| **Loaded From** | `.env` file | Environment |

---

**Status**: ✅ CORRECT APPROACH CONFIRMED  
**Next**: Set up `.env` locally and configure Render dashboard

---

*For more info, see Django documentation on environment variables and Render documentation on environment configuration.*

