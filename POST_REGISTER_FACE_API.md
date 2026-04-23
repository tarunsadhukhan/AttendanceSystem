## 🚀 POST /onboarding/register-face - API Endpoint Documentation

### 📍 Endpoint Details

**URL:** `http://192.168.0.223:5051/onboarding/register-face`  
**Method:** `POST`  
**Content-Type:** `application/json`

---

### 📥 Request Format

#### Headers
```
Content-Type: application/json
```

#### Request Body
```json
{
  "emp_code": "13177",
  "face_image": "base64_encoded_image_data_here"
}
```

**Parameters:**
- `emp_code` (string, required) - Employee code from hrms_ed_official_details
- `face_image` (string, required) - Base64 encoded image data (JPEG/PNG)

---

### 📤 Response Formats

#### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Face registered successfully for John Doe (13177) - 2/3",
  "face_count": 2,
  "can_register": true
}
```

#### Error Responses

**404 - Employee Not Found**
```json
{
  "status": "error",
  "message": "Employee with emp_code 13177 not found or not in official records"
}
```

**400 - Missing emp_code**
```json
{
  "status": "error",
  "message": "emp_code is required"
}
```

**400 - Missing face_image**
```json
{
  "status": "error",
  "message": "face_image is required"
}
```

**400 - Maximum Faces Reached**
```json
{
  "status": "error",
  "message": "Maximum 3 faces already registered for John Doe. Cannot add more."
}
```

**400 - No Face Detected**
```json
{
  "status": "error",
  "message": "No face detected in the image. Please try again."
}
```

**500 - Server Error**
```json
{
  "status": "error",
  "message": "Internal server error message"
}
```

---

### 💻 Example Usage

#### Using cURL
```bash
curl -X POST http://192.168.0.223:5051/onboarding/register-face \
  -H "Content-Type: application/json" \
  -d '{
    "emp_code": "13177",
    "face_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ..."
  }'
```

#### Using PowerShell
```powershell
$url = "http://192.168.0.223:5051/onboarding/register-face"
$body = @{
    emp_code = "13177"
    face_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ..."
} | ConvertTo-Json

Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json"
```

#### Using Python (requests)
```python
import requests
import base64

url = "http://192.168.0.113:5051/onboarding/register-face"

# Read and encode image
with open("face_photo.jpg", "rb") as image_file:
    face_image_base64 = base64.b64encode(image_file.read()).decode()

payload = {
    "emp_code": "13177",
    "face_image": face_image_base64
}

response = requests.post(url, json=payload)
print(response.json())
```

#### Using JavaScript (Fetch API)
```javascript
const url = "http://192.168.0.223:5051/onboarding/register-face";

const payload = {
  emp_code: "13177",
  face_image: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ..."
};

fetch(url, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(payload)
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

---

### 🔄 Backend Processing Flow

```
1. Receive POST request with emp_code + face_image
   ↓
2. Validate emp_code and face_image are present
   ↓
3. Query hrms_ed_official_details for emp_code
   ↓
4. JOIN with hrms_ed_personal_details to get eb_id
   ↓
5. Check if employee exists and is active
   ↓
6. Count existing faces in employee_face_mst (WHERE eb_id AND active=1)
   ↓
7. Verify face_count < 3
   ↓
8. Decode base64 image
   ↓
9. Generate face embedding using face_recognition library
   ↓
10. Validate face detected in image
    ↓
11. INSERT INTO employee_face_mst (eb_id, face_embedding, photo_html)
    ↓
12. Return success response with updated face_count
```

---

### 🗄️ Database Tables

#### employee_face_mst
```sql
CREATE TABLE employee_face_mst (
    emp_face_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    eb_id BIGINT NOT NULL,
    face_embedding LONGTEXT,
    active INT NOT NULL DEFAULT 1,
    photo_html LONGTEXT,
    updated_by INT NOT NULL,
    updated_date_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (eb_id) REFERENCES hrms_ed_personal_details(eb_id)
);
```

---

### ⚠️ Important Notes

1. **Face Limit:** Maximum 3 faces per employee
2. **Image Format:** Base64 encoded JPEG or PNG
3. **Face Detection:** Requires face_recognition library installed
4. **Employee Validation:** emp_code must exist in hrms_ed_official_details
5. **Active Status:** Employee must have active=1 in hrms_ed_personal_details
6. **Storage:** Face data stored with eb_id (not emp_code)

---

### 🔧 Testing

**Test Files Created:**
- `test_register_face.py` - Python test script
- `test_post_endpoint.ps1` - PowerShell test script

**Run Tests:**
```bash
# Python
cd E:\sjm\AttendanceSystem
python test_register_face.py

# PowerShell
cd E:\sjm\AttendanceSystem
.\test_post_endpoint.ps1
```

---

### 🚨 Troubleshooting

#### Issue: Connection Refused
**Solution:** Start the backend server
```bash
cd E:\sjm\AttendanceSystem
python app.py
```

#### Issue: Employee Not Found (404)
**Solution:** Verify emp_code exists
```sql
SELECT o.emp_code, p.eb_id, p.active
FROM hrms_ed_official_details o
INNER JOIN hrms_ed_personal_details p ON o.eb_id = p.eb_id
WHERE o.emp_code = '13177';
```

#### Issue: Maximum Faces Reached (400)
**Solution:** Check and optionally remove old faces
```sql
-- Check current count
SELECT COUNT(*) FROM employee_face_mst WHERE eb_id = 12345 AND active = 1;

-- Deactivate oldest face (if needed)
UPDATE employee_face_mst 
SET active = 0 
WHERE eb_id = 12345 
ORDER BY updated_date_time ASC 
LIMIT 1;
```

#### Issue: No Face Detected (400)
**Solution:** 
- Ensure good lighting when capturing photo
- Face should be clearly visible
- Use actual face photo (not test images)
- Install face_recognition: `pip install face_recognition`

---

### 📱 Mobile App Integration

The Android app automatically calls this endpoint when:
1. User navigates to **On Boarding** screen
2. Enters employee code and clicks **Search**
3. Clicks **📷 Open Camera** and captures photo
4. Clicks **✅ Register Face**

**Mobile App Flow:**
```kotlin
// 1. Capture photo
val photoFile = File(filesDir, "face_photos/face_${timestamp}.jpg")
val photoUri = FileProvider.getUriForFile(this, "${packageName}.fileprovider", photoFile)
cameraLauncher.launch(photoUri)

// 2. Convert to base64
val bytes = photoFile.readBytes()
val base64 = android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP)

// 3. Call API
val request = OnBoardingRegisterRequest(empCode = empCode, faceImage = base64)
RetrofitClient.getApiService(this).registerOnBoardingFace(request)
```

---

### ✅ Status

- ✅ Backend endpoint implemented
- ✅ Mobile app integrated
- ✅ Camera functionality fixed
- ✅ Test scripts created
- ⚠️ **Server must be running on 192.168.0.223:5051**

---

**Created:** April 23, 2026  
**Backend:** E:\sjm\AttendanceSystem  
**Status:** Ready for Production

