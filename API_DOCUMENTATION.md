# Bottle Recycling Machine API Documentation

เอกสารฉบับนี้อธิบายถึงโครงสร้างข้อมูล รูปแบบการร้องขอ (Request) และการตอบกลับ (Response) ของ API สำหรับระบบจัดการตู้แยกขวดรีไซเคิล

## โครงสร้างระบบ (Roles)
ระบบถูกแบ่งการเข้าถึงออกเป็น 3 ระดับ:
1. **Admin**: ผู้ดูแลระบบทั้งหมด จัดการเจ้าของตู้และอนุมัติตู้
2. **Operator**: เจ้าของตู้ จัดการเรทราคา ดูข้อมูลการใช้งานของแต่ละตู้
3. **User**: ผู้ใช้งานทั่วไป (ลงทะเบียน/ใช้งานผ่านหน้าตู้โดยใช้เบอร์โทรศัพท์)

---

## 1. Admin API (ผู้ดูแลระบบ)
**Authentication**: ต้องระบุ `Authorization: Bearer <Admin_Token>`

### 1.1 ดูแดชบอร์ดสรุป (Dashboard Stats)
- **Endpoint**: `GET /api/admin/dashboard`
- **Request Body**: (None)
- **Response**:
```json
{
  "status": "success",
  "data": {
    "total_machines": 10,
    "total_operators": 5,
    "total_bottles": 1500
  }
}
```

### 1.2 จัดการสถานะเจ้าของตู้ (Update User Status)
- **Endpoint**: `PUT /api/admin/users/{id}/status`
- **Request Body**:
```json
{
  "permission": 1  // 1 = Active, 0 = Inactive
}
```

### 1.3 อนุมัติการเปิดใช้งานตู้ (Approve Machine)
- **Endpoint**: `PUT /api/admin/machines/{id}/approve`
- **Request Body**:
```json
{
  "allow": 1  // 1 = อนุญาตให้ทำงานได้, 0 = ไม่อนุญาต
}
```

---

## 2. Operator API (เจ้าของตู้)
**Authentication**: ต้องระบุ `Authorization: Bearer <Operator_Token>`

### 2.1 ตั้งค่ารูปแบบตู้ (Config Machine)
- **Endpoint**: `PUT /api/operator/machines/{id}/config`
- **Condition**: 
  - หาก `type = money` ให้ส่ง `base_prices` (ราคาขายต่อกรัมเต็ม 100%) **ระบบจะคำนวณ 80% แล้วบันทึกอัตโนมัติ**
  - หาก `type = point` ให้ส่ง `rates` เป็นแต้มที่ต้องการให้โดยตรง
- **Request Body (กรณีตั้งค่าเป็นเงิน)**:
```json
{
  "type": "money",
  "base_prices": {
    "clear": 10,   // ระบบจะนำไปบันทึกค่าเป็น 8
    "opaque": 8,   // ระบบจะนำไปบันทึกค่าเป็น 6.4
    "brown": 5     // ระบบจะนำไปบันทึกค่าเป็น 4
  }
}
```
- **Request Body (กรณีตั้งค่าเป็นแต้ม)**:
```json
{
  "type": "point",
  "rates": {
    "clear": 100,
    "opaque": 80,
    "brown": 50
  }
}
```

### 2.2 ดูผู้ใช้งานแยกตามตู้ (Get Machine Users)
- **Endpoint**: `GET /api/operator/machines/{id}/users`
- **Response**:
```json
{
  "status": "success",
  "data": {
    "total_users": 2,
    "members": [
      {
        "id": 1,
        "phonenumber": "0812345678",
        "fname": "สมชาย",
        "lname": "ใจดี",
        "point": 150,
        "createat": "2026-05-16 12:00:00"
      }
    ]
  }
}
```

---

## 3. User API (ผู้ใช้งานที่หน้าตู้)
**Authentication**: สมัครและเข้าสู่ระบบ **ไม่ต้องใช้ Token** 

### 3.1 ลงทะเบียนหน้าตู้ (Register at Machine)
- **Endpoint**: `POST /api/user/machines/{m_id}/register`
- **Request Body**:
```json
{
  "phonenumber": "0812345678",
  "fname": "สมชาย",
  "lname": "ใจดี",
  "age": 25,          // Optional
  "gender": "Male",   // Optional
  "localtion": "BKK"  // Optional
}
```

### 3.2 เข้าสู่ระบบหน้าตู้ (Login at Machine)
- **Endpoint**: `POST /api/user/machines/{m_id}/login`
- **Request Body**:
```json
{
  "phonenumber": "0812345678"
}
```
- **Response**:
```json
{
  "status": "success",
  "message": "เข้าสู่ระบบสำเร็จ",
  "token": "eyJ0eXAiOi...",
  "data": {
    "id": 1,
    "fname": "สมชาย",
    "lname": "ใจดี",
    "point": 150
  }
}
```

### 3.3 หยอดขวด (Deposit Bottle)
**Authentication**: ต้องระบุ `Authorization: Bearer <User_Token>` ที่ได้จาก Login หน้าตู้
- **Endpoint**: `POST /api/user/machines/{m_id}/deposit`
- **Request Body**:
```json
{
  "type": "clear",   // ประเภทขวด: clear (ใส), opaque (ขุ่น), brown (สีชา)
  "weight": 1.5      // น้ำหนักขวดหรือจำนวนที่เป็นตัวคูณ (เช่น 1.5 กรัม)
}
```
- **Response**:
```json
{
  "status": "success",
  "message": "รับขวดสำเร็จ",
  "data": {
    "earned": 12,           // แต้มหรือเงินที่ได้ในรอบนี้
    "total_point": 162      // แต้มหรือเงินสะสมทั้งหมด
  }
}
```
*หมายเหตุ*: ระบบจะทำการคำนวณเงินหรือแต้มโดยนำ `weight` ไปคูณกับค่าเรทของตู้นั้นโดยอัตโนมัติ

### 3.4 แลกแต้ม / ถอนเงิน (Redeem)
**Authentication**: ต้องระบุ `Authorization: Bearer <User_Token>` ที่ได้จาก Login หน้าตู้
- **Endpoint**: `POST /api/user/machines/{m_id}/redeem`
- **Request Body**:
```json
{
  "amount": 50   // จำนวนแต้มหรือยอดเงินที่ต้องการแลกออก
}
```
- **Response**:
```json
{
  "status": "success",
  "message": "แลกเปลี่ยนสำเร็จ",
  "data": {
    "redeemed_amount": 50,
    "remaining_point": 112
  }
}
```
*หมายเหตุ*: ระบบจะทำการหักลบยอดคงเหลือในบัญชีผู้ใช้และบันทึกประวัติการแลกลงในระบบ (ติดลบ)

### 3.5 ดูข้อมูลส่วนตัวและ Point สะสม (Get Profile)
**Authentication**: ต้องระบุ `Authorization: Bearer <User_Token>` ที่ได้จาก Login หน้าตู้
- **Endpoint**: `GET /api/user/me`
- **Request Body**: (None)
- **Response**:
```json
{
  "status": "success",
  "data": {
    "fname": "สมชาย",
    "lname": "ใจดี",
    "point": 162
  }
}
```
