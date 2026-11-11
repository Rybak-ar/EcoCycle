---
name: bottle-backend-development
description: แนวทางการพัฒนา โครงสร้างและข้อควรระวังในการเขียนโค้ดสำหรับโปรเจกต์ Backend เครื่องแยกขวด
---

# Bottle Project Backend Skill / Guidelines

ไฟล์นี้เป็นข้อตกลงและหลักการพัฒนา (Development Principles) สำหรับผู้ที่จะเข้ามาพัฒนาโปรเจกต์ต่อ เพื่อให้โค้ดมีโครงสร้างเดียวกันและง่ายต่อการดูแลรักษา (Maintainability)

## 1. โครงสร้างสถาปัตยกรรม (Architecture)
โปรเจกต์นี้ใช้โครงสร้างแบบ **MVC (Model-View-Controller)** แบบกำหนดเอง (Custom PHP MVC) โดยมีโครงสร้างดังนี้:
- **`src/Routes/api.php`**: เป็นที่รวมการประกาศเส้นทาง (Routing) ทั้งหมด หากเพิ่มฟีเจอร์ใหม่ให้มาลงทะเบียน Route ที่นี่
- **`src/Router.php`**: เป็น Core Logic ของการนำทาง หากมีการทำ Public/Private Endpoint ให้แก้ไขตัวแปร `$public_routes` ที่นี่
- **`src/Controllers/`**: ทำหน้าที่รับ Request, ตรวจสอบ (Validate), เรียกใช้ Model และส่งคืน Response ไม่ควรเขียน Logic การจัดการฐานข้อมูลตรงๆ ที่นี่
- **`src/Models/`**: ทำหน้าที่เชื่อมต่อและกระทำกับฐานข้อมูล ทุก Model ควร Extends จาก `App\Models\Basemodel`

## 2. หลักการพัฒนา (Development Principles)

### 2.1 การจัดการ API และ Routing
- **RESTful API Design**: ตั้งชื่อ Endpoint ให้สื่อความหมาย เช่น `GET /api/admin/machines` ไม่ใช่ `GET /api/admin/get_machines`
- **Controller Separation**: แบ่ง Controller ตามลักษณะผู้ใช้งาน (Role) หรือ Entity หลักๆ 
  - `AdminController` สำหรับผู้ดูแลระบบ
  - `OperatorController` สำหรับเจ้าของตู้
  - `UserController` สำหรับผู้ใช้งานหน้าตู้
  - `MachineController` สำหรับจัดการ Entity ของตู้ทั่วไป

### 2.2 การตรวจสอบข้อมูล (Validation)
- ใช้ฟังก์ชัน `checkEmpty($data, ['field1', 'field2'])` ในการตรวจสอบ Payload เสมอ เพื่อลดปัญหา Null Exception
- ห้าม Trust Client (อย่าเชื่อข้อมูลที่ส่งมาจาก Frontend แบบ 100%) หากมีการคำนวณ เช่น เรทราคา ต้องมีกระบวนการกรองข้อมูลเสมอ

### 2.3 การจัดการฐานข้อมูล (Database Management)
- **ใช้ PDO เสมอ**: เพื่อป้องกัน SQL Injection โดยการใช้ `prepare()` และ `bindParam()`
- **ห้ามแก้ไข Schema แบบ Manual ทิ้งไว้**: หากต้องแก้ไข Table ให้ไปแก้ไขในไฟล์ `src/Database/Schema.php` หรือเขียนสคริปต์ Migration เก็บไว้
- **Foreign Keys**: รักษา Data Integrity โดยตารางที่มีความสัมพันธ์ (เช่น ตู้ กับ เจ้าของตู้) ควรมีการระบุ `ON DELETE SET NULL` หรือ `ON DELETE CASCADE` ให้เหมาะสม

### 2.4 การจัดการความปลอดภัยและ Role-based (Authentication & Authorization)
- **JWT Tokens**: ควบคุมสิทธิ์การเข้าใช้งานผ่าน JWT สำหรับ Admin/Operator ให้ระวังความลับของ `JWT_SECRET`
- **Dynamic Public Routes**: โปรเจกต์มีการรองรับ Regex ในการตรวจสอบ Public Endpoint ใน `Router.php` โปรดตรวจสอบให้แน่ใจว่า Route ที่กำหนดในนั้นไม่ทำให้ข้อมูลรั่วไหล

### 2.5 การทำงานกับ Model และ Base Model
- เมื่อจะสร้างตารางใหม่ ให้สร้างคลาสใน `src/Models/...` เสมอ โดยการประกาศตัวแปร `$table` และ `$primarykey` เพื่อให้สามารถใช้ฟังก์ชันพื้นฐานของ `Basemodel` ได้แก่ `Create`, `Update`, `Delete`, `findById` ได้โดยไม่ต้องเขียน SQL ใหม่

## 3. วิธีการอ่านเอกสารและใช้งาน API (API Documentation)
เราได้จัดทำไฟล์ `API_DOCUMENTATION.md` ไว้เพื่อให้ทีม Frontend หรือผู้ที่นำ API ไปต่อยอดสามารถเข้าใจได้ง่าย โดยมีหลักการอ่านดังนี้:
1. **ดู Role ของตัวเอง**: เอกสารแบ่งตามหัวข้อ 1. Admin, 2. Operator, 3. User ให้ดูหัวข้อที่ตรงกับสิทธิ์ที่คุณมี
2. **ดู Endpoint และ Method**: ระบุชัดเจนว่าต้องใช้ `GET`, `POST`, `PUT`, หรือ `DELETE` กับ URL ไหน
3. **ตรวจสอบ Authentication**: 
   - สังเกตที่หัวข้อ **Authentication** หากเขียนว่า `Authorization: Bearer <Token>` แปลว่าต้องแนบ Token ทุกครั้งใน Header
   - หากเขียนว่า `ไม่ต้องใช้ Token` แปลว่าเป็น Public Route (เช่น การล็อกอิน/ลงทะเบียนหน้าตู้)
4. **ดู Request Body และ Response**: เอกสารมีบล็อกโค้ดตัวอย่าง JSON Payload ที่คุณต้องส่งไป และผลลัพธ์ที่คุณจะได้รับกลับมา ให้ยึดตามตัวแปรในตัวอย่างนั้น (เช่น `amount`, `weight`, `type`)

## 4. จุดที่ต้องโฟกัสในการพัฒนาต่อ (Focus Areas)
1. **การบันทึกประวัติแต้ม (Transaction Logs)**: ตาราง `tb_pointlog` ควรถูกใช้ทุกครั้งที่มีการเข้าใช้งานตู้และมีการเพิ่ม/ลด Point เพื่อการตรวจสอบย้อนหลัง (Audit trail)
2. **การทำ Validation เชิงลึก**: เพิ่มการเช็คประเภทข้อมูล (เช่น เป็นตัวเลข เป็นอีเมล ฯลฯ) ไม่ใช่แค่การเช็คว่าว่างหรือไม่ (`checkEmpty`)
3. **การรับรองความหนาแน่นผู้ใช้งาน (Concurrency)**: การล็อกอินหน้าตู้ หรือการตัด/เพิ่มยอดขวด อาจจะต้องคำนึงถึง Race Conditions เล็กน้อย แนะนำให้ใช้ Transaction (`$db->beginTransaction()`) หากมีการเซฟข้อมูล 2 ตารางพร้อมกัน
4. **Error Handling**: ปัจจุบันใช้ JSON Return กลับไปเป็น HTTP Status code แนะนำให้ทำ Global Exception Handler เพื่อรองรับ 500 Internal Server Error อย่างสวยงามและเป็นระบบ
