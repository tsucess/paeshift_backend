# Payshift API Documentation

## Job Creation API

### Endpoint: `/jobs/jobs/create-job`

Creates a new job in the system.

#### Method: POST

#### Request Body

```json
{
  "user_id": 1,
  "title": "Electrician Needed",
  "industry": 1,
  "subcategory": "Wiring",
  "applicants_needed": 2,
  "job_type": "single_day",
  "shift_type": "morning",
  "date": "2023-12-25",
  "start_time": "09:00",
  "end_time": "17:00",
  "rate": 25.50,
  "location": "123 Main St, New York, NY 10001"
}
```

#### Field Descriptions

| Field | Type | Required | Description | Format |
|-------|------|----------|-------------|--------|
| user_id | integer | Yes | ID of the user creating the job | |
| title | string | Yes | Job title | |
| industry | integer | Yes | Industry ID | |
| subcategory | string | Yes | Subcategory name or ID | |
| applicants_needed | integer | Yes | Number of workers needed | Minimum: 1 |
| job_type | string | Yes | Type of job | Options: "single_day", "multiple_days", "full_time", "part_time", "temporary" |
| shift_type | string | Yes | Type of shift | Options: "morning", "afternoon", "evening", "night", "flexible" |
| date | string | Yes | Job date | Format: YYYY-MM-DD |
| start_time | string | Yes | Job start time | Formats: "HH:MM", "HH:MM:SS", "HH:MM AM/PM" |
| end_time | string | Yes | Job end time | Formats: "HH:MM", "HH:MM:SS", "HH:MM AM/PM" |
| rate | number | Yes | Hourly rate | Decimal with up to 2 decimal places |
| location | string | Yes | Job location address | |

#### Time Format Support

The API supports multiple time formats:

- 24-hour format without seconds: `"14:30"`
- 24-hour format with seconds: `"14:30:00"`
- 12-hour format without seconds: `"02:30PM"` or `"02:30 PM"`
- 12-hour format with seconds: `"02:30:00PM"` or `"02:30:00 PM"`

#### Date Format Support

The API supports multiple date formats:

- ISO format: `"2023-12-25"` (YYYY-MM-DD)
- Day/Month/Year: `"25/12/2023"` (DD/MM/YYYY)
- Month/Day/Year: `"12/25/2023"` (MM/DD/YYYY)
- Day-Month-Year: `"25-12-2023"` (DD-MM-YYYY)
- Month-Day-Year: `"12-25-2023"` (MM-DD-YYYY)

#### Success Response

```json
{
  "success": true,
  "job_id": 123,
  "title": "Electrician Needed",
  "date": "2023-12-25",
  "start_time": "09:00 AM",
  "end_time": "05:00 PM",
  "duration_hours": 8.0,
  "rate": "25.50",
  "total_amount": "204.00",
  "service_fee": "30.60",
  "location": "123 Main St, New York, NY 10001",
  "message": "Job created successfully. Geocoding in progress."
}
```

#### Error Responses

**Validation Error**

```json
{
  "error": "Validation error",
  "details": {
    "start_time": "Invalid time format: '9:00'. Valid formats are: HH:MM (24-hour without seconds), HH:MM:SS (24-hour with seconds), HH:MMAM/PM (12-hour without seconds), HH:MM AM/PM (12-hour with space)"
  },
  "message": "Please correct the errors and try again."
}
```

**User Not Found**

```json
{
  "error": "User not found",
  "details": "No user exists with ID 999",
  "resolution": "Please provide a valid user ID"
}
```

**Server Error**

```json
{
  "error": "Server error",
  "message": "An unexpected error occurred while creating the job",
  "reference": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Geocoding API

### Endpoint: `/jobs/geocode/`

Geocodes an address to latitude and longitude coordinates.

#### Method: POST

#### Request Body

```json
{
  "address": "123 Main St, New York, NY 10001"
}
```

#### Success Response

```json
{
  "success": true,
  "latitude": 40.7128,
  "longitude": -74.0060,
  "accuracy": "ROOFTOP",
  "provider": "google",
  "formatted_address": "123 Main St, New York, NY 10001, USA"
}
```

#### Error Response

```json
{
  "success": false,
  "error": "Address too short: '123'",
  "latitude": null,
  "longitude": null,
  "provider": null
}
```

## Notes

- All monetary values are returned as strings to preserve decimal precision
- Geocoding is performed asynchronously for job creation to improve performance
- The service fee is calculated as 15% of the total amount (rate × duration)
- Time values are stored in 24-hour format but can be displayed in 12-hour format
- All API responses include appropriate HTTP status codes
