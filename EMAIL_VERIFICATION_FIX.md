# 📧 Email Verification Fix - OTP Not Sending

**Problem**: Verification code not being sent to email during signup

**Root Cause**: Email environment variables not configured in Render dashboard

**Solution**: Add email configuration to Render environment variables

---

## 🔍 What's Happening

When a user signs up:
1. ✅ User account is created
2. ✅ OTP code is generated
3. ❌ Email is NOT sent (EMAIL_HOST_PASSWORD is empty)
4. ❌ User can't verify email

---

## 🔧 How to Fix

### **Step 1: Go to Render Dashboard**
```
https://dashboard.render.com
```

### **Step 2: Select paeshift-backend**

### **Step 3: Go to Settings tab**

### **Step 4: Scroll to Environment section**

### **Step 5: Add Email Configuration Variables**

Add these environment variables:

| Key | Value |
|-----|-------|
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | `smtp.gmail.com` |
| `EMAIL_PORT` | `587` |
| `EMAIL_USE_TLS` | `True` |
| `EMAIL_HOST_USER` | `onlypayshift@gmail.com` |
| `EMAIL_HOST_PASSWORD` | `wuxyvmldffuljocg` |
| `DEFAULT_FROM_EMAIL` | `Payshift <onlypayshift@gmail.com>` |

<!-- fcyqdvjcxpfgbcab -->
### **Step 6: Save**

Click "Save" button

### **Step 7: Redeploy**

Go to Deployments tab and click "Deploy latest commit"

---

## 📝 Email Configuration Details

### **Current Configuration (in settings.py)**

```python
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'onlypayshift@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')  # ← EMPTY!
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Payshift <onlypayshift@gmail.com>')
```

### **The Issue**

`EMAIL_HOST_PASSWORD` defaults to empty string `''` if not set in environment variables.

When Django tries to send email with empty password, it fails silently.

---

## 🔐 Gmail App Password

The email uses Gmail SMTP with an app-specific password:

- **Email**: `onlypayshift@gmail.com`
- **App Password**: `wuxyvmldffuljocg`

This is NOT your regular Gmail password. It's a special password for app access.

---

## 📧 Email Sending Flow

```
1. User signs up
   ↓
2. Account created
   ↓
3. OTP generated (6-digit code)
   ↓
4. send_otp_email() called
   ↓
5. Django sends email via Gmail SMTP
   ├─ Host: smtp.gmail.com
   ├─ Port: 587
   ├─ TLS: Enabled
   ├─ User: onlypayshift@gmail.com
   ├─ Password: wuxyvmldffuljocg
   └─ To: user's email
   ↓
6. Email delivered to user
   ↓
7. User receives verification code
```

---

## 🧪 Test Email Sending

After adding environment variables and redeploying:

1. Go to frontend: https://paeshift-frontend.onrender.com
2. Click "Sign Up"
3. Enter email and password
4. Click "Sign Up" button
5. Check email inbox for verification code
6. Enter code to verify

---

## 📊 Email Configuration in Code

### **accounts/utils.py** - send_otp_email()

```python
def send_otp_email(user, otp_code):
    """Send OTP via email with beautiful HTML template"""
    try:
        logger.info(f"📧 Starting email send process for {user.email}")
        subject = "Verify Your Email - Payshift"
        
        # HTML email template
        html_message = f"""
        <html>
            <body>
                <h2>Welcome to Payshift!</h2>
                <p>Your verification code is: <strong>{otp_code}</strong></p>
                <p>This code will expire in 10 minutes.</p>
            </body>
        </html>
        """
        
        # Send email
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send()
        
        logger.info(f"✅ Email sent successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send OTP email: {str(e)}")
        return False
```

### **accounts/otp_api.py** - request_otp()

```python
@otp_router.post("/request")
def request_otp(request, payload: OTPRequestSchema):
    """Request an OTP for verification"""
    
    # Generate OTP
    otp_code = generate_otp()
    
    # Send OTP via email
    send_otp_email(user, otp_code)
    
    return 200, {"message": "OTP sent successfully"}
```

---

## ✅ Verification Process

After email is sent:

1. **User receives email** with 6-digit code
2. **User enters code** in verification form
3. **Backend verifies code** (must match and not expired)
4. **Account activated** if code is correct
5. **User can login**

---

## 🔍 Troubleshooting

### **If email still not sending:**

1. Check Render logs: Services → paeshift-backend → Logs
2. Look for email error messages
3. Verify all email variables are set correctly
4. Check Gmail account hasn't blocked the app

### **If email is blocked:**

1. Go to Gmail account settings
2. Check "Less secure app access" is enabled
3. Or use Gmail app password (recommended)

### **If code expires:**

OTP expires after 10 minutes. User must request new code.

---

## 📝 Environment Variables Checklist

- [ ] `EMAIL_BACKEND` = `django.core.mail.backends.smtp.EmailBackend`
- [ ] `EMAIL_HOST` = `smtp.gmail.com`
- [ ] `EMAIL_PORT` = `587`
- [ ] `EMAIL_USE_TLS` = `True`
- [ ] `EMAIL_HOST_USER` = `onlypayshift@gmail.com`
- [ ] `EMAIL_HOST_PASSWORD` = `wuxyvmldffuljocg`
- [ ] `DEFAULT_FROM_EMAIL` = `Payshift <onlypayshift@gmail.com>`

---

## ✨ Status

❌ **EMAIL VERIFICATION NOT WORKING** (before fix)

✅ **EMAIL VERIFICATION WILL WORK** (after adding env vars)

---

## 🎯 Next Steps

1. Go to Render Dashboard
2. Add email environment variables
3. Redeploy backend
4. Test signup with email verification
5. Verify code is received

---

## 📚 Related Files

| File | Purpose |
|------|---------|
| `accounts/utils.py` | Email sending functions |
| `accounts/otp_api.py` | OTP request/verify logic |
| `accounts/api.py` | Signup endpoint |
| `payshift/settings.py` | Email configuration |

---

*After adding these environment variables, email verification will work!* ✅

