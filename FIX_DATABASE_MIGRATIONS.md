# 🔧 Fix Database Migrations Error

**Error**: `no such table: accounts_customuser`

**Status**: ⚠️ CRITICAL - Database tables not created

**Root Cause**: Django migrations haven't been run on the production database

---

## 🎯 Problem

The backend is deployed but the database tables don't exist because:

1. ❌ Migrations weren't run during build
2. ❌ Backend is using SQLite instead of PostgreSQL
3. ❌ DATABASE_URL environment variable not set in Render

---

## ✅ Solution: Run Migrations on Render

### **Option 1: Run Migrations via Render Console (Recommended)**

1. **Go to Render Dashboard**: https://dashboard.render.com
2. **Select Service**: Click "paeshift-backend"
3. **Go to Shell**: Click "Shell" tab
4. **Run migrations**:
   ```bash
   python manage.py migrate
   ```
5. **Create superuser** (optional):
   ```bash
   python manage.py createsuperuser
   ```

---

### **Option 2: Set DATABASE_URL Environment Variable**

If you have a PostgreSQL database, add this to Render:

1. **Go to Settings**: paeshift-backend → Settings
2. **Add Environment Variable**:
   ```
   Key:   DATABASE_URL
   Value: postgresql://username:password@host:port/database
   ```
3. **Redeploy**: Go to Deployments and click "Deploy latest commit"
4. **Migrations will run automatically** during build

---

## 📋 Environment Variables Needed

Make sure these are set in Render dashboard:

| Variable | Value | Status |
|----------|-------|--------|
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,paeshift-backend-rwp3.onrender.com` | ✅ Required |
| `DJANGO_DEBUG` | `False` | ✅ Required |
| `DJANGO_SETTINGS_MODULE` | `payshift.settings` | ✅ Required |
| `PYTHON_VERSION` | `3.13.4` | ✅ Required |
| `DATABASE_URL` | `postgresql://...` | ⏳ If using PostgreSQL |
| `DJANGO_SECRET_KEY` | `your-secret-key` | ✅ Required |
| `CORS_ALLOWED_ORIGINS` | `https://paeshift-frontend.onrender.com` | ✅ Required |

---

## 🚀 Step-by-Step: Run Migrations via Shell

### **Step 1: Open Render Shell**

1. Go to https://dashboard.render.com
2. Click "paeshift-backend" service
3. Click "Shell" tab at the top

### **Step 2: Run Migrations**

```bash
python manage.py migrate
```

**Expected output:**
```
Operations to perform:
  Apply all migrations: admin, auth, accounts, ...
Running migrations:
  Applying accounts.0001_initial... OK
  Applying accounts.0002_customuser_... OK
  ...
```

### **Step 3: Verify Tables Created**

```bash
python manage.py dbshell
```

Then run:
```sql
.tables
```

Should show: `accounts_customuser` and other tables

### **Step 4: Exit Shell**

```bash
.quit
```

---

## 🔍 Troubleshooting

### **If migrations fail:**

1. **Check database connection**:
   ```bash
   python manage.py dbshell
   ```

2. **Check migration files**:
   ```bash
   python manage.py showmigrations
   ```

3. **Check for errors**:
   ```bash
   python manage.py migrate --verbosity 3
   ```

### **If still using SQLite:**

The backend is falling back to SQLite because:
- `DATABASE_URL` is not set
- `smart_db_config` module is not available

**Solution**: Set `DATABASE_URL` environment variable in Render

---

## 📝 Database Configuration

### **Current Configuration** (settings.py)

```python
FORCE_SQLITE = os.getenv('FORCE_SQLITE', 'False').lower() == 'true'
if FORCE_SQLITE:
    # Use SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # Try to use smart_db_config or fallback to SQLite
    try:
        from smart_db_config import get_database_settings
        DATABASES = {'default': get_database_settings()}
    except ImportError:
        # Fallback to SQLite
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
```

### **To Use PostgreSQL:**

Set `DATABASE_URL` environment variable:
```
postgresql://username:password@host:port/database
```

---

## ✨ After Running Migrations

Once migrations are complete:

1. ✅ All tables will be created
2. ✅ Login will work
3. ✅ API endpoints will work
4. ✅ Frontend can connect to backend

---

## 🧪 Test the Fix

After running migrations:

```bash
# Test login endpoint
curl -X POST https://paeshift-backend-rwp3.onrender.com/accountsapp/login-simple \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

Should return: `200 OK` (not the "no such table" error)

---

## 📚 Related Documentation

| Document | Purpose |
|----------|---------|
| `FIX_ALLOWED_HOSTS_ERROR.md` | Backend ALLOWED_HOSTS fix |
| `RENDER_MANUAL_CONFIGURATION.md` | Manual Render setup |
| `DEPLOYMENT_FIXES_SUMMARY.md` | Complete deployment summary |

---

*For more information, see the related documentation files.*

