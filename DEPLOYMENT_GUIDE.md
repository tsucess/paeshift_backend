# Payshift AWS Elastic Beanstalk Deployment Guide

## Prerequisites
- AWS CLI configured with proper credentials
- EB CLI installed (already done in your eb-env-py310 environment)
- Your application code ready for deployment

## Step-by-Step Deployment Process

### 1. Activate Virtual Environment
```bash
# On Windows
eb-env-py310\Scripts\activate.bat

# On PowerShell (if scripts are enabled)
eb-env-py310\Scripts\Activate.ps1
```

### 2. Check EB CLI Status
```bash
eb-env-py310\Scripts\eb.exe --version
eb-env-py310\Scripts\eb.exe list
```

### 3. Create eb-env-py310 Environment (if it doesn't exist)
```bash
eb-env-py310\Scripts\eb.exe create eb-env-py310 --platform "Python 3.10" --region us-west-2
```

### 4. Set Environment Variables (Important!)
Before deploying, you need to set these environment variables in your EB environment:

```bash
eb-env-py310\Scripts\eb.exe setenv DJANGO_SECRET_KEY="your-production-secret-key"
eb-env-py310\Scripts\eb.exe setenv DJANGO_DEBUG="False"
eb-env-py310\Scripts\eb.exe setenv DJANGO_ALLOWED_HOSTS=".elasticbeanstalk.com"
eb-env-py310\Scripts\eb.exe setenv PAYSTACK_SECRET_KEY="your-paystack-secret-key"
eb-env-py310\Scripts\eb.exe setenv GOOGLE_MAPS_API_KEY="your-google-maps-api-key"
```

### 5. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 6. Deploy to EB
```bash
eb-env-py310\Scripts\eb.exe use eb-env-py310
eb-env-py310\Scripts\eb.exe deploy
```

### 7. Check Deployment Status
```bash
eb-env-py310\Scripts\eb.exe status
eb-env-py310\Scripts\eb.exe health
```

### 8. Open Application
```bash
eb-env-py310\Scripts\eb.exe open
```

## Configuration Files Created

I've created the following configuration files for your deployment:

1. **`.ebextensions/django.config`** - Basic Django configuration
2. **`.ebextensions/01_packages.config`** - System packages
3. **`.ebextensions/02_python.config`** - Python and Django commands
4. **`.ebextensions/03_environment.config`** - Environment variables
5. **`application.py`** - WSGI application entry point
6. **`deploy.bat`** - Automated deployment script

## Important Notes

### Database Configuration
- Your app is currently configured to use SQLite for development
- For production, consider using Amazon RDS (PostgreSQL)
- Update DATABASE_URL environment variable accordingly

### Redis Configuration
- Consider using Amazon ElastiCache for Redis in production
- Update REDIS_HOST environment variable

### Security
- Change all default secret keys and passwords
- Use production payment gateway keys
- Enable HTTPS in production

### Static Files
- Static files are configured to be served from `/static/` path
- Make sure to run `collectstatic` before deployment

## Troubleshooting

### Common Issues:
1. **Environment not found**: Create the environment first using `eb create`
2. **Permission errors**: Ensure AWS credentials are properly configured
3. **Static files not loading**: Check static file configuration in settings
4. **Database errors**: Ensure migrations are run during deployment

### Logs:
```bash
eb-env-py310\Scripts\eb.exe logs
```

## Manual Alternative

If EB CLI is not working properly, you can:
1. Create a ZIP file of your application
2. Upload directly through AWS Console
3. Configure environment variables through the console
4. Monitor deployment through the AWS EB dashboard

## Next Steps After Deployment

1. Set up a custom domain name
2. Configure SSL certificate
3. Set up monitoring and logging
4. Configure auto-scaling
5. Set up CI/CD pipeline
6. Configure database backups
7. Set up Redis/ElastiCache for production caching
