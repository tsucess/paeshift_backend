#!/usr/bin/env python
"""
Fix OTP verification with proper API format
"""
import requests
import json

def verify_otp_with_correct_format():
    """Test OTP verification with the correct API format"""
    
    base_url = "http://payshift-production.eba-qadiqdti.us-west-2.elasticbeanstalk.com"
    verify_url = f"{base_url}/accounts/otp/verify"
    
    print("🔧 OTP Verification Fix")
    print("=" * 50)
    
    # Get the actual OTP code from user
    print("📧 A new OTP was just sent to kfabbzmusic@gmail.com")
    print("🔔 Please check your email for the latest OTP code")
    otp_code = input("\nEnter the NEW OTP code you just received: ").strip()
    
    if not otp_code:
        print("❌ No OTP code provided")
        return False
    
    if len(otp_code) != 6 or not otp_code.isdigit():
        print("⚠️ Warning: OTP should be 6 digits, but proceeding anyway...")
    
    # Based on the API schema, try the correct format
    payload = {
        "email": "kfabbzmusic@gmail.com",
        "code": otp_code,
        "type": "registration",
        "device_info": {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "ip_address": "127.0.0.1",
            "device_name": "Chrome Browser",
            "platform": "Windows"
        }
    }
    
    print(f"\n📤 Sending verification request...")
    print(f"📧 Email: {payload['email']}")
    print(f"🔐 Code: {payload['code']}")
    print(f"🎭 Type: {payload['type']}")
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Origin': base_url,
            'Referer': f"{base_url}/verify"
        }
        
        response = requests.post(verify_url, json=payload, headers=headers, timeout=30)
        
        print(f"\n📥 Response Status: {response.status_code}")
        
        try:
            response_data = response.json()
            print(f"📄 Response Data:")
            print(json.dumps(response_data, indent=2))
        except:
            print(f"📄 Response Text: {response.text}")
            response_data = {"error": "Invalid JSON"}
        
        if response.status_code == 200:
            print("\n🎉 OTP VERIFICATION SUCCESSFUL!")
            print("✅ User account is now verified")
            print("✅ User can now login to the dashboard")
            
            # Check if there's a redirect URL or token
            if isinstance(response_data, dict):
                if 'redirect_url' in response_data:
                    print(f"🔗 Redirect URL: {response_data['redirect_url']}")
                if 'token' in response_data:
                    print(f"🔑 Auth Token: {response_data['token'][:20]}...")
                if 'user' in response_data:
                    print(f"👤 User Info: {response_data['user']}")
            
            return True
            
        elif response.status_code == 400:
            print(f"\n❌ Verification Failed (400 Bad Request)")
            if isinstance(response_data, dict) and 'message' in response_data:
                print(f"💬 Error: {response_data['message']}")
                
                if "expired" in response_data['message'].lower():
                    print("⏰ OTP has expired - request a new one")
                elif "invalid" in response_data['message'].lower():
                    print("🔐 OTP code is incorrect - check your email")
                elif "not found" in response_data['message'].lower():
                    print("👤 User or OTP not found - may need to signup again")
            
            return False
            
        elif response.status_code == 401:
            print(f"\n❌ Unauthorized (401)")
            print("🔐 OTP code is invalid or expired")
            return False
            
        else:
            print(f"\n❌ Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during verification: {str(e)}")
        return False

def request_fresh_otp():
    """Request a fresh OTP for the user"""
    
    base_url = "http://payshift-production.eba-qadiqdti.us-west-2.elasticbeanstalk.com"
    otp_url = f"{base_url}/accounts/otp/request"
    
    print(f"\n🔄 Requesting Fresh OTP")
    print("-" * 30)
    
    payload = {
        "email": "kfabbzmusic@gmail.com",
        "type": "registration"
    }
    
    try:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = requests.post(otp_url, json=payload, headers=headers, timeout=30)
        
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Fresh OTP sent!")
            print("🔔 Check kfabbzmusic@gmail.com for new OTP")
            return True
        else:
            print("❌ Failed to send fresh OTP")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def main():
    """Main function"""
    print("🔧 FIXING OTP VERIFICATION ISSUE")
    print("📧 Email: kfabbzmusic@gmail.com")
    print("=" * 60)
    
    # First, request a fresh OTP to be sure
    print("🔄 Step 1: Requesting fresh OTP to ensure we have a valid one...")
    fresh_otp_sent = request_fresh_otp()
    
    if fresh_otp_sent:
        print("\n✅ Fresh OTP sent successfully!")
        print("⏰ Please wait a moment for the email to arrive...")
        input("Press Enter when you have the new OTP code...")
        
        # Now try verification
        print("\n🔧 Step 2: Testing verification with fresh OTP...")
        verification_success = verify_otp_with_correct_format()
        
        if verification_success:
            print("\n🎉 SUCCESS! OTP verification is now working!")
            print("🚀 User can now access the dashboard")
        else:
            print("\n❌ Verification still failed")
            print("💡 Possible issues:")
            print("   - OTP code was typed incorrectly")
            print("   - Email delay - OTP not received yet")
            print("   - API format still not correct")
    else:
        print("\n❌ Could not send fresh OTP")
        print("🔧 Check the API endpoint and user status")

if __name__ == "__main__":
    main()
