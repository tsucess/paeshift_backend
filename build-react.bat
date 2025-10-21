@echo off
echo Building React frontend for deployment...

cd paeshift-frontend

echo Installing dependencies...
npm install

echo Building React app...
npm run build

if %errorlevel% neq 0 (
    echo ERROR: React build failed
    pause
    exit /b 1
)

echo React build completed successfully!
echo Built files are in paeshift-frontend/dist/

cd ..

echo Deploying to AWS Elastic Beanstalk...
eb-env-py310\Scripts\eb.exe deploy

echo Deployment completed!
pause
