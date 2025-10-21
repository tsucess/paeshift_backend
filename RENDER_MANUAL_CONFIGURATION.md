# 🔧 Render Manual Configuration Guide

**Date**: 2025-10-21  
**Status**: ⚠️ IMPORTANT - Follow these steps if render.yaml is not being detected

---

## 🐛 Problem

Render is showing error:
```
ModuleNotFoundError: No module named 'your_application'
==> Running 'gunicorn your_application.wsgi'
```

This means Render is using a **default/placeholder command** instead of the correct one.

---

## ✅ Solution: Manual Configuration in Render Dashboard

### **Step 1: Go to Render Dashboard**

1. Open https://dashboard.render.com
2. Click on **paeshift-backend** service
3. Go to **Settings** tab

---

### **Step 2: Update Build Command**

**Location**: Settings → Build & Deploy → Build Command

**Current (Wrong)**:
```
(empty or default)
```

**Change to**:
```bash
pip install -r requirements.txt && python manage.py migrate
```

---

### **Step 3: Update Start Command**

**Location**: Settings → Build & Deploy → Start Command

**Current (Wrong)**:
```
gunicorn your_application.wsgi
```

**Change to**:
```bash
gunicorn payshift.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 60
```

---

### **Step 4: Verify Environment Variables**

**Location**: Settings → Environment

Make sure these are set:

| Key | Value |
|-----|-------|
| `DJANGO_SETTINGS_MODULE` | `payshift.settings` |
| `DJANGO_DEBUG` | `False` |
| `PYTHON_VERSION` | `3.13.4` |
| `DATABASE_URL` | `postgresql://...` |
| `DJANGO_SECRET_KEY` | `your-secret-key` |
| `DJANGO_ALLOWED_HOSTS` | `paeshift-backend-rwp3.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | `https://paeshift-frontend.onrender.com` |

---

### **Step 5: Save and Redeploy**

1. Click **Save** button
2. Go to **Deployments** tab
3. Click **Deploy latest commit** button
4. Monitor the build in the logs

---

## 📋 Complete Configuration Checklist

- [ ] Build Command updated
- [ ] Start Command updated
- [ ] Environment variables verified
- [ ] Deployment triggered
- [ ] Build logs show success
- [ ] Service is running

---

## 🔍 Troubleshooting

### If build still fails:

1. **Check logs**: Deployments → View logs
2. **Look for errors**: Search for "error" or "failed"
3. **Common issues**:
   - Missing environment variables
   - Database connection failed
   - Python version mismatch
   - Missing dependencies

### If service won't start:

1. **Check Start Command**: Should be exactly:
   ```
   gunicorn payshift.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 60
   ```

2. **Check DJANGO_SETTINGS_MODULE**: Should be `payshift.settings`

3. **Check DJANGO_DEBUG**: Should be `False` for production

---

## 📝 Files Reference

| File | Purpose |
|------|---------|
| `Procfile` | Backup configuration (Render may not use this) |
| `render.yaml` | Primary configuration (if Render detects it) |
| `.env.example` | Template for environment variables |

---

## 🚀 After Configuration

Once the service is running:

1. **Test the API**:
   ```bash
   curl https://paeshift-backend-rwp3.onrender.com/api/health/
   ```

2. **Check logs**:
   - Deployments → View logs
   - Look for "Application startup complete"

3. **Connect frontend**:
   - Set `VITE_API_BASE_URL=https://paeshift-backend-rwp3.onrender.com`
   - Redeploy frontend

---

## ✨ Status

After following these steps, your backend should:
- ✅ Build successfully
- ✅ Start without errors
- ✅ Accept API requests
- ✅ Connect to database
- ✅ Serve frontend requests

---

*For more information, see `RENDER_DEPLOYMENT_FIX.md`*

