USE ecocycle_db;

-- 1. อัปเดต tb_machine: เพิ่ม shop_id, serial_number, pairing_code
SET @dbname = DATABASE();

-- check shop_id
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_machine' AND COLUMN_NAME = 'shop_id') = 0,
  'ALTER TABLE tb_machine ADD COLUMN shop_id INT DEFAULT NULL AFTER op_id;',
  'SELECT 1;'
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- check serial_number
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_machine' AND COLUMN_NAME = 'serial_number') = 0,
  'ALTER TABLE tb_machine ADD COLUMN serial_number VARCHAR(100) DEFAULT NULL AFTER shop_id;',
  'SELECT 1;'
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- check pairing_code
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_machine' AND COLUMN_NAME = 'pairing_code') = 0,
  'ALTER TABLE tb_machine ADD COLUMN pairing_code VARCHAR(16) DEFAULT NULL AFTER serial_number;',
  'SELECT 1;'
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 2. อัปเดต tb_config: เปลี่ยน m_id เป็น machine_id
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_config' AND COLUMN_NAME = 'm_id') > 0,
  'ALTER TABLE tb_config CHANGE COLUMN m_id machine_id INT;',
  'SELECT 1;'
));
PREPARE alterIfExists FROM @preparedStatement;
EXECUTE alterIfExists;
DEALLOCATE PREPARE alterIfExists;

-- 3. อัปเดต tb_pointrate: เปลี่ยน m_id เป็น machine_id
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_pointrate' AND COLUMN_NAME = 'm_id') > 0,
  'ALTER TABLE tb_pointrate CHANGE COLUMN m_id machine_id INT;',
  'SELECT 1;'
));
PREPARE alterIfExists FROM @preparedStatement;
EXECUTE alterIfExists;
DEALLOCATE PREPARE alterIfExists;

-- 4. อัปเดต tb_member: เพิ่ม u_id, birthday, money และเปลี่ยน m_id เป็น machine_id
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_member' AND COLUMN_NAME = 'u_id') = 0,
  'ALTER TABLE tb_member ADD COLUMN u_id INT DEFAULT NULL AFTER id;',
  'SELECT 1;'
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_member' AND COLUMN_NAME = 'm_id') > 0,
  'ALTER TABLE tb_member CHANGE COLUMN m_id machine_id INT;',
  'SELECT 1;'
));
PREPARE alterIfExists FROM @preparedStatement;
EXECUTE alterIfExists;
DEALLOCATE PREPARE alterIfExists;

SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_member' AND COLUMN_NAME = 'birthday') = 0,
  'ALTER TABLE tb_member ADD COLUMN birthday DATE DEFAULT NULL AFTER lname;',
  'SELECT 1;'
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_member' AND COLUMN_NAME = 'money') = 0,
  'ALTER TABLE tb_member ADD COLUMN money DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER point;',
  'SELECT 1;'
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 5. อัปเดต tb_pointlog: เปลี่ยน u_id เป็น member_id และ m_id เป็น machine_id
SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_pointlog' AND COLUMN_NAME = 'u_id') > 0,
  'ALTER TABLE tb_pointlog CHANGE COLUMN u_id member_id INT;',
  'SELECT 1;'
));
PREPARE alterIfExists FROM @preparedStatement;
EXECUTE alterIfExists;
DEALLOCATE PREPARE alterIfExists;

SET @preparedStatement = (SELECT IF(
  (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'tb_pointlog' AND COLUMN_NAME = 'm_id') > 0,
  'ALTER TABLE tb_pointlog CHANGE COLUMN m_id machine_id INT;',
  'SELECT 1;'
));
PREPARE alterIfExists FROM @preparedStatement;
EXECUTE alterIfExists;
DEALLOCATE PREPARE alterIfExists;

-- 6. อัปเดต tb_user: role เพิ่ม 'shop'
ALTER TABLE tb_user MODIFY COLUMN role ENUM('operator','admin','shop') DEFAULT 'operator';

-- 7. สร้างตารางใหม่ถ้ายังไม่มี
CREATE TABLE IF NOT EXISTS tb_redeem_request (
    id INT AUTO_INCREMENT PRIMARY KEY,
    u_id INT,
    machine_id INT,
    amount FLOAT NOT NULL COMMENT 'จำนวนแต้ม/เงินที่ขอแลก',
    status ENUM('pending','approved','rejected') DEFAULT 'pending',
    createat DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (u_id) REFERENCES tb_member(id) ON DELETE SET NULL,
    FOREIGN KEY (machine_id) REFERENCES tb_machine(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางคำขอแลกแต้ม/เงิน รอการอนุมัติ';

CREATE TABLE IF NOT EXISTS tb_issue_report (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    createat DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('ยังไม่เริ่มดำเนินการ','กำลังเริ่มดำเนินการ','ดำเนินการแล้ว') DEFAULT 'ยังไม่เริ่มดำเนินการ',
    admin_result TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางแจ้งปัญหาและคำตอบจากแอดมิน';

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
