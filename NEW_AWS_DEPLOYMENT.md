# 🚀 Payshift - Deploy to New AWS Account Guide

## 🎯 Complete Setup for Email OTP Verification System

This guide covers deploying Payshift with full email OTP verification to a **new AWS account**.

## 📋 Prerequisites Checklist

### AWS Account Setup:
- [ ] New AWS account created and verified
- [ ] Payment method added and verified
- [ ] AWS CLI installed on your machine
- [ ] EB CLI installed (`pip install awsebcli`)

### Email Configuration:
- [ ] Gmail account: `onlypayshift@gmail.com` accessible
- [ ] 2-Factor Authentication enabled on Gmail
- [ ] Gmail App Password generated (16 characters)

### Application Files:
- [ ] Complete Payshift codebase
- [ ] All dependencies in requirements.txt
- [ ] Environment variables configured

## 🔧 Step 1: AWS Account Configuration

### 1.1 Create IAM User for Deployment
```bash
# In AWS Console:
# 1. Go to IAM > Users > Create User
# 2. Username: payshift-deployer
# 3. Attach policies:
#    - AWSElasticBeanstalkFullAccess
#    - AmazonEC2FullAccess
#    - AmazonS3FullAccess
#    - IAMReadOnlyAccess
# 4. Create access keys for CLI
```

### 1.2 Configure AWS CLI
```bash
# Install AWS CLI if not installed
# Download from: https://aws.amazon.com/cli/

# Configure with new account
aws configure
# Enter:
# AWS Access Key ID: [Your new account access key]
# AWS Secret Access Key: [Your new account secret key]
# Default region name: us-east-1
# Default output format: json

# Verify configuration
aws sts get-caller-identity
```

## 📧 Step 2: Email Configuration

### 2.1 Gmail App Password Setup
```bash
# 1. Go to: https://myaccount.google.com/security
# 2. Enable 2-Step Verification (if not enabled)
# 3. Go to "App passwords" section
# 4. Select app: Mail
# 5. Select device: Other (Custom name)
# 6. Name it: "Payshift Production"
# 7. Copy the 16-character password (e.g., "abcd efgh ijkl mnop")
```

### 2.2 Create Environment File
```bash
# Copy the example file
cp .env.example .env

# Edit .env file with your Gmail App Password:
EMAIL_HOST_PASSWORD=abcdefghijklmnop  # Your 16-char password (no spaces)
EMAIL_HOST_USER=onlypayshift@gmail.com
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEBUG=False
```

## 🏗️ Step 3: Application Preparation

### 3.1 Install Dependencies
```bash
# Activate virtual environment
eb-env-py310\Scripts\activate

# Install all dependencies
pip install -r requirements.txt

# Verify Django works
python manage.py check
```

### 3.2 Collect Static Files
```bash
# Collect all static files for production
python manage.py collectstatic --noinput

# Verify static files are collected
ls staticfiles/
```

### 3.3 Test Email System Locally
```bash
# Start local server
python manage.py runserver

# Test endpoints:
# 1. http://localhost:8000/accountsapp/verify/
# 2. http://localhost:8000/accountsapp/signup
# 3. Try signing up with a real email to test OTP
```

## 🚀 Step 4: Elastic Beanstalk Deployment

### 4.1 Initialize EB Application
```bash
# Initialize Elastic Beanstalk
eb init

# Choose options:
# 1. Select region: us-east-1 (or your preferred region)
# 2. Application name: payshift-production
# 3. Platform: Python 3.10 running on 64bit Amazon Linux 2
# 4. CodeCommit: No
# 5. SSH: Yes, create new keypair
# 6. Keypair name: payshift-key
```

### 4.2 Create Production Environment
```bash
# Create production environment
eb create payshift-prod-env

# This will:
# - Create EC2 instances
# - Set up load balancer
# - Configure auto-scaling
# - Deploy your application
# - Take 5-10 minutes
```

### 4.3 Configure Environment Variables
```bash
# Set all required environment variables
eb setenv \
  EMAIL_HOST_PASSWORD=your_16_char_app_password \
  EMAIL_HOST_USER=onlypayshift@gmail.com \
  EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend \
  EMAIL_HOST=smtp.gmail.com \
  EMAIL_PORT=587 \
  EMAIL_USE_TLS=True \
  DEFAULT_FROM_EMAIL="Payshift <onlypayshift@gmail.com>" \
  DEBUG=False \
  ALLOWED_HOSTS=".elasticbeanstalk.com" \
  SECRET_KEY="your-production-secret-key-here"
```

### 4.4 Deploy Application
```bash
# Deploy the application
eb deploy

# Monitor deployment
eb status
eb health
```

## ✅ Step 5: Verify Deployment

### 5.1 Test Application
```bash
# Open application in browser
eb open

# Test these URLs:
# 1. Main app: https://your-app.elasticbeanstalk.com/
# 2. Verification page: https://your-app.elasticbeanstalk.com/accountsapp/verify/
# 3. API docs: https://your-app.elasticbeanstalk.com/accountsapp/docs
# 4. Admin: https://your-app.elasticbeanstalk.com/admin/
```

### 5.2 Test Email OTP System
```bash
# 1. Go to signup page
# 2. Register with a real email address
# 3. Check email for OTP (including spam folder)
# 4. Use verification page to verify OTP
# 5. Confirm account is activated
```

## 🔧 Configuration Files Required

### .ebextensions/django.config
```yaml
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: payshift.wsgi:application
  aws:elasticbeanstalk:application:environment:
    DJANGO_SETTINGS_MODULE: payshift.settings
```

### .platform/hooks/postdeploy/01_migrate.sh
```bash
#!/bin/bash
source /var/app/venv/*/bin/activate
cd /var/app/current
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

## 💰 Cost Estimation (Monthly)

- **EC2 t3.micro instances**: $8-15
- **Application Load Balancer**: $20-25  
- **Data transfer**: $5-10
- **CloudWatch logs**: $2-5
- **Total estimated**: $35-55/month

## 🚨 Security Checklist

- [ ] DEBUG=False in production
- [ ] Strong SECRET_KEY generated
- [ ] ALLOWED_HOSTS properly configured
- [ ] Gmail App Password used (not regular password)
- [ ] Environment variables set in EB (not in code)
- [ ] HTTPS enabled (automatic with EB)

## 🆘 Troubleshooting

### Common Issues:

1. **Email not sending:**
   ```bash
   eb logs --all | grep -i email
   # Check Gmail App Password is correct
   # Verify 2FA is enabled on Gmail
   ```

2. **Static files missing:**
   ```bash
   python manage.py collectstatic --noinput
   eb deploy
   ```

3. **Database errors:**
   ```bash
   eb ssh
   cd /var/app/current
   python manage.py migrate
   ```

4. **Environment variables:**
   ```bash
   eb printenv
   # Verify all variables are set correctly
   ```

### Debug Commands:
```bash
eb logs --all          # View all logs
eb ssh                 # SSH into instance
eb config              # View configuration
eb printenv            # View environment variables
eb status              # Check status
eb health              # Check health
```

## 🎉 Success!

Your Payshift application with email OTP verification is now live!

**Features Available:**
- ✅ User registration with email OTP
- ✅ Beautiful verification page
- ✅ Professional email templates
- ✅ Complete API documentation
- ✅ Admin interface
- ✅ All Django apps functional

**Next Steps:**
1. Set up custom domain (optional)
2. Configure SSL certificate (optional)
3. Set up monitoring and alerts
4. Create backup strategy

---

**🔗 Your live application:** `https://your-app.elasticbeanstalk.com/`
