# 🔧 Fix ALLOWED_HOSTS Error on Render

**Error**: `Invalid HTTP_HOST header: 'paeshift-backend-rwp3.onrender.com'. You may need to add 'paeshift-backend-rwp3.onrender.com' to ALLOWED_HOSTS.`

**Status**: ⚠️ CRITICAL - Must fix to deploy

---

## ✅ Solution: Add Environment Variable to Render Dashboard

### **Step 1: Go to Render Dashboard**

1. Open https://dashboard.render.com
2. Click on **paeshift-backend** service
3. Click on **Settings** tab (top right)

---

### **Step 2: Go to Environment Variables**

1. Scroll down to **Environment** section
2. Click **Add Environment Variable** button

---

### **Step 3: Add DJANGO_ALLOWED_HOSTS**

**Add this variable:**

| Key | Value |
|-----|-------|
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,paeshift-backend-rwp3.onrender.com` |

**Important**: 
- ❌ Do NOT include `https://` or `http://`
- ✅ Just the domain name
- ✅ Separate multiple hosts with commas (no spaces)

---

### **Step 4: Save and Redeploy**

1. Click **Save** button
2. Go to **Deployments** tab
3. Click **Deploy latest commit** button
4. Wait for build to complete
5. Check logs for success

---

## 📋 Complete Environment Variables Checklist

Make sure ALL of these are set in Render dashboard:

| Variable | Value | Required |
|----------|-------|----------|
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,paeshift-backend-rwp3.onrender.com` | ✅ YES |
| `DJANGO_DEBUG` | `False` | ✅ YES |
| `DJANGO_SETTINGS_MODULE` | `payshift.settings` | ✅ YES |
| `PYTHON_VERSION` | `3.13.4` | ✅ YES |
| `DATABASE_URL` | `postgresql://...` | ✅ YES |
| `DJANGO_SECRET_KEY` | `your-secret-key` | ✅ YES |
| `CORS_ALLOWED_ORIGINS` | `https://paeshift-frontend.onrender.com` | ✅ YES |
| `GOOGLE_MAPS_API_KEY` | `AIzaSyCiCDANDMScIcsm-d0QMDaAXFS8M-0GdLU` | ⏳ Optional |

---

## 🔍 How to Find Your Environment Variables Section

**Path in Render Dashboard:**
```
Dashboard 
  → paeshift-backend (service)
    → Settings (tab)
      → Environment (section)
        → Add Environment Variable (button)
```

---

## 📸 Visual Steps

1. **Dashboard Home**: https://dashboard.render.com
2. **Select Service**: Click "paeshift-backend"
3. **Settings Tab**: Click "Settings" at top
4. **Environment Section**: Scroll down to find "Environment"
5. **Add Variable**: Click "Add Environment Variable"
6. **Fill in**:
   - Key: `DJANGO_ALLOWED_HOSTS`
   - Value: `localhost,127.0.0.1,paeshift-backend-rwp3.onrender.com`
7. **Save**: Click "Save" button
8. **Redeploy**: Go to "Deployments" tab and click "Deploy latest commit"

---

## ✨ After Adding the Variable

Once you add `DJANGO_ALLOWED_HOSTS` and redeploy:

1. ✅ Error should disappear
2. ✅ Backend will accept requests
3. ✅ Frontend can connect to backend
4. ✅ API endpoints will work

---

## 🚀 Test the Fix

After redeployment, test with:

```bash
curl https://paeshift-backend-rwp3.onrender.com/api/health/
```

Should return: `200 OK` (not the ALLOWED_HOSTS error)

---

## 📝 Alternative: Update .env.example

The `.env.example` file has been updated with the correct value:

```env
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,paeshift-backend-rwp3.onrender.com
```

This is for reference only. **You must set it in Render dashboard** for production.

---

## ⚠️ Important Notes

- **Local Development**: Use `localhost,127.0.0.1`
- **Production (Render)**: Add `paeshift-backend-rwp3.onrender.com`
- **Multiple Domains**: Separate with commas, no spaces
- **No Protocol**: Don't include `http://` or `https://`

---

*For more information, see `RENDER_MANUAL_CONFIGURATION.md`*

