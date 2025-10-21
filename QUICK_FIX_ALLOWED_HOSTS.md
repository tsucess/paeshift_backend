# ⚡ QUICK FIX: ALLOWED_HOSTS Error

**Error**: `Invalid HTTP_HOST header: 'paeshift-backend-rwp3.onrender.com'. You may need to add 'paeshift-backend-rwp3.onrender.com' to ALLOWED_HOSTS.`

---

## 🚀 Quick Fix (2 minutes)

### **1. Open Render Dashboard**
```
https://dashboard.render.com
```

### **2. Click on paeshift-backend service**

### **3. Click Settings tab**

### **4. Scroll to Environment section**

### **5. Click "Add Environment Variable"**

### **6. Add this variable:**

```
Key:   DJANGO_ALLOWED_HOSTS
Value: localhost,127.0.0.1,paeshift-backend-rwp3.onrender.com
```

### **7. Click Save**

### **8. Go to Deployments tab**

### **9. Click "Deploy latest commit"**

### **10. Wait for build to complete ✅**

---

## ✅ Done!

The error should be fixed. Your backend will now accept requests from the Render domain.

---

## 📝 Important Notes

- ❌ Do NOT include `https://` or `http://`
- ✅ Just the domain name
- ✅ Separate multiple hosts with commas (no spaces)
- ✅ After saving, you MUST redeploy

---

## 🔗 Reference

For detailed information, see: `FIX_ALLOWED_HOSTS_ERROR.md`

