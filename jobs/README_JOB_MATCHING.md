# Concurrent Job Matching System with User Activity Monitoring

This system provides a sophisticated job matching algorithm that uses multiple weighted factors including user activity to match jobs to users and users to jobs. It leverages concurrent processing for optimal performance.

## Features

- **Multi-factor matching**: Location, skills, activity, rating, and experience
- **User activity tracking**: Monitors user engagement for better matches
- **Concurrent processing**: Handles large datasets efficiently
- **Gamification integration**: Uses engagement metrics for ranking
- **Comprehensive testing**: Unit, integration, and performance tests

## Components

1. **Job Matching Utility** (`jobs/job_matching_utils.py`)
   - Core matching algorithm with weighted factors
   - Concurrent processing with ThreadPoolExecutor
   - Distance calculation using Haversine formula

2. **User Activity Tracking** (`accounts/user_activity.py`)
   - Login and session tracking
   - Job view and application monitoring
   - Engagement scoring system
   - Integration with gamification

3. **Simulation System** (`jobs/management/commands/job_matching_simulation.py`)
   - Test data generation
   - Performance benchmarking
   - Match quality analysis

4. **Test Suite** (`jobs/tests/test_job_matching.py`)
   - Unit tests for scoring functions
   - Integration tests for matching pipeline
   - Performance tests for concurrent processing

## Usage

### Running the Simulation

```bash
# Basic simulation
python manage.py job_matching_simulation

# Custom parameters
python manage.py job_matching_simulation --users=50 --jobs=100 --iterations=5 --batch-size=20 --save-results
```

### Using the Matching API

```python
from jobs.job_matching_utils import match_jobs_to_users, match_users_to_jobs

# Match jobs to users
job_matches = match_jobs_to_users(jobs_list, users_list)

# Match users to jobs
user_matches = match_users_to_jobs(users_list, jobs_list)
```

### Tracking User Activity

```python
from accounts.user_activity import track_user_login, track_job_view, get_user_engagement_score

# Track user login
track_user_login(user, ip_address='127.0.0.1')

# Track job view
track_job_view(user, job_id=123)

# Get engagement score
score = get_user_engagement_score(user)
```

## Implementation Details

### Matching Factors and Weights

| Factor | Weight | Description |
|--------|--------|-------------|
| Location | 35% | Proximity between job and user locations |
| Skills | 25% | Industry and subcategory alignment |
| Activity | 15% | User engagement on the platform |
| Rating | 15% | Average rating from reviews |
| Experience | 10% | Number of completed jobs |

### Concurrency Model

The system uses Python's `concurrent.futures` module with `ThreadPoolExecutor` to process matches in parallel:

1. Jobs are divided into batches
2. Each batch is processed concurrently
3. Results are combined and sorted by match quality

This approach significantly improves performance for large datasets.

## Testing

Run the tests with:

```bash
pytest jobs/tests/test_job_matching.py -v
```

## Documentation

For more detailed information, see:

- [Job Matching System Documentation](docs/job_matching_system.md)
- [API Reference](docs/api_reference.md)
- [Performance Benchmarks](docs/performance_benchmarks.md)
