"""
Test script to verify OnBoarding API endpoints
"""
import requests
import json

# Test server URL (adjust if needed)
BASE_URL = "http://192.168.0.113:5051"

print("=" * 60)
print("Testing OnBoarding API Endpoints")
print("=" * 60)

# Test 1: Get employee by emp_code
print("\n1. Testing GET /onboarding/employee/<emp_code>")
print("-" * 60)

# Replace with a valid emp_code from your database
test_emp_code = "13177"  # Change this to a valid emp_code

url = f"{BASE_URL}/onboarding/employee/{test_emp_code}"
print(f"Request: GET {url}")

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)

