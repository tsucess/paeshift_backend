"""
Django Python 3.14 Compatibility Fix

This module patches Django's template context to work with Python 3.14.
The issue is that Django's Context class uses __copy__ which doesn't work
properly with Python 3.14's object model.

This should be imported early in the Django startup process.
"""

import sys
from django.template.context import Context

# Only apply the fix for Python 3.14+
if sys.version_info >= (3, 14):
    original_copy = Context.__copy__
    
    def patched_copy(self):
        """Patched __copy__ method that works with Python 3.14"""
        try:
            # Try the original method first
            return original_copy(self)
        except AttributeError:
            # If it fails, create a new context manually
            new_context = Context()
            new_context.dicts = self.dicts[:]
            return new_context
    
    Context.__copy__ = patched_copy

