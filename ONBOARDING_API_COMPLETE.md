# OnBoarding API Implementation - Complete

## 📍 Backend Location
**Path:** `E:\sjm\AttendanceSystem`

## 🚀 What Was Implemented

### 1. Created OnBoarding Module
**Location:** `E:\sjm\AttendanceSystem\src\onboarding\`

**Files Created:**
- `__init__.py` - Module initializer
- `query.py` - SQL queries for employee lookup and face registration
- `onboarding.py` - Flask blueprint with API endpoints

### 2. API Endpoints

#### GET /onboarding/employee/{emp_code}
**Description:** Lookup employee by emp_code and return details with face count

**Parameters:**
- `emp_code` (path) - Employee code from hrms_ed_official_details

**Example Request:**
```
GET http://192.168.0.113:5051/onboarding/employee/13177
```

**Success Response (200):**
```json
{
  "status": "success",
  "eb_id": 12345,
  "emp_code": "13177",
  "name": "John Doe",
  "department_name": "Production",
  "designation_name": "Operator",
  "branch_id": 29,
  "face_count": 1,
  "can_register": true
}
```

**Error Response (404):**
```json
{
  "status": "error",
  "message": "Employee with emp_code 13177 not found or not in official records"
}
```

---

#### POST /onboarding/register-face
**Description:** Register a face photo for an employee (max 3 faces)

**Request Body:**
```json
{
  "emp_code": "13177",
  "face_image": "base64_encoded_image_string"
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "message": "Face registered successfully for John Doe (13177) - 2/3",
  "face_count": 2,
  "can_register": true
}
```

**Error Responses:**

**404 - Employee Not Found:**
```json
{
  "status": "error",
  "message": "Employee with emp_code 13177 not found or not in official records"
}
```

**400 - Max Faces Reached:**
```json
{
  "status": "error",
  "message": "Maximum 3 faces already registered for John Doe. Cannot add more."
}
```

**400 - No Face Detected:**
```json
{
  "status": "error",
  "message": "No face detected in the image. Please try again."
}
```

---

## 🔄 How It Works

1. **User enters Employee Code** (e.g., "13177")
2. **Mobile app calls:** `GET /onboarding/employee/13177`
3. **Backend:**
   - Looks up `emp_code` in `hrms_ed_official_details`
   - Joins with `hrms_ed_personal_details` to get eb_id
   - Counts existing faces in `employee_face_mst`
   - Returns employee details + face count
4. **User captures face photo**
5. **Mobile app calls:** `POST /onboarding/register-face` with emp_code + base64 image
6. **Backend:**
   - Validates employee exists
   - Checks face count < 3
   - Generates face embedding (if face_recognition library available)
   - Inserts into `employee_face_mst` with eb_id
   - Returns success with updated count

---

## 🗄️ Database Tables Used

### hrms_ed_official_details
- Contains `emp_code` (employee code)
- Contains `eb_id` (employee base ID)
- Used for employee lookup

### hrms_ed_personal_details
- Contains employee personal information (name, etc.)
- Linked via `eb_id`
- Must have `active = 1`

### employee_face_mst
- Stores face embeddings and photos
- Uses `eb_id` as foreign key
- Max 3 faces per employee (checked by counting rows with `active = 1`)

---

## 🔧 Server Configuration

**Database:** sjm @ 13.126.47.172
**Port:** 5051
**Host:** 0.0.0.0

**To Start Server:**
```bash
cd E:\sjm\AttendanceSystem
python app.py
```

**To Test:**
```bash
cd E:\sjm\AttendanceSystem
python test_onboarding.py
```

---

## ✅ Mobile App Updates

The mobile app has already been updated to:
- Accept Employee Code input (text field)
- Call the correct API endpoints
- Handle emp_code instead of eb_id
- Display face count and registration status

**APK Built and Installed:** ✅

---

## 🔍 Troubleshooting

### If you get 404 error:

1. **Check if server is running:**
   ```bash
   curl http://192.168.0.113:5051/
   ```
   Should return: `{"status": "success", "message": "✅ Attendance Server Running!"}`

2. **Verify employee exists:**
   - Check if emp_code exists in `hrms_ed_official_details`
   - Check if corresponding eb_id exists in `hrms_ed_personal_details`
   - Check if employee has `active = 1`

3. **Restart server:**
   - Stop any running Python processes
   - Navigate to `E:\sjm\AttendanceSystem`
   - Run `python app.py`

4. **Check server IP:**
   - Verify the mobile app is configured with correct server IP
   - Current: `http://192.168.0.113:5051`
   - You can change it from the Login screen (Settings icon)

---

## 📝 Notes

- Face embedding generation requires `face_recognition` library
- If library is not installed, the API will still work but won't validate faces
- Maximum 3 faces per employee enforced at database level
- All queries join official_details and personal_details for data consistency

---

**Implementation Date:** April 23, 2026
**Status:** ✅ Complete and Ready for Testing

