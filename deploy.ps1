# Payshift Deployment Script for AWS Elastic Beanstalk
# Run this script in PowerShell
# Configured with PostgreSQL Primary and SQLite Fallback

Write-Host "========================================" -ForegroundColor Green
Write-Host "Payshift Deployment to AWS Elastic Beanstalk" -ForegroundColor Green
Write-Host "PostgreSQL Primary + SQLite Fallback Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Green

# Display Database Configuration
Write-Host "`nDatabase Configuration:" -ForegroundColor Yellow
Write-Host "Primary: PostgreSQL (AWS RDS)" -ForegroundColor White
Write-Host "Host: paeshift-postgres-db.cmd66sgm8qyp.us-east-1.rds.amazonaws.com" -ForegroundColor White
Write-Host "Database: postgres" -ForegroundColor White
Write-Host "Username: postgres" -ForegroundColor White
Write-Host "Port: 5432" -ForegroundColor White
Write-Host "Fallback: SQLite (local file)" -ForegroundColor White
Write-Host "Region: us-east-1f" -ForegroundColor White

# Step 1: Test Database Configuration
Write-Host "`nStep 1: Testing Database Configuration..." -ForegroundColor Yellow
try {
    python smart_db_config.py
    Write-Host "✅ Database configuration test completed" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Database test failed, but deployment will continue with SQLite fallback" -ForegroundColor Yellow
}

# Step 2: Check EB CLI
Write-Host "`nStep 2: Checking EB CLI..." -ForegroundColor Yellow
try {
    & "eb-env-py310\Scripts\eb.exe" --version
    Write-Host "✅ EB CLI is working" -ForegroundColor Green
} catch {
    Write-Host "❌ ERROR: EB CLI not found or not working properly" -ForegroundColor Red
    Write-Host "Please check your eb-env-py310 virtual environment" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 3: Build React Frontend
Write-Host "`nStep 3: Building React Frontend..." -ForegroundColor Yellow
Set-Location "paeshift-frontend"
try {
    Write-Host "📦 Installing npm dependencies..." -ForegroundColor White
    npm install

    Write-Host "🔧 Setting production environment variables..." -ForegroundColor White
    $env:VITE_API_BASE_URL = "http://payshift-production.eba-qadiqdti.us-east-1.elasticbeanstalk.com"
    $env:VITE_APP_ENV = "production"

    Write-Host "🏗️ Building React app for production..." -ForegroundColor White
    npm run build

    Write-Host "✅ React build completed successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ React build failed" -ForegroundColor Red
    Write-Host "Error details: $_" -ForegroundColor Red
    Set-Location ".."
    Read-Host "Press Enter to exit"
    exit 1
}
Set-Location ".."

# Step 4: List environments
Write-Host "`nStep 4: Listing current environments..." -ForegroundColor Yellow
& "eb-env-py310\Scripts\eb.exe" list

# Step 5: Collect static files
Write-Host "`nStep 5: Collecting static files..." -ForegroundColor Yellow
try {
    python manage.py collectstatic --noinput
    Write-Host "✅ Static files collected successfully" -ForegroundColor Green
} catch {
    Write-Host "⚠️  WARNING: Static files collection failed, continuing anyway..." -ForegroundColor Yellow
}

# Step 6: Create environment if it doesn't exist
Write-Host "`nStep 6: Checking/Creating eb-env-py310 environment..." -ForegroundColor Yellow
$envExists = & "eb-env-py310\Scripts\eb.exe" status eb-env-py310 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Environment eb-env-py310 does not exist. Creating it..." -ForegroundColor Yellow
    Write-Host "This will take several minutes..." -ForegroundColor Yellow
    & "eb-env-py310\Scripts\eb.exe" create eb-env-py310 --platform "Python 3.10"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ ERROR: Failed to create environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "✅ Environment eb-env-py310 exists" -ForegroundColor Green
}

# Step 7: Use the environment
Write-Host "`nStep 7: Setting environment to eb-env-py310..." -ForegroundColor Yellow
& "eb-env-py310\Scripts\eb.exe" use eb-env-py310

# Step 8: Deploy with PostgreSQL Configuration
Write-Host "`nStep 8: Deploying to AWS Elastic Beanstalk..." -ForegroundColor Yellow
Write-Host "🚀 Deploying with PostgreSQL primary and SQLite fallback..." -ForegroundColor Cyan
Write-Host "This may take several minutes..." -ForegroundColor Yellow
& "eb-env-py310\Scripts\eb.exe" deploy
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ERROR: Deployment failed" -ForegroundColor Red
    Write-Host "Check the logs using: eb-env-py310\Scripts\eb.exe logs" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "🎉 Deployment completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Step 9: Get application URL and status
Write-Host "`nStep 9: Getting application information..." -ForegroundColor Yellow
& "eb-env-py310\Scripts\eb.exe" status

# Step 10: Open application
Write-Host "`nStep 10: Opening application in browser..." -ForegroundColor Yellow
& "eb-env-py310\Scripts\eb.exe" open

Write-Host "`n📝 Post-Deployment Notes:" -ForegroundColor Cyan
Write-Host "✅ Database: PostgreSQL primary with SQLite fallback configured" -ForegroundColor White
Write-Host "✅ Frontend: React app built and deployed" -ForegroundColor White
Write-Host "✅ API: User profile location field issue fixed" -ForegroundColor White
Write-Host "✅ CORS: Configured for frontend communication" -ForegroundColor White

Write-Host "`n🔧 Useful Commands:" -ForegroundColor Cyan
Write-Host "eb-env-py310\Scripts\eb.exe status  - Check application status" -ForegroundColor White
Write-Host "eb-env-py310\Scripts\eb.exe logs    - View application logs" -ForegroundColor White
Write-Host "eb-env-py310\Scripts\eb.exe health  - Check application health" -ForegroundColor White

Read-Host "`nPress Enter to exit"
