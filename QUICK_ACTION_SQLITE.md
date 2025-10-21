# ⚡ Quick Action: Fix Database Error

**Error**: `no such table: accounts_customuser`

**Solution**: Migrations need to run on Render

---

## 🚀 What to Do

### **Step 1: Go to Render Dashboard**

```
https://dashboard.render.com
```

### **Step 2: Select paeshift-backend**

Click on the paeshift-backend service

### **Step 3: Go to Deployments**

Click the "Deployments" tab

### **Step 4: Redeploy**

Click "Deploy latest commit" button

### **Step 5: Wait for Build**

Monitor the build logs. You should see:
```
Running migrations...
Migrations completed successfully
Application startup complete
```

### **Step 6: Test**

Try logging in from the frontend. Should work now!

---

## ✅ What Changed

- ✅ `render.yaml` - Added SQLite configuration
- ✅ `Procfile` - Added migration release phase
- ✅ Environment variables - Set `FORCE_SQLITE=True`
- ✅ Persistent disk - Database survives redeployments

---

## 📊 Build Process

When you redeploy, Render will:

1. Install dependencies
2. **Run migrations** ← Creates database tables
3. Collect static files
4. Start the application

---

## 🔍 Monitor Build

In Render Dashboard:
- Services → paeshift-backend → Deployments
- Click on the latest deployment
- Watch the build logs in real-time

---

## ✨ After Deployment

- ✅ Database tables created
- ✅ Login works
- ✅ API endpoints work
- ✅ Frontend can connect

---

## 📝 Git Commits

Latest changes pushed:
- Commit: `6a14a12`
- Message: "Configure SQLite database with persistent storage and automatic migrations for Render"

---

**That's it! Just redeploy and the database error will be fixed.** 🎉

