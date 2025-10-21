Write-Host "=== Paeshift Deployment with React Build ===" -ForegroundColor Cyan

# Step 1: Build React frontend
Write-Host "Step 1: Building React frontend..." -ForegroundColor Yellow
Set-Location paeshift-frontend

Write-Host "Installing npm dependencies..." -ForegroundColor Yellow
npm install

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: npm install failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Building React app..." -ForegroundColor Yellow
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: React build failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "React build completed successfully!" -ForegroundColor Green

# Step 2: Return to root directory
Set-Location ..

# Step 3: Deploy to Elastic Beanstalk
Write-Host "Step 2: Deploying to AWS Elastic Beanstalk..." -ForegroundColor Yellow
Write-Host "This may take several minutes..." -ForegroundColor Yellow

& "eb-env-py310\Scripts\eb.exe" deploy

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Deployment failed" -ForegroundColor Red
    Write-Host "Check the logs using: eb-env-py310\Scripts\eb.exe logs" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Deployment completed successfully!" -ForegroundColor Green
Write-Host "Opening application..." -ForegroundColor Yellow

& "eb-env-py310\Scripts\eb.exe" open

Read-Host "Press Enter to exit"
