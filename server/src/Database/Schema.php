<?php

namespace App\Database;

class Schema {
    private $db;

    public function __construct($db) {
        $this->db = $db;
    }

    public function createTables() {
        $this->migrateColumns();

        $queries = [
            // 1. tb_user
            "CREATE TABLE IF NOT EXISTS tb_user (
                id INT AUTO_INCREMENT PRIMARY KEY,
                op_name TEXT NOT NULL,
                email TEXT,
                phonenumber TEXT,
                password TEXT NOT NULL,
                role ENUM('operator','admin','shop') DEFAULT 'operator',
                permission BOOLEAN DEFAULT FALSE,
                createat DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางผู้ประกอบการและร้านค้า'",

            // 2. tb_machine
            "CREATE TABLE IF NOT EXISTS tb_machine (
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางข้อมูลเครื่อง'",

            // 3. tb_config
            "CREATE TABLE IF NOT EXISTS tb_config (
                id INT AUTO_INCREMENT PRIMARY KEY,
                machine_id INT,
                type ENUM('point', 'money') DEFAULT 'point' COMMENT 'เลือกประเภทเป็นแบบเก็บเเต้มหรือเสียเงิน',
                allow BOOLEAN DEFAULT TRUE COMMENT 'เปิดสิทธิการใช้งาน',
                FOREIGN KEY (machine_id) REFERENCES tb_machine(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางตั้งค่าตัวเครื่อง'",

            // 4. tb_pointrate
            "CREATE TABLE IF NOT EXISTS tb_pointrate (
                id INT AUTO_INCREMENT PRIMARY KEY,
                machine_id INT,
                `key` TEXT NOT NULL,
                `value` FLOAT DEFAULT 0,
                FOREIGN KEY (machine_id) REFERENCES tb_machine(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางตั้งค่าpoint'",

            // 5. tb_member
            "CREATE TABLE IF NOT EXISTS `tb_member` (
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางลงทะเบียนผู้ใช้งาน'",
            
            // 6. tb_pointlog
            "CREATE TABLE IF NOT EXISTS tb_pointlog (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT,
                machine_id INT,
                bottle_type VARCHAR(20) DEFAULT NULL COMMENT 'ชนิดขวด: clear, opaque, brown',
                weight FLOAT DEFAULT 0 COMMENT 'น้ำหนักขวด (กรัม)',
                point FLOAT DEFAULT 0,
                createat DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES tb_member(id) ON DELETE SET NULL,
                FOREIGN KEY (machine_id) REFERENCES tb_machine(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางประวัติการหยอดขวดทีละใบ'",

            // 7. tb_redeem_request
            "CREATE TABLE IF NOT EXISTS tb_redeem_request (
                id INT AUTO_INCREMENT PRIMARY KEY,
                u_id INT,
                machine_id INT,
                amount FLOAT NOT NULL COMMENT 'จำนวนแต้ม/เงินที่ขอแลก',
                status ENUM('pending','approved','rejected') DEFAULT 'pending',
                createat DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (u_id) REFERENCES tb_member(id) ON DELETE SET NULL,
                FOREIGN KEY (machine_id) REFERENCES tb_machine(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางคำขอแลกแต้ม/เงิน รอการอนุมัติ'",

            // 8. tb_issue_report
            "CREATE TABLE IF NOT EXISTS tb_issue_report (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                createat DATETIME DEFAULT CURRENT_TIMESTAMP,
                status ENUM('ยังไม่เริ่มดำเนินการ','กำลังเริ่มดำเนินการ','ดำเนินการแล้ว') DEFAULT 'ยังไม่เริ่มดำเนินการ',
                admin_result TEXT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางแจ้งปัญหาและคำตอบจากแอดมิน'",

            // 9. tb_product
            "CREATE TABLE IF NOT EXISTS tb_product (
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางสินค้าประจำตู้'",

            // 10. tb_product_redeem
            "CREATE TABLE IF NOT EXISTS tb_product_redeem (
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
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='ตารางคำขอแลกสินค้าของลูกค้า'"
        ];

        foreach ($queries as $sql) {
            try {
                $this->db->exec($sql);
                echo "Success: Created or verified table structure.\n";
            } catch (\PDOException $e) {
                echo "Error creating table: " . $e->getMessage() . "\n";
            }
        }
    }

    private function migrateColumns() {
        $tables = [
            'tb_config',
            'tb_pointrate',
            'tb_member',
            'tb_pointlog',
            'tb_redeem_request',
            'tb_product',
            'tb_product_redeem'
        ];

        // 1. Rename m_id -> machine_id (compatible with MariaDB 10.4 and MySQL 8)
        foreach ($tables as $table) {
            try {
                $stmt = $this->db->prepare(
                    'SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name
                     AND COLUMN_NAME = \'m_id\''
                );
                $stmt->execute([':table_name' => $table]);

                if ((int)$stmt->fetchColumn() > 0) {
                    $this->db->exec("ALTER TABLE `{$table}` CHANGE COLUMN `m_id` `machine_id` INT NULL");
                }
            } catch (\PDOException $e) {
                echo "Error migrating {$table} m_id: " . $e->getMessage() . "\n";
            }
        }

        // 2. Rename u_id -> member_id in tb_pointlog
        try {
            $stmt = $this->db->prepare(
                'SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = \'tb_pointlog\'
                 AND COLUMN_NAME = \'u_id\''
            );
            $stmt->execute();

            if ((int)$stmt->fetchColumn() > 0) {
                $this->db->exec("ALTER TABLE `tb_pointlog` CHANGE COLUMN `u_id` `member_id` INT NULL");
            }
        } catch (\PDOException $e) {
            echo "Error migrating tb_pointlog u_id: " . $e->getMessage() . "\n";
        }

        // 3. Add shop_id, serial_number, pairing_code to tb_machine
        $machineCols = [
            'shop_id' => 'ALTER TABLE tb_machine ADD COLUMN shop_id INT DEFAULT NULL AFTER op_id',
            'serial_number' => 'ALTER TABLE tb_machine ADD COLUMN serial_number VARCHAR(100) DEFAULT NULL AFTER shop_id',
            'pairing_code' => 'ALTER TABLE tb_machine ADD COLUMN pairing_code VARCHAR(16) DEFAULT NULL AFTER serial_number'
        ];
        foreach ($machineCols as $col => $sql) {
            try {
                $stmt = $this->db->prepare("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tb_machine' AND COLUMN_NAME = :col");
                $stmt->execute([':col' => $col]);
                if ((int)$stmt->fetchColumn() == 0) {
                    $this->db->exec($sql);
                }
            } catch (\PDOException $e) {}
        }

        // 4. Add u_id, birthday, money to tb_member
        $memberCols = [
            'u_id' => 'ALTER TABLE tb_member ADD COLUMN u_id INT DEFAULT NULL AFTER id',
            'birthday' => 'ALTER TABLE tb_member ADD COLUMN birthday DATE DEFAULT NULL AFTER lname',
            'money' => 'ALTER TABLE tb_member ADD COLUMN money DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER point'
        ];
        foreach ($memberCols as $col => $sql) {
            try {
                $stmt = $this->db->prepare("SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tb_member' AND COLUMN_NAME = :col");
                $stmt->execute([':col' => $col]);
                if ((int)$stmt->fetchColumn() == 0) {
                    $this->db->exec($sql);
                }
            } catch (\PDOException $e) {}
        }

        // 5. Ensure role in tb_user includes 'shop'
        try {
            $this->db->exec("ALTER TABLE `tb_user` MODIFY COLUMN `role` ENUM('operator','admin','shop') DEFAULT 'operator'");
        } catch (\PDOException $e) {}
    }

    public function dropTables() {
        $queries = [
            "SET FOREIGN_KEY_CHECKS = 0",
            "DROP TABLE IF EXISTS tb_user",
            "DROP TABLE IF EXISTS tb_member",
            "DROP TABLE IF EXISTS tb_pointrate",
            "DROP TABLE IF EXISTS tb_config",
            "DROP TABLE IF EXISTS tb_machine",
            "DROP TABLE IF EXISTS tb_pointlog",
            "DROP TABLE IF EXISTS tb_redeem_request",
            "DROP TABLE IF EXISTS tb_issue_report",
            "DROP TABLE IF EXISTS tb_product_redeem",
            "DROP TABLE IF EXISTS tb_product",
            "SET FOREIGN_KEY_CHECKS = 1"
        ];

        foreach ($queries as $sql) {
            $this->db->exec($sql);
        }
        echo "All tables dropped.\n";
    }
}
