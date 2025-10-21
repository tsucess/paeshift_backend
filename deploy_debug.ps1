# Comprehensive Deployment Script with Full Debugging
# Payshift AWS Elastic Beanstalk Deployment

# Function to log messages with timestamp
function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] [$Level] $Message"
    Write-Host $logMessage
    Add-Content -Path $logFile -Value $logMessage
}

# Create log file with timestamp
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = "deployment_$timestamp.log"

Write-Log "========================================" "HEADER"
Write-Log "Payshift Deployment to AWS Elastic Beanstalk" "HEADER"
Write-Log "Started at: $(Get-Date)" "HEADER"
Write-Log "========================================" "HEADER"

Write-Log "Current directory: $(Get-Location)" "DEBUG"
Write-Log "PowerShell version: $($PSVersionTable.PSVersion)" "DEBUG"

# Step 1: Check Python
Write-Log "Step 1: Checking Python installation..." "INFO"
try {
    $pythonVersion = python --version 2>&1
    Write-Log "Python version: $pythonVersion" "DEBUG"
    Write-Log "Python check successful" "SUCCESS"
} catch {
    Write-Log "Python check failed: $($_.Exception.Message)" "ERROR"
    exit 1
}

# Step 2: Check EB CLI
Write-Log "Step 2: Checking EB CLI..." "INFO"
$ebPath = ".\eb-env-py310\Scripts\eb.exe"
Write-Log "EB CLI path: $ebPath" "DEBUG"

if (Test-Path $ebPath) {
    Write-Log "EB CLI executable found" "DEBUG"
    try {
        $ebVersion = & $ebPath --version 2>&1
        Write-Log "EB CLI version: $ebVersion" "DEBUG"
        Write-Log "EB CLI check successful" "SUCCESS"
    } catch {
        Write-Log "EB CLI execution failed: $($_.Exception.Message)" "ERROR"
        exit 1
    }
} else {
    Write-Log "EB CLI not found at path: $ebPath" "ERROR"
    exit 1
}

# Step 3: Check AWS credentials and list environments
Write-Log "Step 3: Checking AWS credentials and environments..." "INFO"
try {
    Write-Log "Executing: eb list --verbose" "DEBUG"
    $listOutput = & $ebPath list --verbose 2>&1
    Write-Log "List output: $listOutput" "DEBUG"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Log "Environment list retrieved successfully" "SUCCESS"
    } else {
        Write-Log "Environment list failed with exit code: $LASTEXITCODE" "WARNING"
        Write-Log "This might indicate AWS credential issues" "WARNING"
    }
} catch {
    Write-Log "List command failed: $($_.Exception.Message)" "ERROR"
}

# Step 4: Collect static files
Write-Log "Step 4: Collecting static files..." "INFO"
try {
    Write-Log "Executing: python manage.py collectstatic --noinput" "DEBUG"
    $staticOutput = python manage.py collectstatic --noinput 2>&1
    Write-Log "Static collection output: $staticOutput" "DEBUG"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Log "Static files collected successfully" "SUCCESS"
    } else {
        Write-Log "Static files collection failed with exit code: $LASTEXITCODE" "WARNING"
        Write-Log "Continuing with deployment anyway..." "WARNING"
    }
} catch {
    Write-Log "Static collection failed: $($_.Exception.Message)" "WARNING"
}

# Step 5: Check if paeshift-env exists
Write-Log "Step 5: Checking if paeshift-env environment exists..." "INFO"
try {
    Write-Log "Executing: eb status paeshift-env" "DEBUG"
    $statusOutput = & $ebPath status paeshift-env 2>&1
    Write-Log "Status output: $statusOutput" "DEBUG"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Log "Environment paeshift-env exists and is accessible" "SUCCESS"
        $environmentExists = $true
    } else {
        Write-Log "Environment paeshift-env does not exist or is not accessible" "INFO"
        Write-Log "Status command exit code: $LASTEXITCODE" "DEBUG"
        $environmentExists = $false
    }
} catch {
    Write-Log "Status check failed: $($_.Exception.Message)" "WARNING"
    $environmentExists = $false
}

# Step 6: Create environment if it doesn't exist
if (-not $environmentExists) {
    Write-Log "Step 6: Creating paeshift-env environment..." "INFO"
    try {
        Write-Log "Executing: eb create paeshift-env --platform 'Python 3.11' --verbose" "DEBUG"
        Write-Log "Environment creation started at: $(Get-Date)" "DEBUG"
        
        $createOutput = & $ebPath create paeshift-env --platform "Python 3.11" --verbose 2>&1
        Write-Log "Create output: $createOutput" "DEBUG"
        Write-Log "Environment creation finished at: $(Get-Date)" "DEBUG"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Log "Environment paeshift-env created successfully" "SUCCESS"
        } else {
            Write-Log "Environment creation failed with exit code: $LASTEXITCODE" "ERROR"
            Write-Log "Fetching logs for troubleshooting..." "DEBUG"
            
            try {
                $logsOutput = & $ebPath logs --all 2>&1
                Write-Log "Environment logs: $logsOutput" "DEBUG"
            } catch {
                Write-Log "Failed to fetch logs: $($_.Exception.Message)" "ERROR"
            }
            exit 1
        }
    } catch {
        Write-Log "Environment creation failed: $($_.Exception.Message)" "ERROR"
        exit 1
    }
} else {
    Write-Log "Step 6: Environment paeshift-env already exists, skipping creation" "INFO"
}

# Step 7: Set environment as default
Write-Log "Step 7: Setting paeshift-env as default environment..." "INFO"
try {
    Write-Log "Executing: eb use paeshift-env" "DEBUG"
    $useOutput = & $ebPath use paeshift-env 2>&1
    Write-Log "Use output: $useOutput" "DEBUG"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Log "paeshift-env set as default environment successfully" "SUCCESS"
    } else {
        Write-Log "Failed to set paeshift-env as default with exit code: $LASTEXITCODE" "ERROR"
        exit 1
    }
} catch {
    Write-Log "Setting default environment failed: $($_.Exception.Message)" "ERROR"
    exit 1
}

# Step 8: Deploy to Elastic Beanstalk
Write-Log "Step 8: Deploying to AWS Elastic Beanstalk..." "INFO"
Write-Log "This may take several minutes..." "INFO"
try {
    Write-Log "Executing: eb deploy --verbose" "DEBUG"
    Write-Log "Deployment started at: $(Get-Date)" "DEBUG"
    
    $deployOutput = & $ebPath deploy --verbose 2>&1
    Write-Log "Deploy output: $deployOutput" "DEBUG"
    Write-Log "Deployment finished at: $(Get-Date)" "DEBUG"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Log "Deployment completed successfully!" "SUCCESS"
    } else {
        Write-Log "Deployment failed with exit code: $LASTEXITCODE" "ERROR"
        Write-Log "Fetching deployment logs for troubleshooting..." "DEBUG"
        
        try {
            $deployLogsOutput = & $ebPath logs --all 2>&1
            Write-Log "Deployment logs: $deployLogsOutput" "DEBUG"
        } catch {
            Write-Log "Failed to fetch deployment logs: $($_.Exception.Message)" "ERROR"
        }
        
        try {
            Write-Log "Checking environment health..." "DEBUG"
            $healthOutput = & $ebPath health --refresh 2>&1
            Write-Log "Health output: $healthOutput" "DEBUG"
        } catch {
            Write-Log "Failed to check health: $($_.Exception.Message)" "ERROR"
        }
        exit 1
    }
} catch {
    Write-Log "Deployment failed: $($_.Exception.Message)" "ERROR"
    exit 1
}

# Step 9: Final health check
Write-Log "Step 9: Performing final health check..." "INFO"
try {
    $finalHealthOutput = & $ebPath health 2>&1
    Write-Log "Final health check: $finalHealthOutput" "DEBUG"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Log "Application health check passed" "SUCCESS"
    } else {
        Write-Log "Health check returned exit code: $LASTEXITCODE" "WARNING"
    }
} catch {
    Write-Log "Final health check failed: $($_.Exception.Message)" "WARNING"
}

# Step 10: Open application
Write-Log "Step 10: Opening application..." "INFO"
try {
    $openOutput = & $ebPath open 2>&1
    Write-Log "Open output: $openOutput" "DEBUG"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Log "Application opened successfully" "SUCCESS"
    } else {
        Write-Log "Failed to open application with exit code: $LASTEXITCODE" "WARNING"
    }
} catch {
    Write-Log "Opening application failed: $($_.Exception.Message)" "WARNING"
}

Write-Log "========================================" "HEADER"
Write-Log "DEPLOYMENT PROCESS COMPLETED" "HEADER"
Write-Log "Completed at: $(Get-Date)" "HEADER"
Write-Log "Log file saved to: $logFile" "HEADER"
Write-Log "========================================" "HEADER"

Write-Host "`nPress any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
