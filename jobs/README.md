# Jobs Module

This module handles job creation, management, and geocoding functionality for the Payshift platform.

## Enhanced Geocoding System

The geocoding system has been improved with the following features:

1. **Redis-based Caching**: Geocoding results are cached in Redis to reduce API calls and improve performance.
2. **Multiple Provider Support**: The system now supports multiple geocoding providers (Google Maps, Nominatim, Mapbox) with automatic fallback.
3. **Improved Error Handling**: Detailed error messages and validation for better debugging.
4. **Consistent Coordinate Precision**: All coordinates are stored with 6 decimal places for consistency.

### Configuration

Add the following settings to your `.env` file:

```
# Redis settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password_if_needed
REDIS_GEOCODE_DB=1

# Geocoding settings
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
MAPBOX_API_KEY=your_mapbox_api_key
GEOCODING_TIMEOUT=15
GEOCODING_PROVIDERS=google,nominatim,mapbox
GEOCODING_MAX_RETRIES=3
```

### Usage

#### Direct Geocoding

```python
from jobs.geocoding import geocode_address

# Geocode an address
result = geocode_address("123 Main St, New York, NY 10001")

if result["success"]:
    latitude = result["latitude"]
    longitude = result["longitude"]
    provider = result["provider"]  # Which provider returned the result
    print(f"Coordinates: {latitude}, {longitude} (via {provider})")
else:
    print(f"Geocoding failed: {result['error']}")
```

#### Job Creation with Geocoding

When creating a job, the geocoding is handled automatically:

```python
from jobs.models import Job

# Create a job
job = Job.objects.create(
    title="Electrician Needed",
    location="123 Main St, New York, NY 10001",
    # ... other fields
)

# The geocoding will be performed asynchronously
# and the job will be updated with the coordinates
```

### Cache Management

To manage the geocoding cache:

```python
from jobs.geocoding_cache import clear_geocoding_cache, get_cache_stats

# Get cache statistics
stats = get_cache_stats()
print(f"Cache entries: {stats['total_entries']}")
print(f"Memory used: {stats['memory_used_bytes']} bytes")

# Clear the cache if needed
clear_geocoding_cache()
```

## Time Format Validation

The system now supports multiple time formats:

- 24-hour format without seconds: `"14:30"`
- 24-hour format with seconds: `"14:30:00"`
- 12-hour format without seconds: `"02:30PM"` or `"02:30 PM"`
- 12-hour format with seconds: `"02:30:00PM"` or `"02:30:00 PM"`

And multiple date formats:

- ISO format: `"2023-12-25"` (YYYY-MM-DD)
- Day/Month/Year: `"25/12/2023"` (DD/MM/YYYY)
- Month/Day/Year: `"12/25/2023"` (MM/DD/YYYY)
- Day-Month-Year: `"25-12-2023"` (DD-MM-YYYY)
- Month-Day-Year: `"12-25-2023"` (MM-DD-YYYY)

## API Documentation

For detailed API documentation, see [api_docs.md](api_docs.md).
