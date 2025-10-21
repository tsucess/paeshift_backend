# ⚡ Quick Redeploy - Fix Database Tables

**Problem**: Database tables missing (`no such table: accounts_customuser`)

**Solution**: Redeploy with new build.sh script

---

## 🚀 What to Do (2 minutes)

### **1. Open Render Dashboard**
```
https://dashboard.render.com
```

### **2. Click paeshift-backend**

### **3. Go to Deployments tab**

### **4. Click "Deploy latest commit"**

### **5. Wait for Build**

Monitor the logs. You should see:
```
Step 1: Installing dependencies...
Step 2: Running Django migrations...
Step 3: Checking for superuser...
Step 4: Collecting static files...
Build process completed successfully!
```

### **6. Test**

Try logging in. Should work now!

---

## ✅ What Changed

- ✅ Created `build.sh` - Custom build script
- ✅ Updated `render.yaml` - Uses build.sh
- ✅ Procfile - Already has release phase
- ✅ Migrations will run automatically

---

## 📊 Build Process

When you redeploy:

1. **Install dependencies** - pip install
2. **Run migrations** - Creates database tables
3. **Create superuser** - If needed
4. **Collect static files** - For admin panel
5. **Start application** - gunicorn

---

## 🔍 Monitor Build

In Render Dashboard:
- Services → paeshift-backend → Deployments
- Click latest deployment
- Watch build logs in real-time

---

## ✨ After Deployment

- ✅ All database tables created
- ✅ Login works
- ✅ Admin panel works
- ✅ API endpoints work
- ✅ No more database errors

---

## 📝 Git Commits

Latest changes:
- `b42f167` - Add build.sh script
- `0d7addb` - Add migrations fix guide

---

**That's it! Just redeploy and the database error will be fixed.** 🎉

