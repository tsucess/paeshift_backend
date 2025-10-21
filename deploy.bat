@echo off
setlocal enabledelayedexpansion

:: Create log file with timestamp
set TIMESTAMP=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set LOGFILE=deployment_%TIMESTAMP%.log

echo ======================================== | tee %LOGFILE%
echo Payshift Deployment to AWS Elastic Beanstalk | tee -a %LOGFILE%
echo Started at: %date% %time% | tee -a %LOGFILE%
echo ======================================== | tee -a %LOGFILE%

echo. | tee -a %LOGFILE%
echo [DEBUG] Current directory: %CD% | tee -a %LOGFILE%
echo [DEBUG] Python version check... | tee -a %LOGFILE%
python --version 2>&1 | tee -a %LOGFILE%

echo. | tee -a %LOGFILE%
echo Step 1: Checking EB CLI... | tee -a %LOGFILE%
echo [DEBUG] EB CLI path: %CD%\eb-env-py310\Scripts\eb.exe | tee -a %LOGFILE%
eb-env-py310\Scripts\eb.exe --version 2>&1 | tee -a %LOGFILE%
if %errorlevel% neq 0 (
    echo [ERROR] EB CLI not found or not working properly | tee -a %LOGFILE%
    echo [ERROR] Please check your eb-env-py310 virtual environment | tee -a %LOGFILE%
    echo [DEBUG] Exit code: %errorlevel% | tee -a %LOGFILE%
    pause
    exit /b 1
)
echo [SUCCESS] EB CLI is working | tee -a %LOGFILE%

echo. | tee -a %LOGFILE%
echo Step 2: Checking AWS credentials... | tee -a %LOGFILE%
eb-env-py310\Scripts\eb.exe list --verbose 2>&1 | tee -a %LOGFILE%
set LIST_EXIT_CODE=%errorlevel%
echo [DEBUG] List command exit code: %LIST_EXIT_CODE% | tee -a %LOGFILE%

echo. | tee -a %LOGFILE%
echo Step 3: Collecting static files... | tee -a %LOGFILE%
python manage.py collectstatic --noinput 2>&1 | tee -a %LOGFILE%
if %errorlevel% neq 0 (
    echo [WARNING] Static files collection failed, continuing anyway... | tee -a %LOGFILE%
    echo [DEBUG] Static collection exit code: %errorlevel% | tee -a %LOGFILE%
) else (
    echo [SUCCESS] Static files collected successfully | tee -a %LOGFILE%
)

echo. | tee -a %LOGFILE%
echo Step 4: Checking if paeshift-env environment exists... | tee -a %LOGFILE%
eb-env-py310\Scripts\eb.exe status paeshift-env 2>&1 | tee -a %LOGFILE%
set STATUS_EXIT_CODE=%errorlevel%
echo [DEBUG] Status command exit code: %STATUS_EXIT_CODE% | tee -a %LOGFILE%

if %STATUS_EXIT_CODE% neq 0 (
    echo [INFO] Environment paeshift-env does not exist, creating it... | tee -a %LOGFILE%
    echo [DEBUG] Creating environment with Python 3.11 platform... | tee -a %LOGFILE%
    eb-env-py310\Scripts\eb.exe create paeshift-env --platform "Python 3.11" --verbose 2>&1 | tee -a %LOGFILE%
    set CREATE_EXIT_CODE=%errorlevel%
    echo [DEBUG] Create command exit code: %CREATE_EXIT_CODE% | tee -a %LOGFILE%

    if !CREATE_EXIT_CODE! neq 0 (
        echo [ERROR] Environment creation failed | tee -a %LOGFILE%
        echo [DEBUG] Checking logs for more details... | tee -a %LOGFILE%
        eb-env-py310\Scripts\eb.exe logs --all 2>&1 | tee -a %LOGFILE%
        pause
        exit /b 1
    )
    echo [SUCCESS] Environment paeshift-env created successfully | tee -a %LOGFILE%
) else (
    echo [SUCCESS] Environment paeshift-env already exists | tee -a %LOGFILE%
)

echo. | tee -a %LOGFILE%
echo Step 5: Setting paeshift-env as default environment... | tee -a %LOGFILE%
eb-env-py310\Scripts\eb.exe use paeshift-env 2>&1 | tee -a %LOGFILE%
if %errorlevel% neq 0 (
    echo [ERROR] Failed to set paeshift-env as default | tee -a %LOGFILE%
    echo [DEBUG] Use command exit code: %errorlevel% | tee -a %LOGFILE%
    pause
    exit /b 1
)
echo [SUCCESS] paeshift-env set as default environment | tee -a %LOGFILE%

echo. | tee -a %LOGFILE%
echo Step 6: Deploying to AWS Elastic Beanstalk... | tee -a %LOGFILE%
echo [INFO] This may take several minutes... | tee -a %LOGFILE%
echo [DEBUG] Starting deployment at: %date% %time% | tee -a %LOGFILE%
eb-env-py310\Scripts\eb.exe deploy --verbose 2>&1 | tee -a %LOGFILE%
set DEPLOY_EXIT_CODE=%errorlevel%
echo [DEBUG] Deploy command exit code: %DEPLOY_EXIT_CODE% | tee -a %LOGFILE%
echo [DEBUG] Deployment finished at: %date% %time% | tee -a %LOGFILE%

if %DEPLOY_EXIT_CODE% neq 0 (
    echo [ERROR] Deployment failed | tee -a %LOGFILE%
    echo [DEBUG] Fetching deployment logs... | tee -a %LOGFILE%
    eb-env-py310\Scripts\eb.exe logs --all 2>&1 | tee -a %LOGFILE%
    echo [DEBUG] Checking environment health... | tee -a %LOGFILE%
    eb-env-py310\Scripts\eb.exe health --refresh 2>&1 | tee -a %LOGFILE%
    pause
    exit /b 1
)

echo. | tee -a %LOGFILE%
echo ======================================== | tee -a %LOGFILE%
echo [SUCCESS] Deployment completed successfully! | tee -a %LOGFILE%
echo Completed at: %date% %time% | tee -a %LOGFILE%
echo ======================================== | tee -a %LOGFILE%

echo. | tee -a %LOGFILE%
echo Step 7: Checking application health... | tee -a %LOGFILE%
eb-env-py310\Scripts\eb.exe health 2>&1 | tee -a %LOGFILE%

echo. | tee -a %LOGFILE%
echo Step 8: Opening application... | tee -a %LOGFILE%
eb-env-py310\Scripts\eb.exe open 2>&1 | tee -a %LOGFILE%

echo. | tee -a %LOGFILE%
echo [INFO] Deployment log saved to: %LOGFILE% | tee -a %LOGFILE%
echo [INFO] Full deployment process completed successfully! | tee -a %LOGFILE%

pause
