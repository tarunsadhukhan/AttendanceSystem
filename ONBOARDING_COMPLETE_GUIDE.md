# OnBoarding System - Complete Flow Documentation

## 🎯 System Architecture

```
Mobile App (Android)
    ↓
    | HTTP Request
    ↓
Backend API (Flask - E:\sjm\AttendanceSystem)
    ↓
    | SQL Query
    ↓
Database (MySQL - sjm @ 13.126.47.172)
```

---

## 📊 Data Flow Diagram

### 1. Employee Lookup Flow

```
User Input: emp_code = "13177"
    ↓
Mobile App → GET /onboarding/employee/13177
    ↓
Backend receives emp_code
    ↓
Query: hrms_ed_official_details (WHERE emp_code = '13177')
    ↓
JOIN: hrms_ed_personal_details (ON eb_id)
    ↓
Result: {eb_id: 12345, emp_code: "13177", name: "John Doe", ...}
    ↓
Query: employee_face_mst (COUNT WHERE eb_id = 12345 AND active = 1)
    ↓
Result: face_count = 1
    ↓
Response: {status: "success", eb_id: 12345, face_count: 1, can_register: true}
    ↓
Mobile App displays employee info + face count
```

### 2. Face Registration Flow

```
User captures photo → base64 encoding
    ↓
Mobile App → POST /onboarding/register-face
    {emp_code: "13177", face_image: "base64..."}
    ↓
Backend receives request
    ↓
Validate: emp_code exists in hrms_ed_official_details
    ↓
Retrieve: eb_id from emp_code
    ↓
Check: face_count < 3
    ↓
Generate: face_embedding from image (using face_recognition)
    ↓
Insert: employee_face_mst
    - eb_id: 12345
    - face_embedding: [128-dimensional vector]
    - photo_html: base64 image
    - active: 1
    ↓
Response: {status: "success", face_count: 2, can_register: true}
    ↓
Mobile App shows success message
```

---

## 🗄️ Database Schema

### Table: hrms_ed_official_details
```sql
┌──────────────┬──────────────┬──────────┐
│ Column       │ Type         │ Key      │
├──────────────┼──────────────┼──────────┤
│ eb_id        │ BIGINT       │ FK       │
│ emp_code     │ VARCHAR(50)  │ UNIQUE   │
│ sub_dept_id  │ INT          │          │
│ designation_id│ INT         │          │
│ branch_id    │ INT          │          │
└──────────────┴──────────────┴──────────┘
```

### Table: hrms_ed_personal_details
```sql
┌──────────────┬──────────────┬──────────┐
│ Column       │ Type         │ Key      │
├──────────────┼──────────────┼──────────┤
│ eb_id        │ BIGINT       │ PRIMARY  │
│ first_name   │ VARCHAR(100) │          │
│ middle_name  │ VARCHAR(100) │          │
│ last_name    │ VARCHAR(100) │          │
│ active       │ TINYINT(1)   │          │
└──────────────┴──────────────┴──────────┘
```

### Table: employee_face_mst
```sql
┌─────────────────┬──────────────┬──────────┐
│ Column          │ Type         │ Key      │
├─────────────────┼──────────────┼──────────┤
│ emp_face_id     │ BIGINT       │ PRIMARY  │
│ eb_id           │ BIGINT       │ FK       │
│ face_embedding  │ LONGTEXT     │          │
│ active          │ INT          │          │
│ photo_html      │ LONGTEXT     │          │
│ updated_by      │ INT          │          │
│ updated_date_time│ TIMESTAMP   │          │
└─────────────────┴──────────────┴──────────┘
```

---

## 🔑 Key Concepts

### Why emp_code → eb_id conversion?

1. **User Input:** emp_code is user-friendly (e.g., "13177", "EMP001")
2. **Database Storage:** eb_id is the internal foreign key reference
3. **Conversion:** Backend looks up eb_id from emp_code
4. **Storage:** Face data is stored with eb_id in employee_face_mst

### Why max 3 faces?

- Allows for multiple face angles/expressions
- Improves face recognition accuracy
- Prevents database bloat
- Enforced by counting rows WHERE eb_id = ? AND active = 1

---

## 🔧 API Details

### Endpoint 1: Get Employee

**URL:** `GET /onboarding/employee/<emp_code>`

**Path Parameter:**
- `emp_code` (string) - Employee code from official records

**Response Codes:**
- `200` - Success
- `404` - Employee not found
- `500` - Server error

**Success Response:**
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

### Endpoint 2: Register Face

**URL:** `POST /onboarding/register-face`

**Request Body:**
```json
{
  "emp_code": "13177",
  "face_image": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}
```

**Response Codes:**
- `200` - Success
- `400` - Validation error (missing data, max faces, no face detected)
- `404` - Employee not found
- `500` - Server error

**Success Response:**
```json
{
  "status": "success",
  "message": "Face registered successfully for John Doe (13177) - 2/3",
  "face_count": 2,
  "can_register": true
}
```

---

## 🧪 Testing Guide

### 1. Test Employee Lookup

```bash
# Replace 13177 with a valid emp_code from your database
curl http://192.168.0.113:5051/onboarding/employee/13177
```

### 2. Test Face Registration

```bash
# Create a test image file (test.jpg) and convert to base64
# Then send the request

curl -X POST http://192.168.0.113:5051/onboarding/register-face \
  -H "Content-Type: application/json" \
  -d '{
    "emp_code": "13177",
    "face_image": "BASE64_STRING_HERE"
  }'
```

### 3. Using Python Test Script

```bash
cd E:\sjm\AttendanceSystem
python test_onboarding.py
```

---

## 🚨 Troubleshooting

### Error: 404 - Employee not found

**Possible Causes:**
1. emp_code doesn't exist in `hrms_ed_official_details`
2. Employee doesn't have record in `hrms_ed_personal_details`
3. Employee's `active` flag is 0

**Solution:**
```sql
-- Check if employee exists
SELECT o.emp_code, p.eb_id, p.active
FROM hrms_ed_official_details o
LEFT JOIN hrms_ed_personal_details p ON o.eb_id = p.eb_id
WHERE o.emp_code = '13177';
```

### Error: 400 - Maximum faces reached

**Solution:**
```sql
-- Check current face count
SELECT COUNT(*) FROM employee_face_mst 
WHERE eb_id = 12345 AND active = 1;

-- Delete old faces if needed (backup first!)
UPDATE employee_face_mst 
SET active = 0 
WHERE eb_id = 12345 
ORDER BY updated_date_time ASC 
LIMIT 1;
```

### Error: 400 - No face detected

**Possible Causes:**
1. Image quality too poor
2. No face visible in image
3. face_recognition library not installed

**Solution:**
- Ensure good lighting when capturing photo
- Face should be clearly visible
- Install face_recognition: `pip install face_recognition`

### Error: Connection refused

**Solution:**
1. Check if server is running:
   ```bash
   curl http://192.168.0.113:5051/
   ```

2. Restart server:
   ```bash
   cd E:\sjm\AttendanceSystem
   python app.py
   ```

3. Check firewall settings (port 5051)

---

## 📱 Mobile App Usage

1. **Login** to the app
2. Navigate to **Attendance** → **On Boarding**
3. Enter **Employee Code** (e.g., 13177)
4. Click **Search**
5. Review employee details and face count
6. Click **📷 Open Camera**
7. Take a photo of the employee's face
8. Click **✅ Register Face**
9. Wait for confirmation
10. Repeat steps 6-8 for additional faces (max 3)

---

## 🔐 Security Notes

- Employee must have `active = 1` to register faces
- Face embeddings are stored securely in database
- Original images stored as base64 in `photo_html`
- Access controlled by mobile app authentication

---

## 📞 Support

For issues or questions:
1. Check this documentation
2. Review error logs in backend console
3. Test API endpoints using curl or Postman
4. Verify database records manually

---

**Last Updated:** April 23, 2026
**Version:** 1.0
**Status:** ✅ Production Ready

