#!/usr/bin/env python3
"""
Deployment Monitor
Checks if the application is deployed and working
"""

import requests
import time
import json

def test_application_health(url):
    """Test if the application is responding"""
    
    print(f"🌐 Testing application at: {url}")
    
    try:
        # Test main page
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Application is responding!")
            print(f"✅ Status Code: {response.status_code}")
            
            # Check if it's serving React content
            if "<!DOCTYPE html>" in response.text:
                print("✅ HTML content detected")
                
                if "React" in response.text or "vite" in response.text.lower():
                    print("✅ React frontend detected!")
                else:
                    print("⚠️  Basic HTML, React might not be built")
            
            return True
            
        else:
            print(f"❌ Application returned status: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Application timeout - might still be starting")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect - application might not be deployed yet")
        return False
    except Exception as e:
        print(f"❌ Error testing application: {e}")
        return False

def test_api_endpoints(base_url):
    """Test key API endpoints"""
    
    print(f"\n🔧 Testing API endpoints...")
    
    endpoints = [
        "/api/auth/signup/",
        "/api/auth/login/",
        "/admin/",
        "/welcome/"
    ]
    
    for endpoint in endpoints:
        url = base_url.rstrip('/') + endpoint
        
        try:
            response = requests.get(url, timeout=5)
            
            if response.status_code in [200, 201, 302, 405]:  # 405 = Method not allowed (expected for POST endpoints)
                print(f"✅ {endpoint}: Working (Status: {response.status_code})")
            else:
                print(f"❌ {endpoint}: Status {response.status_code}")
                
        except Exception as e:
            print(f"❌ {endpoint}: Error - {e}")

def monitor_deployment():
    """Monitor the deployment process"""
    
    print("🚀 DEPLOYMENT MONITORING")
    print("=" * 50)
    
    # Expected URL
    url = "http://payshift-production-east.eba-qadiqdti.us-east-1.elasticbeanstalk.com"
    
    print(f"Target URL: {url}")
    print("Waiting for deployment to complete...")
    
    max_attempts = 20
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        print(f"\n🔍 Attempt {attempt}/{max_attempts}")
        
        if test_application_health(url):
            print("\n🎉 APPLICATION IS LIVE!")
            
            # Test API endpoints
            test_api_endpoints(url)
            
            print(f"\n🎯 NEXT STEPS:")
            print(f"1. Visit: {url}")
            print(f"2. Test signup flow")
            print(f"3. Check EB logs for database configuration")
            print(f"4. Verify all features work")
            
            return True
        
        if attempt < max_attempts:
            print("⏳ Waiting 30 seconds before next check...")
            time.sleep(30)
    
    print(f"\n❌ Application not responding after {max_attempts} attempts")
    print("🔧 Check Elastic Beanstalk console for deployment status")
    return False

if __name__ == '__main__':
    success = monitor_deployment()
    
    if success:
        print("\n✅ Deployment monitoring complete - Application is live!")
    else:
        print("\n❌ Deployment monitoring failed - Check EB console")
