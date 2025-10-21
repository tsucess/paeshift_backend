# Simulation Commands for Payshift

This document provides an overview of the simulation commands available for testing the Payshift application.

## Overview

The simulation commands allow you to create test data and simulate various workflows in the Payshift application. These commands are useful for:

1. Testing application functionality
2. Populating the database with realistic test data
3. Identifying potential issues or bottlenecks
4. Demonstrating the application workflow

## Available Commands

### 1. Admin Registration Simulation

Simulates the registration of admin users with different roles.

```bash
python manage.py simulate_admin_registration --count=3 --password=adminpass123
```

**Parameters:**
- `--count`: Number of admin users to create (default: 3)
- `--password`: Password for admin users (default: adminpass123)

**Output:**
- List of created admin users with their roles

### 2. Client Registration Simulation

Simulates the registration of client users with profiles.

```bash
python manage.py simulate_client_registration --count=10 --password=clientpass123
```

**Parameters:**
- `--count`: Number of client users to create (default: 10)
- `--password`: Password for client users (default: clientpass123)

**Output:**
- List of created client users with their profile information

### 3. Applicant Registration Simulation

Simulates the registration of applicant users with profiles and location history.

```bash
python manage.py simulate_applicant_registration --count=20 --password=applicantpass123 --with-location
```

**Parameters:**
- `--count`: Number of applicant users to create (default: 20)
- `--password`: Password for applicant users (default: applicantpass123)
- `--with-location`: Create location history for applicants (flag)

**Output:**
- List of created applicant users with their profile information

### 4. Job Creation Simulation

Simulates the creation of jobs by client users.

```bash
python manage.py simulate_job_creation --client-count=5 --jobs-per-client=3 --use-existing-clients
```

**Parameters:**
- `--client-count`: Number of client users to create or use (default: 5)
- `--jobs-per-client`: Number of jobs per client (default: 3)
- `--use-existing-clients`: Use existing client users instead of creating new ones (flag)

**Output:**
- List of created jobs with their details

### 5. Job Application Simulation

Simulates job applications from applicants to jobs.

```bash
python manage.py simulate_job_application --applicant-count=10 --applications-per-applicant=3 --use-existing-applicants
```

**Parameters:**
- `--applicant-count`: Number of applicant users to create or use (default: 10)
- `--applications-per-applicant`: Number of applications per applicant (default: 3)
- `--use-existing-applicants`: Use existing applicant users instead of creating new ones (flag)

**Output:**
- List of created job applications

### 6. Payment Processing Simulation

Simulates payment processing for jobs, including webhook callbacks.

```bash
python manage.py simulate_payment_processing --count=10 --payment-method=both --success-rate=0.8
```

**Parameters:**
- `--count`: Number of payments to process (default: 10)
- `--payment-method`: Payment method to simulate (choices: paystack, flutterwave, both; default: both)
- `--success-rate`: Success rate for payments (0.0-1.0, default: 0.8)

**Output:**
- List of processed payments with their status

### 7. Dispute Management Simulation

Simulates the creation and resolution of disputes between clients and applicants.

```bash
python manage.py simulate_dispute_management --count=5 --resolution-rate=1.0 --client-favor-rate=0.5
```

**Parameters:**
- `--count`: Number of disputes to create (default: 5)
- `--resolution-rate`: Rate at which disputes are resolved (0.0-1.0, default: 0.7)
- `--client-favor-rate`: Rate at which resolutions favor the client (0.0-1.0, default: 0.5)

**Output:**
- List of created disputes with their status and resolution details

### 8. Location Streams Simulation

Simulates location data for users, including home addresses, job locations, and live location history.

```bash
python manage.py simulate_location_streams --user-count=10 --updates-per-user=5 --update-home-address --create-location-history --update-job-locations
```

**Parameters:**
- `--user-count`: Number of users to update locations for (default: 10)
- `--updates-per-user`: Number of location updates per user (default: 5)
- `--update-home-address`: Update home addresses in user profiles (flag)
- `--create-location-history`: Create location history entries (flag)
- `--update-job-locations`: Update job locations (flag)

**Output:**
- List of updated home addresses, location history entries, and job locations

### 9. Full End-to-End Simulation

Runs all the individual simulations in sequence to create a complete test environment.

```bash
python manage.py run_full_simulation --admin-count=3 --client-count=10 --applicant-count=20 --jobs-per-client=3 --applications-per-applicant=3 --payment-success-rate=0.8
```

**Parameters:**
- `--admin-count`: Number of admin users to create (default: 3)
- `--client-count`: Number of client users to create (default: 10)
- `--applicant-count`: Number of applicant users to create (default: 20)
- `--jobs-per-client`: Number of jobs per client (default: 3)
- `--applications-per-applicant`: Number of applications per applicant (default: 3)
- `--payment-success-rate`: Success rate for payments (0.0-1.0, default: 0.8)
- `--output-file`: Output file for simulation results (default: simulation_results_TIMESTAMP.json)

**Output:**
- Detailed simulation results with timing information
- Analysis of potential issues
- Summary of created entities

### 10. Test Webhook

Tests the payment webhook implementation without requiring an actual payment gateway.

```bash
python manage.py test_webhook --payment-method=paystack --success --reference=TEST_12345678
```

**Parameters:**
- `--payment-method`: Payment method to simulate (choices: paystack, flutterwave; default: paystack)
- `--success`: Simulate a successful payment (flag)
- `--reference`: Payment reference to use (default: auto-generated)

**Output:**
- Response status code and content from the webhook endpoint

### 11. Run Simulations (Simulation Manager)

Provides a unified interface for running one or more simulations with configurable parameters.

```bash
# List available simulations
python manage.py run_simulations --list

# Run specific simulations
python manage.py run_simulations --simulations=admin,client,job

# Run all simulations with custom parameters
python manage.py run_simulations --admin-count=2 --client-count=5 --applicant-count=10 --save-results
```

**Parameters:**
- `--simulations`: Comma-separated list of simulations to run (e.g., admin,client,job)
- `--list`: List available simulations (flag)
- `--save-results`: Save simulation results to a JSON file (flag)
- `--admin-count`: Number of admin users to create (default: 1)
- `--client-count`: Number of client users to create (default: 2)
- `--applicant-count`: Number of applicant users to create (default: 5)
- `--jobs-per-client`: Number of jobs per client (default: 3)
- `--applications-per-applicant`: Number of job applications per applicant (default: 2)
- `--payment-success-rate`: Success rate for payment processing (0.0-1.0, default: 0.8)
- `--password`: Password for created users (default: password123)

**Output:**
- Summary of each simulation run
- Overall execution statistics
- Path to results file if --save-results is used

## Error Handling

All simulation commands include comprehensive error handling:

1. **Transaction Isolation**: Database operations are wrapped in transactions
2. **Error Logging**: Errors are logged to `simulation.log`
3. **Error Collection**: Errors are collected and reported in the command output
4. **Graceful Degradation**: Commands continue running even if some operations fail

## Logging

Simulation activities are logged to `simulation.log`. You can monitor this file for debugging and auditing purposes.

## Extending

To add a new simulation command:

1. Create a new file in `jobs/management/commands/`
2. Implement the `Command` class with `add_arguments` and `handle` methods
3. Use the existing commands as templates for structure and error handling

## Best Practices

When running simulations:

1. **Start Small**: Begin with small counts to verify functionality
2. **Use Existing Data**: Use the `--use-existing-*` flags to build on previous simulations
3. **Monitor Logs**: Keep an eye on the log files for errors or warnings
4. **Check Database**: Verify the created data in the admin interface
5. **Clean Up**: Consider cleaning up test data after simulations if needed
