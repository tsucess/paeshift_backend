# API Documentation Setup Guide

## Overview

This guide explains how to set up and generate API documentation for Paeshift using **drf-spectacular**, which generates OpenAPI 3.0 schemas and provides Swagger UI and ReDoc interfaces.

---

## Installation

### Step 1: Install drf-spectacular

```bash
pip install drf-spectacular
```

### Step 2: Update requirements.txt

```bash
pip freeze > requirements.txt
```

---

## Configuration

### Step 1: Add to INSTALLED_APPS

Edit `paeshift-recover/payshift/settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'drf_spectacular',
]
```

### Step 2: Configure REST Framework

Add to `settings.py`:

```python
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Paeshift API',
    'DESCRIPTION': 'Gig Economy Platform API',
    'VERSION': '1.0.0',
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    'SERVERS': [
        {'url': 'http://localhost:8000', 'description': 'Development'},
        {'url': 'https://api.paeshift.com', 'description': 'Production'},
    ],
    'CONTACT': {
        'name': 'Paeshift Support',
        'email': 'support@paeshift.com',
    },
    'LICENSE': {
        'name': 'MIT',
    },
    'TAGS': [
        {'name': 'Auth', 'description': 'Authentication endpoints'},
        {'name': 'Jobs', 'description': 'Job management endpoints'},
        {'name': 'Applications', 'description': 'Job application endpoints'},
        {'name': 'Payments', 'description': 'Payment processing endpoints'},
        {'name': 'Ratings', 'description': 'Rating and feedback endpoints'},
        {'name': 'Notifications', 'description': 'Notification endpoints'},
        {'name': 'Chat', 'description': 'Real-time chat endpoints'},
        {'name': 'Gamification', 'description': 'Gamification endpoints'},
    ],
}
```

### Step 3: Add URLs

Edit `paeshift-recover/payshift/urls.py`:

```python
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    # ... existing patterns ...
    
    # API Schema
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    
    # Swagger UI
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # ReDoc
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
```

---

## Documenting Endpoints

### Basic Endpoint Documentation

```python
from ninja import Router
from .schemas import InputSchema, OutputSchema

router = Router(tags=["Jobs"])

@router.post(
    "/create",
    response={201: OutputSchema, 400: ErrorSchema},
    description="Create a new job posting",
    summary="Create Job"
)
def create_job(request, payload: InputSchema):
    """
    Create a new job posting.
    
    This endpoint allows clients to create new job postings.
    
    Args:
        payload: Job creation data
    
    Returns:
        201: Created job object
        400: Validation error
    
    Raises:
        ValidationError: If input data is invalid
    """
    # Implementation
    pass
```

### Schema Documentation

```python
from pydantic import BaseModel, Field
from typing import Optional

class JobCreateSchema(BaseModel):
    """Schema for creating a job."""
    
    title: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Job title"
    )
    description: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Detailed job description"
    )
    budget: float = Field(
        ...,
        gt=0,
        description="Job budget in USD"
    )
    location: str = Field(
        ...,
        description="Job location"
    )
    job_type: str = Field(
        ...,
        description="Type of job (single_day, multiple_days)"
    )
    required_skills: Optional[list] = Field(
        None,
        description="List of required skills"
    )
    
    class Config:
        from_attributes = True
        example = {
            "title": "Web Development Project",
            "description": "Build a responsive website...",
            "budget": 500.00,
            "location": "Remote",
            "job_type": "single_day",
            "required_skills": ["React", "Node.js"]
        }
```

---

## Accessing Documentation

After setup, access the documentation at:

- **Swagger UI**: `http://localhost:8000/api/docs/`
- **ReDoc**: `http://localhost:8000/api/redoc/`
- **OpenAPI Schema**: `http://localhost:8000/api/schema/`

---

## Best Practices

### 1. Use Descriptive Names
```python
@router.get("/jobs/{job_id}", description="Retrieve job details")
def get_job(request, job_id: int):
    pass
```

### 2. Document Response Codes
```python
@router.post(
    "/create",
    response={
        201: JobSchema,
        400: ErrorSchema,
        401: ErrorSchema,
        403: ErrorSchema,
    }
)
def create_job(request, payload: JobCreateSchema):
    pass
```

### 3. Use Field Examples
```python
class JobSchema(BaseModel):
    id: int = Field(..., example=1)
    title: str = Field(..., example="Web Developer")
    budget: float = Field(..., example=500.00)
```

### 4. Document Errors
```python
class ErrorSchema(BaseModel):
    """Error response schema."""
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Machine-readable error code")
    details: dict = Field(default={}, description="Additional error details")
```

---

## Generating Schema

### Manual Generation

```bash
python manage.py spectacular --file schema.yml
```

### Automated Generation

Add to CI/CD pipeline to generate schema on each deployment.

---

## Integration with Frontend

### Using OpenAPI Schema

```javascript
// In frontend, use the schema to generate API client
import SwaggerClient from 'swagger-client';

const client = await SwaggerClient.build({
    url: 'http://localhost:8000/api/schema/',
    requestInterceptor: (request) => {
        request.headers.Authorization = `Bearer ${token}`;
        return request;
    }
});
```

---

## Troubleshooting

### Issue: Schema not generating

**Solution**: Ensure all routers are properly registered in `urls.py`

### Issue: Endpoints not appearing in docs

**Solution**: Add `tags` parameter to endpoint decorator

### Issue: Authentication not working in Swagger UI

**Solution**: Configure authentication in `SPECTACULAR_SETTINGS`:

```python
SPECTACULAR_SETTINGS = {
    'SECURITY': [
        {
            'bearerAuth': []
        }
    ],
    'SECURITY_DEFINITIONS': {
        'bearerAuth': {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }
    }
}
```

---

## Next Steps

1. ✅ Install drf-spectacular
2. ✅ Configure settings
3. ✅ Add URLs
4. ✅ Document all endpoints
5. ✅ Test documentation
6. ✅ Deploy to production

---

**Status**: Ready for Implementation  
**Estimated Time**: 2-3 hours


