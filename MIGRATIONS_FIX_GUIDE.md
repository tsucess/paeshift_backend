# 🔧 Migrations Fix Guide - Ensure Database Tables Are Created

**Error**: `no such table: accounts_customuser`

**Root Cause**: Migrations were not running during the Render build process

**Solution**: Created `build.sh` script to explicitly run migrations

---

## ✅ What Was Fixed

### **New Files Created**

1. **build.sh** - Custom build script that:
   - Installs dependencies
   - Runs migrations
   - Creates superuser if needed
   - Collects static files

### **Files Updated**

1. **render.yaml** - Now uses `bash build.sh` as buildCommand
2. **Procfile** - Already has release phase for migrations

---

## 📝 Build Process Flow

```
1. Render detects new commit
   ↓
2. Runs: bash build.sh
   ├─ pip install -r requirements.txt
   ├─ python manage.py migrate --noinput
   ├─ Create superuser (if needed)
   └─ python manage.py collectstatic --noinput
   ↓
3. Procfile release phase (if using Procfile)
   ├─ python manage.py migrate
   └─ python manage.py collectstatic --noinput
   ↓
4. Start application
   └─ gunicorn payshift.wsgi:application
```

---

## 🚀 How to Deploy

### **Step 1: Go to Render Dashboard**
```
https://dashboard.render.com
```

### **Step 2: Select paeshift-backend**

### **Step 3: Go to Deployments**

### **Step 4: Click "Deploy latest commit"**

### **Step 5: Monitor Build Logs**

Watch for these messages:
```
Step 1: Installing dependencies...
Step 2: Running Django migrations...
Step 3: Checking for superuser...
Step 4: Collecting static files...
Build process completed successfully!
```

### **Step 6: Verify**

- ✅ No database errors
- ✅ Login works
- ✅ Admin panel accessible
- ✅ API endpoints work

---

## 📊 What build.sh Does

### **1. Install Dependencies**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### **2. Run Migrations**
```bash
python manage.py migrate --noinput
```
Creates all database tables:
- `accounts_customuser`
- `jobs_job`
- `payment_payment`
- And all other app tables

### **3. Create Superuser**
```bash
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
END
```

Creates admin user if it doesn't exist:
- Username: `admin`
- Email: `admin@example.com`
- Password: `admin123`

### **4. Collect Static Files**
```bash
python manage.py collectstatic --noinput
```

---

## 🔍 Troubleshooting

### **If migrations still don't run:**

1. Check build logs in Render Dashboard
2. Look for error messages in build.sh output
3. Verify `FORCE_SQLITE=True` is set
4. Check that `build.sh` has execute permissions

### **If database is still empty:**

1. Go to Render Dashboard
2. Delete the service
3. Recreate it
4. Redeploy

### **If you need to reset database:**

1. Delete persistent disk in Render Dashboard
2. Redeploy service
3. Migrations will run and create fresh database

---

## 📝 Git Commits

- `b42f167` - Add build.sh script and update render.yaml to ensure migrations run properly

---

## 📚 Files Reference

| File | Purpose |
|------|---------|
| `build.sh` | Custom build script for Render |
| `render.yaml` | Render deployment configuration |
| `Procfile` | Heroku-style deployment config |
| `requirements.txt` | Python dependencies |
| `manage.py` | Django management script |

---

## ✨ Environment Variables

Make sure these are set in Render Dashboard:

| Variable | Value |
|----------|-------|
| `FORCE_SQLITE` | `True` |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SETTINGS_MODULE` | `payshift.settings` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,paeshift-backend-rwp3.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | `https://paeshift-frontend.onrender.com` |

---

## ✅ Status

✅ **MIGRATIONS FIX APPLIED**

The backend will now:
- Run migrations automatically during build
- Create all database tables
- Create superuser if needed
- Collect static files
- Start successfully

---

## 🎉 Next Steps

1. Go to Render Dashboard
2. Click "Deploy latest commit"
3. Wait for build to complete
4. Test login and API endpoints

**The database error should be completely fixed!** 🚀

