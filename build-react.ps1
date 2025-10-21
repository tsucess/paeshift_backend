Write-Host "Building React frontend for deployment..." -ForegroundColor Yellow

Set-Location paeshift-frontend

Write-Host "Installing dependencies..." -ForegroundColor Yellow
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
Write-Host "Built files are in paeshift-frontend/dist/" -ForegroundColor Green

Read-Host "Press Enter to continue"
