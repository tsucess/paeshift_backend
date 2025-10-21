# Manual Deployment Steps for Payshift to AWS Elastic Beanstalk

## Quick Commands to Run

Open Command Prompt or PowerShell in your project directory and run these commands one by one:

### 1. Check EB CLI
```cmd
eb-env-py310\Scripts\eb.exe --version
```

### 2. List current environments
```cmd
eb-env-py310\Scripts\eb.exe list
```

### 3. Create eb-env-py310 environment (if it doesn't exist)
```cmd
eb-env-py310\Scripts\eb.exe create eb-env-py310 --platform "Python 3.10"
```
**Note: This will take 5-10 minutes**

### 4. Use the eb-env-py310 environment
```cmd
eb-env-py310\Scripts\eb.exe use eb-env-py310
```

### 5. Collect static files
```cmd
python manage.py collectstatic --noinput
```

### 6. Deploy to Elastic Beanstalk
```cmd
eb-env-py310\Scripts\eb.exe deploy
```
**Note: This will take 3-5 minutes**

### 7. Check deployment status
```cmd
eb-env-py310\Scripts\eb.exe status
```

### 8. Open your application
```cmd
eb-env-py310\Scripts\eb.exe open
```

## Alternative: Run the Deployment Script

I've created two deployment scripts for you:

### Option 1: Batch Script (Windows)
```cmd
deploy.bat
```

### Option 2: PowerShell Script
```powershell
powershell -ExecutionPolicy Bypass -File deploy.ps1
```

## If Environment Already Exists

If `eb-env-py310` already exists in your AWS account, you can skip step 3 and go directly to step 4.

## Environment Variables

After deployment, you may need to set environment variables through the AWS Console:

1. Go to AWS Elastic Beanstalk Console
2. Select your application
3. Select `eb-env-py310` environment
4. Go to Configuration > Software
5. Add these environment variables:
   - `DJANGO_SECRET_KEY`: Your production secret key
   - `DJANGO_DEBUG`: False
   - `PAYSTACK_SECRET_KEY`: Your Paystack secret key
   - `GOOGLE_MAPS_API_KEY`: Your Google Maps API key

## Troubleshooting

### If deployment fails:
```cmd
eb-env-py310\Scripts\eb.exe logs
```

### If environment creation fails:
- Check your AWS credentials
- Ensure you have proper permissions
- Try a different region

### If static files don't load:
- Make sure `collectstatic` ran successfully
- Check the `.ebextensions/django.config` file

## Files I've Prepared for You

1. **`.elasticbeanstalk/config.yml`** - Updated to use eb-env-py310
2. **`.ebextensions/django.config`** - Django configuration
3. **`.ebextensions/01_packages.config`** - System packages
4. **`.ebextensions/02_python.config`** - Python commands
5. **`.ebextensions/03_environment.config`** - Environment variables
6. **`application.py`** - WSGI entry point
7. **`deploy.bat`** - Windows batch deployment script
8. **`deploy.ps1`** - PowerShell deployment script

## Expected Output

When successful, you should see:
- Environment creation: "Environment eb-env-py310 launched successfully"
- Deployment: "Environment update completed successfully"
- Your application URL will be displayed

## Next Steps After Deployment

1. Test your application functionality
2. Set up a custom domain
3. Configure SSL certificate
4. Set up monitoring
5. Configure auto-scaling if needed
