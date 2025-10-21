#!/usr/bin/env python
"""
Check production deployment health
"""
import requests
import json

def check_production_health():
    """Check if production deployment is healthy"""
    
    # Possible production URLs
    possible_urls = [
        "http://payshift-production.us-west-2.elasticbeanstalk.com",
        "http://paeshift-env.us-west-2.elasticbeanstalk.com", 
        "http://paeshift.us-west-2.elasticbeanstalk.com",
    ]
    
    print("🏥 Production Health Check")
    print("=" * 50)
    
    working_url = None
    
    for url in possible_urls:
        print(f"\n🔍 Testing: {url}")
        
        try:
            # Test main page
            response = requests.get(f"{url}/", timeout=15)
            print(f"   📄 Main page: {response.status_code}")
            
            if response.status_code in [200, 301, 302]:
                working_url = url
                print(f"   ✅ Main page accessible")
                
                # Test API endpoints
                try:
                    api_response = requests.get(f"{url}/accountsapp/", timeout=10)
                    print(f"   📡 API endpoint: {api_response.status_code}")
                except:
                    print(f"   ⚠️ API endpoint not accessible")
                
                # Test admin
                try:
                    admin_response = requests.get(f"{url}/admin/", timeout=10)
                    print(f"   🔧 Admin page: {admin_response.status_code}")
                except:
                    print(f"   ⚠️ Admin page not accessible")
                
                break
            else:
                print(f"   ❌ Not accessible ({response.status_code})")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection failed")
        except requests.exceptions.Timeout:
            print(f"   ❌ Timeout")
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    if working_url:
        print(f"\n🎉 Production deployment is healthy!")
        print(f"🌐 Working URL: {working_url}")
        return working_url
    else:
        print(f"\n❌ No working production URL found")
        print(f"💡 Make sure your Elastic Beanstalk environment is running")
        return None

if __name__ == "__main__":
    working_url = check_production_health()
    
    if working_url:
        print(f"\n🚀 Ready to test signup at: {working_url}/accountsapp/signup")
    else:
        print(f"\n🔧 Need to deploy or check Elastic Beanstalk environment")
