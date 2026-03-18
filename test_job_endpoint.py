#!/usr/bin/env python
"""
Test script to verify the /jobs/{job_id} endpoint works correctly
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payshift.settings')
django.setup()

from jobs.models import Job
from jobs.utils import serialize_job

def test_serialize_job():
    """Test the serialize_job function with a real job"""
    try:
        # Get the first job from the database
        job = Job.objects.first()
        
        if not job:
            print("❌ No jobs found in database")
            return False
        
        print(f"Testing with job ID: {job.id}")
        
        # Try to serialize the job
        serialized = serialize_job(job, include_extra=True, user_id=None)
        
        # Check required fields
        required_fields = ['id', 'title', 'description', 'status', 'start_date', 'end_date']
        missing_fields = [f for f in required_fields if f not in serialized]
        
        if missing_fields:
            print(f"❌ Missing fields: {missing_fields}")
            return False
        
        print("✓ All required fields present")
        print(f"✓ Job serialized successfully: {serialized['title']}")
        print(f"  - ID: {serialized['id']}")
        print(f"  - Status: {serialized['status']}")
        print(f"  - Start Date: {serialized['start_date']}")
        print(f"  - End Date: {serialized['end_date']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Testing Job Serialization ===\n")
    success = test_serialize_job()
    print("\n=== Test Result ===")
    if success:
        print("✓ Test PASSED")
        sys.exit(0)
    else:
        print("✗ Test FAILED")
        sys.exit(1)

