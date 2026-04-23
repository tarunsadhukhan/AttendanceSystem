# Test POST /onboarding/register-face endpoint using PowerShell
# Usage: .\test_register_face.ps1

$BASE_URL = "http://192.168.0.113:5051"
$TEST_EMP_CODE = "13177"  # Change to valid emp_code

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  Testing POST /onboarding/register-face" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# Step 1: Check if employee exists
Write-Host "`n1. Checking if employee exists..." -ForegroundColor Yellow
Write-Host "----------------------------------------------------------------------"

$empUrl = "$BASE_URL/onboarding/employee/$TEST_EMP_CODE"
Write-Host "GET $empUrl"

try {
    $empResponse = Invoke-RestMethod -Uri $empUrl -Method Get -TimeoutSec 5 -ErrorAction Stop

    Write-Host "Status: 200" -ForegroundColor Green
    Write-Host "Response:"
    Write-Host ($empResponse | ConvertTo-Json -Depth 3)

    if ($empResponse.status -eq "success") {
        Write-Host "`n✅ Employee found: $($empResponse.name)" -ForegroundColor Green
        Write-Host "   Face count: $($empResponse.face_count)/3"
        Write-Host "   Can register: $($empResponse.can_register)"

        # Step 2: Test face registration
        if ($empResponse.can_register -eq $true) {
            Write-Host "`n2. Testing face registration..." -ForegroundColor Yellow
            Write-Host "----------------------------------------------------------------------"

            # Test image (1x1 red pixel PNG - base64)
            $testImageBase64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

            $registerUrl = "$BASE_URL/onboarding/register-face"
            $body = @{
                emp_code = $TEST_EMP_CODE
                face_image = $testImageBase64
            } | ConvertTo-Json

            Write-Host "POST $registerUrl"
            Write-Host "Payload:"
            Write-Host "  emp_code: $TEST_EMP_CODE"
            Write-Host "  face_image: [base64 data, $($testImageBase64.Length) chars]"

            try {
                $registerResponse = Invoke-RestMethod -Uri $registerUrl -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10 -ErrorAction Stop

                Write-Host "`nStatus: 200" -ForegroundColor Green
                Write-Host "Response:"
                Write-Host ($registerResponse | ConvertTo-Json -Depth 3)

                if ($registerResponse.status -eq "success") {
                    Write-Host "`n✅ API endpoint is working!" -ForegroundColor Green
                    Write-Host "   Note: Used test image, not a real face" -ForegroundColor Yellow
                    Write-Host "   Real face images from mobile app should work"
                } else {
                    Write-Host "`n❌ Registration failed" -ForegroundColor Red
                }
            }
            catch {
                Write-Host "`n❌ Error during registration:" -ForegroundColor Red
                Write-Host "   $($_.Exception.Message)" -ForegroundColor Red

                if ($_.Exception.Response) {
                    $statusCode = $_.Exception.Response.StatusCode.value__
                    Write-Host "   HTTP Status: $statusCode" -ForegroundColor Red
                }
            }
        }
        else {
            Write-Host "`n⚠️  Cannot register - maximum faces reached" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "`n❌ Employee not found" -ForegroundColor Red
    }
}
catch {
    Write-Host "❌ Connection Error" -ForegroundColor Red
    Write-Host "   $($_.Exception.Message)" -ForegroundColor Red

    Write-Host "`n📋 POSSIBLE CAUSES:" -ForegroundColor Yellow
    Write-Host "   1. Backend server is not running"
    Write-Host "   2. Wrong IP address (current: 192.168.0.113)"
    Write-Host "   3. Wrong port (current: 5051)"
    Write-Host "   4. Firewall blocking connection"

    Write-Host "`n💡 TO START SERVER:" -ForegroundColor Cyan
    Write-Host "   cd E:\sjm\AttendanceSystem"
    Write-Host "   python app.py"
}

Write-Host "`n======================================================================" -ForegroundColor Cyan
Write-Host "  Test Complete" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

Write-Host "`n📖 API DOCUMENTATION:" -ForegroundColor Cyan
Write-Host "   Method: POST"
Write-Host "   URL: http://192.168.0.113:5051/onboarding/register-face"
Write-Host "   Content-Type: application/json"
Write-Host ""
Write-Host "   Request Body:"
Write-Host "   {"
Write-Host '     "emp_code": "13177",'
Write-Host '     "face_image": "base64_encoded_image_data"'
Write-Host "   }"
Write-Host ""
Write-Host "   Success Response (200):"
Write-Host "   {"
Write-Host '     "status": "success",'
Write-Host '     "message": "Face registered successfully for John Doe (13177) - 2/3",'
Write-Host '     "face_count": 2,'
Write-Host '     "can_register": true'
Write-Host "   }"

