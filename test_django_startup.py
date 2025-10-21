#!/usr/bin/env python
"""
Simple test script to verify Django can start up without errors.
"""
import os
import sys
import django

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payshift.settings')

try:
    print("Attempting to initialize Django...")
    django.setup()
    print("✅ Django initialized successfully!")
    print("✅ All checks passed!")
    sys.exit(0)
except Exception as e:
    print(f"❌ Error initializing Django: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

