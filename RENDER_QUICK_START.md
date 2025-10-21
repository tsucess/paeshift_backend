# 🚀 Render Deployment Quick Start

## ✅ Step 1 Complete: Backend Preparation

Your backend is now ready for Render deployment!

### What Was Done

```
✅ requirements.txt       - 69 Python dependencies
✅ runtime.txt           - Python 3.12.0 specified
✅ .env.example          - Environment variables template
✅ Procfile              - Gunicorn startup command
✅ Django Settings       - Production configuration
```

---

## 🎯 Quick Reference

### Key Files
| File | Purpose |
|------|---------|
| `requirements.txt` | All Python packages needed |
| `runtime.txt` | Python version (3.12.0) |
| `Procfile` | How to start the app |
| `.env.example` | Environment variables needed |

### Key Dependencies
- **Django 4.2.16** - Web framework
- **PostgreSQL** - Database (psycopg2-binary)
- **Gunicorn** - Production server
- **Channels** - WebSocket support
- **Redis** - Caching
- **Celery** - Background tasks
- **Paystack & Flutterwave** - Payment processing

---

## 🔧 Environment Variables Needed

### Must Set (Critical)
```
DJANGO_SECRET_KEY=<generate-strong-key>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-backend.onrender.com
DATABASE_URL=postgresql://user:pass@host:port/db
CORS_ALLOWED_ORIGINS=https://your-frontend.onrender.com
```

### Should Set (Recommended)
```
REDIS_URL=redis://...
SENTRY_DSN=https://...
GOOGLE_MAPS_API_KEY=...
```

### Payment & Email
```
PAYSTACK_SECRET_KEY=...
PAYSTACK_PUBLIC_KEY=...
FLUTTERWAVE_SECRET_KEY=...
FLUTTERWAVE_PUBLIC_KEY=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
```

---

## 📋 Deployment Checklist

### Before Deploying
- [ ] Commit changes to GitHub
- [ ] Have Render account ready
- [ ] Have PostgreSQL database URL
- [ ] Have all environment variables ready

### On Render Dashboard
- [ ] Create PostgreSQL database
- [ ] Create Web Service
- [ ] Connect GitHub repository
- [ ] Set all environment variables
- [ ] Deploy

### After Deployment
- [ ] Run migrations: `python manage.py migrate`
- [ ] Create superuser: `python manage.py createsuperuser`
- [ ] Test API endpoints
- [ ] Check logs for errors

---

## 🚀 Next Steps

### Step 2: Create Render Services

1. **Create PostgreSQL Database**
   - Go to Render Dashboard
   - New → PostgreSQL
   - Name: `paeshift-db`
   - Copy Internal Database URL

2. **Create Web Service**
   - New → Web Service
   - Connect your backend repo
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn payshift.wsgi:application`
   - Add environment variables

3. **Run Migrations**
   - Use Render Shell
   - `python manage.py migrate`
   - `python manage.py createsuperuser`

---

## 📚 Useful Commands

### Generate Secret Key
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Test Locally Before Deploying
```bash
# Set environment variables
export DJANGO_DEBUG=False
export DJANGO_SECRET_KEY=your-key
export DATABASE_URL=postgresql://...

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver
```

---

## 🔐 Security Reminders

- ✅ Never commit `.env` file
- ✅ Use `.env.example` as template
- ✅ Generate strong `DJANGO_SECRET_KEY`
- ✅ Set `DJANGO_DEBUG=False` in production
- ✅ Use environment variables for all secrets
- ✅ Update `ALLOWED_HOSTS` with your domain
- ✅ Set `CORS_ALLOWED_ORIGINS` correctly

---

## 📞 Troubleshooting

### 502 Bad Gateway
- Check logs in Render dashboard
- Verify environment variables are set
- Ensure migrations have run

### Database Connection Error
- Verify `DATABASE_URL` is correct
- Check database is running
- Ensure IP whitelist allows Render

### CORS Errors
- Update `CORS_ALLOWED_ORIGINS` with frontend URL
- Verify frontend URL is correct
- Check CSRF settings

### Static Files Not Loading
- Run: `python manage.py collectstatic`
- Check `STATIC_ROOT` and `STATIC_URL`

---

## 📖 Documentation

- [Render Django Docs](https://render.com/docs/deploy-django)
- [Django Deployment](https://docs.djangoproject.com/en/4.2/howto/deployment/)
- [Environment Variables](https://12factor.net/config)

---

## ✨ Status

**Backend**: ✅ Ready for Render  
**Frontend**: ⏳ Next (Step 1 for frontend)  
**Database**: ⏳ Create on Render  
**Deployment**: ⏳ Ready to start  

---

**Last Updated**: 2025-10-21  
**Ready to Deploy**: YES ✅

