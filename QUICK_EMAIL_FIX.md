# ⚡ Quick Fix: Email Verification Not Sending

**Problem**: Users not receiving verification codes during signup

**Solution**: Add email environment variables to Render

---

## 🚀 What to Do (2 minutes)

### **1. Open Render Dashboard**
```
https://dashboard.render.com
```

### **2. Click paeshift-backend**

### **3. Go to Settings tab**

### **4. Scroll to Environment section**

### **5. Add These Variables**

```
EMAIL_BACKEND = django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST = smtp.gmail.com
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = onlypayshift@gmail.com
EMAIL_HOST_PASSWORD = wuxyvmldffuljocg
DEFAULT_FROM_EMAIL = Payshift <onlypayshift@gmail.com>
```

### **6. Click Save**

### **7. Go to Deployments tab**

### **8. Click "Deploy latest commit"**

### **9. Wait for build to complete**

### **10. Test**

Try signing up with a new email. You should receive the verification code!

---

## ✅ What This Fixes

- ✅ Verification codes sent to email
- ✅ Users can verify their accounts
- ✅ Signup process works
- ✅ Email notifications work

---

## 📊 Email Configuration

| Variable | Value |
|----------|-------|
| Backend | Gmail SMTP |
| Host | smtp.gmail.com |
| Port | 587 |
| TLS | Enabled |
| Email | onlypayshift@gmail.com |
| Password | wuxyvmldffuljocg |

---

## 🔍 Monitor

After redeployment:
- Services → paeshift-backend → Logs
- Look for "Email sent successfully" messages

---

## 🎉 Done!

Email verification will now work! Users can sign up and receive verification codes.

---

**That's it! Just add the environment variables and redeploy.** ✅

