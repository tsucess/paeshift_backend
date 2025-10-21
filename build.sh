#!/bin/bash
set -e

echo "=========================================="
echo "Starting Render Build Process"
echo "=========================================="

# Step 1: Install dependencies
echo "Step 1: Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 2: Run migrations
echo "Step 2: Running Django migrations..."
python manage.py migrate --noinput

# Step 3: Create superuser if needed
echo "Step 3: Checking for superuser..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    print("Creating superuser...")
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print("Superuser created!")
else:
    print("Superuser already exists")
END

# Step 4: Collect static files
echo "Step 4: Collecting static files..."
python manage.py collectstatic --noinput

echo "=========================================="
echo "Build process completed successfully!"
echo "=========================================="

