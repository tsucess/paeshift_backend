# 📋 Render Deployment Checklist

## ✅ Step 1: Backend Preparation (COMPLETE)

- [x] **requirements.txt** - 69 dependencies listed
- [x] **runtime.txt** - Python 3.12.0 specified
- [x] **Procfile** - Gunicorn startup command
- [x] **.env.example** - Environment variables documented
- [x] **Django Settings** - Production configuration ready
- [x] **Documentation** - 4 guides created

---

## ⏳ Step 2: Create Render Services

### 2.1 Create PostgreSQL Database
- [ ] Go to https://render.com/dashboard
- [ ] Click "New +" → "PostgreSQL"
- [ ] Fill in details:
  - [ ] Name: `paeshift-db`
  - [ ] Database: `paeshift`
  - [ ] User: `paeshift_user`
  - [ ] Region: Choose closest to you
  - [ ] Plan: Choose appropriate tier
- [ ] Copy **Internal Database URL**
- [ ] Save for later use

### 2.2 Create Web Service
- [ ] Go to Render Dashboard
- [ ] Click "New +" → "Web Service"
- [ ] Connect GitHub repository
- [ ] Fill in details:
  - [ ] Name: `paeshift-backend`
  - [ ] Environment: `Python 3`
  - [ ] Build Command: `pip install -r requirements.txt`
  - [ ] Start Command: `gunicorn payshift.wsgi:application`
  - [ ] Plan: Choose appropriate tier
- [ ] Click "Create Web Service"

### 2.3 Set Environment Variables
- [ ] Go to Web Service → Environment
- [ ] Add all variables from `.env.example`:

**Critical Variables:**
- [ ] `DJANGO_SECRET_KEY` - Generate strong key
- [ ] `DJANGO_DEBUG=False`
- [ ] `DJANGO_ALLOWED_HOSTS=your-backend.onrender.com`
- [ ] `DATABASE_URL` - From PostgreSQL service
- [ ] `CORS_ALLOWED_ORIGINS=https://your-frontend.onrender.com`

**Optional but Recommended:**
- [ ] `REDIS_URL` - If using Redis
- [ ] `SENTRY_DSN` - If using Sentry
- [ ] `GOOGLE_MAPS_API_KEY` - For geolocation

**Payment & Email:**
- [ ] `PAYSTACK_SECRET_KEY`
- [ ] `PAYSTACK_PUBLIC_KEY`
- [ ] `FLUTTERWAVE_SECRET_KEY`
- [ ] `FLUTTERWAVE_PUBLIC_KEY`
- [ ] `EMAIL_HOST_USER`
- [ ] `EMAIL_HOST_PASSWORD`

**AWS S3 (if using):**
- [ ] `AWS_ACCESS_KEY_ID`
- [ ] `AWS_SECRET_ACCESS_KEY`
- [ ] `AWS_STORAGE_BUCKET_NAME`
- [ ] `AWS_S3_REGION_NAME`

---

## ⏳ Step 3: Deploy & Initialize

### 3.1 Deploy
- [ ] Render automatically deploys on push
- [ ] Or manually deploy from Render dashboard
- [ ] Check deployment logs for errors

### 3.2 Run Migrations
- [ ] Go to Web Service → Shell
- [ ] Run: `python manage.py migrate`
- [ ] Verify no errors

### 3.3 Create Superuser
- [ ] In Shell, run: `python manage.py createsuperuser`
- [ ] Follow prompts to create admin account
- [ ] Save credentials securely

### 3.4 Collect Static Files
- [ ] In Shell, run: `python manage.py collectstatic --noinput`
- [ ] Verify no errors

---

## ⏳ Step 4: Test Backend

### 4.1 Test API Endpoints
- [ ] Visit: `https://your-backend.onrender.com/api/`
- [ ] Check if API is responding
- [ ] Test authentication endpoints

### 4.2 Check Logs
- [ ] Go to Web Service → Logs
- [ ] Look for any errors
- [ ] Verify database connection successful

### 4.3 Test Database
- [ ] Go to Shell
- [ ] Run: `python manage.py shell`
- [ ] Test: `from accounts.models import CustomUser; CustomUser.objects.count()`
- [ ] Should return a number (not error)

---

## ⏳ Step 5: Frontend Preparation

### 5.1 Update Frontend API URL
- [ ] Update API base URL to: `https://your-backend.onrender.com`
- [ ] Update CORS origin in backend if needed
- [ ] Test frontend connection to backend

### 5.2 Deploy Frontend
- [ ] Follow Step 1 for frontend (requirements, build config)
- [ ] Create Render Web Service for frontend
- [ ] Set environment variables
- [ ] Deploy

---

## 🔐 Security Checklist

- [ ] `DJANGO_SECRET_KEY` is strong and unique
- [ ] `DJANGO_DEBUG=False` in production
- [ ] All secrets in environment variables (not in code)
- [ ] `.env` file is in `.gitignore`
- [ ] HTTPS enabled (Render does this automatically)
- [ ] CORS_ALLOWED_ORIGINS set correctly
- [ ] CSRF_TRUSTED_ORIGINS set correctly
- [ ] Database password is strong
- [ ] Admin credentials saved securely

---

## 📊 Verification Checklist

### Backend
- [ ] Web Service is running (green status)
- [ ] Database is connected
- [ ] Migrations completed successfully
- [ ] API endpoints responding
- [ ] Admin panel accessible
- [ ] Logs show no errors

### Frontend
- [ ] Frontend deployed successfully
- [ ] Can connect to backend API
- [ ] Authentication working
- [ ] No CORS errors in console

### Integration
- [ ] Frontend can fetch data from backend
- [ ] Authentication tokens working
- [ ] Payment processing configured
- [ ] Email notifications working
- [ ] WebSockets connected (if applicable)

---

## 🆘 Troubleshooting

### 502 Bad Gateway
```
✓ Check logs in Render dashboard
✓ Verify all environment variables set
✓ Ensure migrations have run
✓ Check database connection
```

### Database Connection Error
```
✓ Verify DATABASE_URL is correct
✓ Check database is running
✓ Ensure IP whitelist allows Render
✓ Test connection in Shell
```

### CORS Errors
```
✓ Update CORS_ALLOWED_ORIGINS with frontend URL
✓ Verify frontend URL is correct
✓ Check CSRF_TRUSTED_ORIGINS
✓ Clear browser cache
```

### Static Files Not Loading
```
✓ Run: python manage.py collectstatic
✓ Check STATIC_ROOT and STATIC_URL
✓ Verify WhiteNoise is installed
```

### Email Not Sending
```
✓ Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
✓ Check Gmail app password is correct
✓ Verify 2FA is enabled on Gmail
✓ Check email logs
```

---

## 📞 Useful Commands

### Generate Django Secret Key
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Test Database Connection
```bash
python manage.py dbshell
```

### Check Installed Packages
```bash
pip list
```

### Run Tests
```bash
pytest
```

---

## 📚 Documentation Files

- `RENDER_DEPLOYMENT_SETUP.md` - Detailed setup guide
- `RENDER_QUICK_START.md` - Quick reference
- `STEP_1_COMPLETION_SUMMARY.md` - Summary of changes
- `DEPLOYMENT_STEP_1_COMPLETE.md` - Completion details
- `RENDER_DEPLOYMENT_CHECKLIST.md` - This file

---

## 📈 Progress Tracking

| Step | Task | Status | Date |
|------|------|--------|------|
| 1 | Backend Preparation | ✅ Complete | 2025-10-21 |
| 2 | Create Render Services | ⏳ Pending | - |
| 3 | Deploy & Initialize | ⏳ Pending | - |
| 4 | Test Backend | ⏳ Pending | - |
| 5 | Frontend Preparation | ⏳ Pending | - |
| 6 | Deploy Frontend | ⏳ Pending | - |
| 7 | Integration Testing | ⏳ Pending | - |

---

**Last Updated**: 2025-10-21  
**Backend Status**: ✅ Ready for Step 2  
**Next Action**: Create Render services

