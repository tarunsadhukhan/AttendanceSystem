"""
Test POST /onboarding/register-face endpoint
"""
import requests
import json
import base64

# Configuration
BASE_URL = "http://192.168.0.223:5051"
TEST_EMP_CODE = "13177"  # Change to a valid emp_code from your database

print("=" * 70)
print("Testing POST /onboarding/register-face")
print("=" * 70)

# Step 1: First, test if employee exists
print("\n1. Checking if employee exists...")
print("-" * 70)

emp_url = f"{BASE_URL}/onboarding/employee/{TEST_EMP_CODE}"
print(f"GET {emp_url}")

try:
    emp_response = requests.get(emp_url, timeout=5)
    print(f"Status: {emp_response.status_code}")
    
    if emp_response.status_code == 200:
        emp_data = emp_response.json()
        print(f"Response: {json.dumps(emp_data, indent=2)}")
        
        if emp_data.get('status') == 'success':
            print(f"\n✅ Employee found: {emp_data.get('name')}")
            print(f"   Face count: {emp_data.get('face_count')}/3")
            print(f"   Can register: {emp_data.get('can_register')}")
            
            # Step 2: Create a test image (small red square)
            if emp_data.get('can_register'):
                print("\n2. Testing face registration...")
                print("-" * 70)
                
                # Create a simple test image (1x1 red pixel PNG)
                # This is just for testing the API, not a real face photo
                test_image_base64 = (
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
                )
                
                register_url = f"{BASE_URL}/onboarding/register-face"
                payload = {
                    "emp_code": TEST_EMP_CODE,
                    "face_image": test_image_base64
                }
                
                print(f"POST {register_url}")
                print(f"Payload:")
                print(f"  emp_code: {TEST_EMP_CODE}")
                print(f"  face_image: [base64 data, {len(test_image_base64)} chars]")
                
                try:
                    register_response = requests.post(
                        register_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                    
                    print(f"\nStatus: {register_response.status_code}")
                    print(f"Response: {json.dumps(register_response.json(), indent=2)}")
                    
                    if register_response.status_code == 200:
                        print("\n✅ API endpoint is working!")
                        print("   Note: Used test image, not a real face")
                        print("   Real face images from mobile app should work")
                    else:
                        print("\n❌ Registration failed")
                        
                except requests.exceptions.Timeout:
                    print("\n❌ Request timed out")
                    print("   Server may be slow or not responding")
                except requests.exceptions.ConnectionError:
                    print("\n❌ Connection error")
                    print("   Server may not be running on 192.168.0.113:5051")
                except Exception as e:
                    print(f"\n❌ Error: {str(e)}")
            else:
                print("\n⚠️  Cannot register - maximum faces reached")
        else:
            print(f"\n❌ Employee not found")
    else:
        print(f"❌ HTTP {emp_response.status_code}")
        print(f"Response: {emp_response.text}")
        
except requests.exceptions.Timeout:
    print("❌ Request timed out")
    print("   Check if server is running: cd E:\\sjm\\AttendanceSystem && python app.py")
except requests.exceptions.ConnectionError:
    print("❌ Connection refused")
    print("   Server is not running or wrong IP/port")
    print("   Action: Start server with: cd E:\\sjm\\AttendanceSystem && python app.py")
except Exception as e:
    print(f"❌ Error: {str(e)}")

print("\n" + "=" * 70)
print("Test Complete")
print("=" * 70)

# Troubleshooting tips
print("\n📋 TROUBLESHOOTING:")
print("   1. Ensure backend server is running:")
print("      cd E:\\sjm\\AttendanceSystem")
print("      python app.py")
print("")
print("   2. Verify server IP and port:")
print("      Server should be on: 192.168.0.223:5051")
print("")
print("   3. Check employee exists:")
print(f"      emp_code '{TEST_EMP_CODE}' must exist in hrms_ed_official_details")
print("")
print("   4. For real face registration:")
print("      Use the mobile app to capture actual face photos")

