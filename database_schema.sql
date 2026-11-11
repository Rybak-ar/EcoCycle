-- ==========================================
-- ฐานข้อมูลสำหรับระบบตู้รับขวดอัตโนมัติ (ตรงตาม Schema ฝั่งเว็บ)
-- ==========================================
CREATE DATABASE IF NOT EXISTS ecocycle_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ecocycle_db;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS tb_product_redeem;
DROP TABLE IF EXISTS tb_product;
DROP TABLE IF EXISTS tb_issue_report;
DROP TABLE IF EXISTS tb_pointlog;
DROP TABLE IF EXISTS tb_member;
DROP TABLE IF EXISTS tb_pointrate;
DROP TABLE IF EXISTS tb_config;
DROP TABLE IF EXISTS tb_machine;
DROP TABLE IF EXISTS tb_user;

SET FOREIGN_KEY_CHECKS = 1;

-- 1. ตารางผู้ดูแลระบบ / ผู้ประกอบการ / ร้านค้า
CREATE TABLE IF NOT EXISTS tb_user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    op_name TEXT NOT NULL,
    email TEXT,
    phonenumber TEXT,
    password TEXT NOT NULL,
    role ENUM('operator','admin','shop') DEFAULT 'operator',
    permission BOOLEAN DEFAULT FALSE,
    createat DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางผู้ประกอบการและร้านค้า';

-- 2. ตารางข้อมูลเครื่อง/ตู้รับขวด
CREATE TABLE IF NOT EXISTS tb_machine (
    id INT AUTO_INCREMENT PRIMARY KEY,
    op_id INT,
    shop_id INT DEFAULT NULL,
    serial_number VARCHAR(100) DEFAULT NULL,
    pairing_code VARCHAR(16) DEFAULT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    location TEXT,
    count INT DEFAULT 0 COMMENT 'จำนวนขวด',
    createat DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (op_id) REFERENCES tb_user(id) ON DELETE SET NULL,
    FOREIGN KEY (shop_id) REFERENCES tb_user(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางข้อมูลเครื่อง';

-- 3. ตารางตั้งค่าตัวเครื่อง
CREATE TABLE IF NOT EXISTS tb_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    machine_id INT,
    type ENUM('point', 'money') DEFAULT 'point' COMMENT 'เลือกประเภทเป็นแบบเก็บเเต้มหรือเสียเงิน',
    allow BOOLEAN DEFAULT TRUE COMMENT 'เปิดสิทธิการใช้งาน',
    FOREIGN KEY (machine_id) REFERENCES tb_machine(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางตั้งค่าตัวเครื่อง';

-- 4. ตารางตั้งค่าpoint / เรทราคา
CREATE TABLE IF NOT EXISTS tb_pointrate (
    id INT AUTO_INCREMENT PRIMARY KEY,
    machine_id INT,
    `key` TEXT NOT NULL,
    `value` FLOAT DEFAULT 0,
    FOREIGN KEY (machine_id) REFERENCES tb_machine(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางตั้งค่าpoint';

-- 5. ตารางลงทะเบียนผู้ใช้งาน (สมาชิก)
CREATE TABLE IF NOT EXISTS `tb_member` (
    `id` int AUTO_INCREMENT PRIMARY KEY,
    `u_id` int DEFAULT NULL,
    `machine_id` int DEFAULT NULL,
    `phonenumber` text COLLATE utf8mb4_unicode_ci NOT NULL,
    `title` text COLLATE utf8mb4_unicode_ci,
    `fname` text COLLATE utf8mb4_unicode_ci,
    `lname` text COLLATE utf8mb4_unicode_ci,
    `birthday` date DEFAULT NULL,
    `gender` text COLLATE utf8mb4_unicode_ci,
    `localtion` text COLLATE utf8mb4_unicode_ci,
    `point` float DEFAULT '0',
    `money` decimal(10,2) NOT NULL DEFAULT '0.00',
    `createat` datetime DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`machine_id`) REFERENCES tb_machine(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางลงทะเบียนผู้ใช้งาน';

-- 6. ตารางประวัติการหยอดขวดทีละใบ
CREATE TABLE IF NOT EXISTS tb_pointlog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    member_id INT,
    machine_id INT,
    bottle_type VARCHAR(20) DEFAULT NULL COMMENT 'ชนิดขวด: clear, opaque, brown',
    weight FLOAT DEFAULT 0 COMMENT 'น้ำหนักขวด (กรัม)',
    point FLOAT DEFAULT 0,
    createat DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES tb_member(id) ON DELETE SET NULL,
    FOREIGN KEY (machine_id) REFERENCES tb_machine(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางประวัติการหยอดขวดทีละใบ';


-- 8. ตารางแจ้งปัญหา
CREATE TABLE IF NOT EXISTS tb_issue_report (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    createat DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('ยังไม่เริ่มดำเนินการ','กำลังเริ่มดำเนินการ','ดำเนินการแล้ว') DEFAULT 'ยังไม่เริ่มดำเนินการ',
    admin_result TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางแจ้งปัญหาและคำตอบจากแอดมิน';

-- 9. ตารางสินค้าประจำตู้
CREATE TABLE IF NOT EXISTS tb_product (
    id INT AUTO_INCREMENT PRIMARY KEY,
    machine_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    image_url TEXT NULL,
    cost_type ENUM('point', 'money') DEFAULT 'point',
    point_cost FLOAT NOT NULL DEFAULT 0,
    stock INT NOT NULL DEFAULT 0,
    status ENUM('active', 'inactive', 'out_of_stock') DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES tb_machine(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางสินค้าประจำตู้';

-- 10. ตารางคำขอแลกสินค้าของลูกค้า
CREATE TABLE IF NOT EXISTS tb_product_redeem (
    id INT AUTO_INCREMENT PRIMARY KEY,
    machine_id INT NOT NULL,
    u_id INT NOT NULL,
    product_id INT NOT NULL,
    redeem_code VARCHAR(32) NOT NULL UNIQUE,
    quantity INT NOT NULL DEFAULT 1,
    points_used FLOAT NOT NULL DEFAULT 0,
    status ENUM('pending', 'completed', 'cancelled') DEFAULT 'pending',
    operator_note TEXT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    FOREIGN KEY (machine_id) REFERENCES tb_machine(id) ON DELETE CASCADE,
    FOREIGN KEY (u_id) REFERENCES tb_member(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES tb_product(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางคำขอแลกสินค้าของลูกค้า';

-- ==========================================
-- ข้อมูลทดสอบ (Initial Test Data)
-- ==========================================

-- ผู้ใช้งานระบบ (รหัสผ่านคือ 123456 เข้ารหัสด้วย bcrypt)
INSERT INTO tb_user (id, op_name, email, phonenumber, password, role, permission) VALUES 
(1, 'ผู้ดูแลระบบสูงสุด', 'admin@bottle.com', '0999999999', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'admin', 1),
(2, 'นายสมชาย ผู้ประกอบการ', 'somchai@bottle.com', '123', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'operator', 1),
(3, 'ร้านค้าประชารัฐ สาขา 1', 'shop1@bottle.com', '0888888888', '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'shop', 1)
ON DUPLICATE KEY UPDATE op_name=VALUES(op_name);

-- ตู้รับขวด
INSERT INTO tb_machine (id, op_id, shop_id, name, status, location, count) VALUES 
(1, 2, 3, 'ตู้รับขวดอัจฉริยะ สาขา 1', 'online', 'หน้าเซเว่น ซอย 1', 15)
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- การตั้งค่าตู้
INSERT INTO tb_config (id, machine_id, type, allow) VALUES 
(1, 1, 'point', 1)
ON DUPLICATE KEY UPDATE type=VALUES(type);

-- เรทแต้ม
INSERT INTO tb_pointrate (machine_id, `key`, `value`) VALUES 
(1, 'clear', 18),
(1, 'opaque', 15),
(1, 'brown', 10);

-- สมาชิกทดสอบ (เบอร์ 123 สำหรับทดสอบหน้าตู้)
INSERT INTO tb_member (id, machine_id, phonenumber, fname, lname, point, money) VALUES 
(1, 1, '123', 'สมศักดิ์', 'รักสะอาด', 36, 0.00)
ON DUPLICATE KEY UPDATE fname=VALUES(fname);
