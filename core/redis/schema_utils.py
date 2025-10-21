"""
Utility module for Django Ninja schema classes.
"""
from ninja import Schema
from pydantic import ConfigDict


class HashableSchema(Schema):
    """
    Base schema class that is hashable (can be used as dictionary keys).
    
    All response schemas used in API endpoints should inherit from this class
    to avoid "unhashable type" errors in Django Ninja.
    
    Example:
        ```python
        from core.schema_utils import HashableSchema
        
        class MyResponseSchema(HashableSchema):
            message: str
            status: str
        ```
    """
    model_config = ConfigDict(frozen=True)
