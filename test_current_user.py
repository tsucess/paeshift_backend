#!/usr/bin/env python3
"""
Test script to check current user authentication
"""
import requests
import json

def test_current_user():
    print("🔍 Testing Current User Authentication")
    print("=" * 50)
    
    # Get token from localStorage (you'll need to copy this from browser)
    print("📋 To test your current authentication:")
    print("1. Open browser console (F12)")
    print("2. Type: localStorage.getItem('access_token')")
    print("3. Copy the token and paste it below")
    print()
    
    token = input("🔑 Paste your access token here: ").strip()
    
    if not token:
        print("❌ No token provided")
        return
    
    # Test whoami endpoint
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        print(f"🌐 Testing whoami endpoint...")
        response = requests.get('http://127.0.0.1:8000/accounts/whoami/', headers=headers)
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Authentication successful!")
            print(f"👤 Current User: {data.get('username')} (ID: {data.get('id')})")
            print(f"🎭 Role: {data.get('role')}")
            print(f"📧 Email: {data.get('email')}")
            
            # Check if this user owns any jobs
            print("\n🔍 Checking jobs owned by this user...")
            jobs_response = requests.get('http://127.0.0.1:8000/jobs/alljobs', headers=headers)
            
            if jobs_response.status_code == 200:
                jobs_data = jobs_response.json()
                user_jobs = [job for job in jobs_data.get('jobs', []) if job.get('client_id') == data.get('id')]
                
                print(f"📊 Total jobs in system: {len(jobs_data.get('jobs', []))}")
                print(f"💼 Jobs owned by you: {len(user_jobs)}")
                
                if user_jobs:
                    print("\n🎯 Your jobs that can be started:")
                    for job in user_jobs:
                        if job.get('status') == 'upcoming':
                            accepted_count = job.get('accepted_applicants_count', 0)
                            can_start = accepted_count > 0
                            status_icon = "✅" if can_start else "❌"
                            print(f"   {status_icon} {job.get('title')} (ID: {job.get('id')})")
                            print(f"      Status: {job.get('status')}")
                            print(f"      Accepted applicants: {accepted_count}")
                            if can_start:
                                print(f"      🚀 Ready to start shift!")
                            else:
                                print(f"      ⏳ Need to accept applicants first")
                            print()
                else:
                    print("❌ You don't own any jobs")
                    print("💡 The jobs in the system are owned by user ID 2 ('user')")
                    print("💡 You need to login as the 'user' account to start those shifts")
            
        else:
            print("❌ Authentication failed!")
            print(f"📄 Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure Django server is running at http://127.0.0.1:8000/")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_current_user()
