"""
Schema utilities for API schemas.

This module provides utilities for working with API schemas, including:
- HashableSchema: A base class for schemas that can be hashed
"""

from ninja import Schema


class HashableSchema(Schema):
    """
    A schema that can be hashed.
    
    This is useful for caching schema instances or using them as dictionary keys.
    """
    
    def __hash__(self):
        """
        Generate a hash for this schema instance.
        
        Returns:
            int: Hash value
        """
        # Convert to dict and hash the frozenset of items
        dict_items = frozenset(self.dict().items())
        return hash(dict_items)
    
    def __eq__(self, other):
        """
        Check if this schema instance is equal to another.
        
        Args:
            other: Another schema instance
            
        Returns:
            bool: True if equal, False otherwise
        """
        if not isinstance(other, HashableSchema):
            return False
        return self.dict() == other.dict()
