# PowerShell script to install development dependencies for Paeshift
# Run this script from the paeshift-recover directory

Write-Host "🚀 Installing Paeshift Development Dependencies" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""

# Check if virtual environment is activated
if (-not $env:VIRTUAL_ENV) {
    Write-Host "⚠️  Virtual environment not activated!" -ForegroundColor Yellow
    Write-Host "Please activate it first:" -ForegroundColor Yellow
    Write-Host "  venv\Scripts\activate" -ForegroundColor Cyan
    exit 1
}

Write-Host "✅ Virtual environment detected: $env:VIRTUAL_ENV" -ForegroundColor Green
Write-Host ""

# Upgrade pip
Write-Host "📦 Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

Write-Host ""
Write-Host "📦 Installing development requirements..." -ForegroundColor Cyan
Write-Host "This may take 3-5 minutes..." -ForegroundColor Yellow
Write-Host ""

# Install requirements
pip install -r requirements-dev.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Installation successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Green
    Write-Host "  1. Run migrations: python manage.py migrate" -ForegroundColor Cyan
    Write-Host "  2. Create superuser: python manage.py createsuperuser" -ForegroundColor Cyan
    Write-Host "  3. Start server: python manage.py runserver" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "❌ Installation failed!" -ForegroundColor Red
    Write-Host "Please check the error messages above." -ForegroundColor Red
    exit 1
}

