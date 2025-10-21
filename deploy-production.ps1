#!/usr/bin/env powershell
# Production deployment script for Paeshift
# This script prepares the app for AWS Elastic Beanstalk deployment

Write-Host "🚀 Starting Paeshift Production Deployment..." -ForegroundColor Green

# Step 1: Activate virtual environment
Write-Host "📦 Activating virtual environment..." -ForegroundColor Yellow
& "eb-env-py310\Scripts\Activate.ps1"

# Step 2: Install/Update Python dependencies
Write-Host "📦 Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Step 3: Build React frontend (if Node.js is available)
Write-Host "⚛️ Building React frontend..." -ForegroundColor Yellow
Set-Location paeshift-frontend

# Check if npm is available
try {
    npm --version | Out-Null
    Write-Host "✅ Node.js found, building React app..." -ForegroundColor Green
    
    # Install React dependencies
    npm install
    
    # Build React app for production
    npm run build
    
    Write-Host "✅ React build completed!" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Node.js not found, skipping React build..." -ForegroundColor Yellow
    Write-Host "React app will use development mode" -ForegroundColor Yellow
}

# Go back to project root
Set-Location ..

# Step 4: Collect Django static files
Write-Host "📁 Collecting Django static files..." -ForegroundColor Yellow
python manage.py collectstatic --noinput --clear

# Step 5: Run Django checks
Write-Host "🔍 Running Django system checks..." -ForegroundColor Yellow
python manage.py check --deploy

# Step 6: Create/update database migrations (but don't run them)
Write-Host "🗃️ Creating database migrations..." -ForegroundColor Yellow
python manage.py makemigrations

# Step 7: Deploy to Elastic Beanstalk
Write-Host "🌐 Deploying to AWS Elastic Beanstalk..." -ForegroundColor Green
eb deploy

Write-Host "✅ Deployment completed!" -ForegroundColor Green
Write-Host "🌍 Your app should be available at your EB environment URL" -ForegroundColor Cyan

# Step 8: Show deployment info
Write-Host "📊 Getting deployment status..." -ForegroundColor Yellow
eb status

Write-Host "🎉 Deployment process finished!" -ForegroundColor Green
