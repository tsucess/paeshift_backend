# Prepare Deployment Package for Elastic Beanstalk
# Single Instance Free Tier Setup

Write-Host "📦 Preparing Payshift Deployment Package" -ForegroundColor Green
Write-Host "=" * 50

# Build React Frontend with correct environment
Write-Host "🔨 Building React Frontend..." -ForegroundColor Cyan
cd paeshift-frontend
$env:VITE_API_BASE_URL="http://payshift-production-east.eba-qadiqdti.us-east-1.elasticbeanstalk.com"
npm run build

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ React build completed successfully" -ForegroundColor Green
} else {
    Write-Host "❌ React build failed" -ForegroundColor Red
    exit 1
}

cd ..

# Create deployment package
Write-Host "`n📦 Creating deployment package..." -ForegroundColor Cyan

# Files to include in deployment
$filesToInclude = @(
    "*.py",
    "requirements.txt",
    "manage.py",
    ".ebextensions\*",
    "payshift\*",
    "accounts\*",
    "core\*",
    "jobs\*",
    "payment\*",
    "rating\*",
    "notifications\*",
    "paeshift-frontend\dist\*",
    "static\*",
    "templates\*"
)

# Create zip file
$zipFile = "payshift-deployment-$(Get-Date -Format 'yyyyMMdd-HHmmss').zip"

Write-Host "Creating $zipFile..." -ForegroundColor Yellow

# Use PowerShell to create zip
Compress-Archive -Path $filesToInclude -DestinationPath $zipFile -Force

Write-Host "✅ Deployment package created: $zipFile" -ForegroundColor Green

Write-Host "`n🎯 Next Steps:" -ForegroundColor Yellow
Write-Host "1. Go to Elastic Beanstalk Console (us-east-1)"
Write-Host "2. Create new environment with these settings:"
Write-Host "   - Environment name: payshift-production-east"
Write-Host "   - Platform: Python 3.11"
Write-Host "   - Instance type: t3.micro (free tier)"
Write-Host "   - Environment type: Single instance"
Write-Host "3. Upload this zip file: $zipFile"
Write-Host "4. Add your RDS password to environment variables"
Write-Host "5. Deploy and test!"

Write-Host "`n📋 Environment Variables to Add:" -ForegroundColor Cyan
Write-Host "RDS_PASSWORD = [your-rds-master-password]"
Write-Host "(All other variables are already configured)"

Write-Host "`nPress any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
