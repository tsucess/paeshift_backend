# Core Utilities

This directory contains core utilities used throughout the application.

## Schema Utils

The `schema_utils.py` module provides utilities for working with Django Ninja schemas.

### HashableSchema

The `HashableSchema` class is a base class for all response schemas used in API endpoints. It makes schemas hashable, which is required for Django Ninja's internal implementation.

```python
from core.schema_utils import HashableSchema

class MyResponseSchema(HashableSchema):
    message: str
    status: str
```

#### Why HashableSchema is Needed

Django Ninja uses schema classes as dictionary keys in its internal implementation. In Python, to be used as a dictionary key, an object must be hashable (have a `__hash__` method).

The `HashableSchema` class adds the `frozen=True` configuration to the schema, which:
1. Makes the model immutable (attributes can't be changed after creation)
2. Automatically adds a `__hash__` method to the class

This prevents errors like:
```
TypeError: unhashable type: 'MessageOut'
```

#### Usage Guidelines

- Use `HashableSchema` for all response schemas in API endpoints
- Regular input schemas that aren't used as responses don't need to be hashable
- If you see "unhashable type" errors in your API endpoints, make sure the response schema inherits from `HashableSchema`

#### Implementation Details

The `HashableSchema` class is implemented using Pydantic's `ConfigDict` with `frozen=True`:

```python
class HashableSchema(Schema):
    """Base schema class that is hashable (can be used as dictionary keys)"""
    model_config = ConfigDict(frozen=True)
```

This is a standard approach for making Pydantic models hashable and is much cleaner than creating a custom utility function.
