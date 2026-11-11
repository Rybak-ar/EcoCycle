<?php

namespace App\Controllers;

class ShopController extends BaseController
{
    protected $db;

    public function __construct()
    {
        $this->db = (new \Config\Database())->connect();
    }

    // ดูรายการตู้สำหรับร้านค้า
    public function getShopMachines()
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        $stmt = $this->db->prepare("SELECT * FROM tb_machine WHERE shop_id = :shop_id OR op_id = :op_id");
        $stmt->execute([
            ':shop_id' => $payload['id'] ?? 0,
            ':op_id' => $payload['id'] ?? 0
        ]);
        $machines = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse(['status' => 'success', 'data' => $machines], 200);
    }

    // ดูสินค้าประจำตู้
    public function getMachineProducts($machine_id)
    {
        $stmt = $this->db->prepare("SELECT * FROM tb_product WHERE machine_id = :machine_id AND status != 'inactive' ORDER BY id DESC");
        $stmt->execute([':machine_id' => $machine_id]);
        $products = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse(['status' => 'success', 'data' => $products], 200);
    }

    // เพิ่มสินค้าประจำตู้
    public function addProduct($machine_id)
    {
        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['name', 'point_cost', 'stock']);

        $stmt = $this->db->prepare(
            "INSERT INTO tb_product (machine_id, name, description, image_url, cost_type, point_cost, stock, status) 
             VALUES (:machine_id, :name, :desc, :img, :cost_type, :point_cost, :stock, :status)"
        );
        $stmt->execute([
            ':machine_id' => $machine_id,
            ':name' => $data['name'],
            ':desc' => $data['description'] ?? null,
            ':img' => $data['image_url'] ?? null,
            ':cost_type' => $data['cost_type'] ?? 'point',
            ':point_cost' => floatval($data['point_cost']),
            ':stock' => intval($data['stock']),
            ':status' => $data['status'] ?? 'active'
        ]);

        $this->jsonResponse(['status' => 'success', 'message' => 'เพิ่มสินค้าสำเร็จ', 'id' => $this->db->lastInsertId()], 201);
    }

    // แก้ไขสินค้า
    public function updateProduct($id)
    {
        $data = $this->getJsonInput();
        $fields = [];
        $params = [':id' => $id];

        foreach (['name', 'description', 'image_url', 'cost_type', 'point_cost', 'stock', 'status'] as $key) {
            if (isset($data[$key])) {
                $fields[] = "`$key` = :$key";
                $params[":$key"] = $data[$key];
            }
        }

        if (empty($fields)) {
            $this->jsonResponse(['status' => 'error', 'message' => 'ไม่มีข้อมูลสำหรับอัปเดต'], 400);
        }

        $sql = "UPDATE tb_product SET " . implode(', ', $fields) . " WHERE id = :id";
        $stmt = $this->db->prepare($sql);
        $stmt->execute($params);

        $this->jsonResponse(['status' => 'success', 'message' => 'อัปเดตสินค้าสำเร็จ'], 200);
    }

    // ลบสินค้า
    public function deleteProduct($id)
    {
        $stmt = $this->db->prepare("DELETE FROM tb_product WHERE id = :id");
        $stmt->execute([':id' => $id]);
        $this->jsonResponse(['status' => 'success', 'message' => 'ลบสินค้าสำเร็จ'], 200);
    }

    // สรุปยอดร้านค้า
    public function getShopStats($machine_id)
    {
        $totalProducts = $this->db->query("SELECT COUNT(*) FROM tb_product WHERE machine_id = " . intval($machine_id))->fetchColumn();
        $totalRedeemed = $this->db->query("SELECT COUNT(*) FROM tb_product_redeem WHERE machine_id = " . intval($machine_id) . " AND status = 'completed'")->fetchColumn();
        $pendingRedeems = $this->db->query("SELECT COUNT(*) FROM tb_product_redeem WHERE machine_id = " . intval($machine_id) . " AND status = 'pending'")->fetchColumn();

        $this->jsonResponse([
            'status' => 'success',
            'data' => [
                'total_products' => $totalProducts,
                'total_redeemed' => $totalRedeemed,
                'pending_redeems' => $pendingRedeems
            ]
        ], 200);
    }

    // รายการแลกสินค้าของตู้
    public function getProductRedeems($machine_id)
    {
        $stmt = $this->db->prepare(
            "SELECT r.*, p.name as product_name, p.image_url, m.fname, m.lname, m.phonenumber 
             FROM tb_product_redeem r 
             JOIN tb_product p ON r.product_id = p.id 
             JOIN tb_member m ON r.u_id = m.id 
             WHERE r.machine_id = :machine_id 
             ORDER BY r.created_at DESC"
        );
        $stmt->execute([':machine_id' => $machine_id]);
        $redeems = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse(['status' => 'success', 'data' => $redeems], 200);
    }

    // ตรวจสอบโค้ดแลกสินค้า
    public function verifyRedeemCode($machine_id)
    {
        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['redeem_code']);

        $stmt = $this->db->prepare(
            "SELECT r.*, p.name as product_name, p.point_cost, m.fname, m.lname, m.phonenumber 
             FROM tb_product_redeem r 
             JOIN tb_product p ON r.product_id = p.id 
             JOIN tb_member m ON r.u_id = m.id 
             WHERE r.machine_id = :machine_id AND r.redeem_code = :code"
        );
        $stmt->execute([
            ':machine_id' => $machine_id,
            ':code' => trim($data['redeem_code'])
        ]);
        $item = $stmt->fetch(\PDO::FETCH_ASSOC);

        if ($item) {
            $this->jsonResponse(['status' => 'success', 'data' => $item], 200);
        }
        $this->jsonResponse(['status' => 'error', 'message' => 'ไม่พบรหัสแลกสินค้า หรือรหัสไม่ถูกต้อง'], 404);
    }

    // ยืนยันการรับสินค้า
    public function confirmProductRedeem($id)
    {
        $stmt = $this->db->prepare("UPDATE tb_product_redeem SET status = 'completed', completed_at = NOW() WHERE id = :id AND status = 'pending'");
        $stmt->execute([':id' => $id]);

        if ($stmt->rowCount() > 0) {
            $this->jsonResponse(['status' => 'success', 'message' => 'ยืนยันการรับของรางวัลสำเร็จ'], 200);
        }
        $this->jsonResponse(['status' => 'error', 'message' => 'ไม่พบรายการที่รอยืนยัน'], 400);
    }

    // ปฏิเสธการแลกสินค้า (คืนแต้มให้สมาชิก)
    public function rejectProductRedeem($id)
    {
        $stmt = $this->db->prepare("SELECT * FROM tb_product_redeem WHERE id = :id AND status = 'pending'");
        $stmt->execute([':id' => $id]);
        $redeem = $stmt->fetch(\PDO::FETCH_ASSOC);

        if (!$redeem) {
            $this->jsonResponse(['status' => 'error', 'message' => 'ไม่พบรายการที่รอดำเนินการ'], 404);
        }

        // คืนแต้มให้สมาชิก
        $this->db->prepare("UPDATE tb_member SET point = point + :pts WHERE id = :uid")
                 ->execute([':pts' => $redeem['points_used'], ':uid' => $redeem['u_id']]);

        // คืนสต็อก
        $this->db->prepare("UPDATE tb_product SET stock = stock + :qty WHERE id = :pid")
                 ->execute([':qty' => $redeem['quantity'], ':pid' => $redeem['product_id']]);

        // ปรับสถานะเป็น cancelled
        $this->db->prepare("UPDATE tb_product_redeem SET status = 'cancelled' WHERE id = :id")
                 ->execute([':id' => $id]);

        $this->jsonResponse(['status' => 'success', 'message' => 'ยกเลิกรายการและคืนแต้มเรียบร้อย'], 200);
    }

    // ผูกตู้กับร้านค้าด้วย Pairing code
    public function linkMachine()
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['pairing_code']);

        $stmt = $this->db->prepare("SELECT * FROM tb_machine WHERE pairing_code = :code");
        $stmt->execute([':code' => trim($data['pairing_code'])]);
        $machine = $stmt->fetch(\PDO::FETCH_ASSOC);

        if ($machine) {
            $update = $this->db->prepare("UPDATE tb_machine SET shop_id = :shop_id, pairing_code = NULL WHERE id = :id");
            $update->execute([
                ':shop_id' => $payload['id'],
                ':id' => $machine['id']
            ]);
            $this->jsonResponse(['status' => 'success', 'message' => 'ผูกตู้กับร้านค้าสำเร็จ', 'data' => $machine], 200);
        }

        $this->jsonResponse(['status' => 'error', 'message' => 'รหัสจับคู่ไม่ถูกต้องหรือหมดอายุ'], 400);
    }

    // สมาชิกแลกสินค้าด้วยแต้ม
    public function redeemProduct($machine_id)
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['product_id']);

        $productId = intval($data['product_id']);
        $quantity = isset($data['quantity']) ? max(1, intval($data['quantity'])) : 1;
        $memberId = $payload['member_id'];

        // ตรวจสอบสินค้าและสต็อก
        $stmt = $this->db->prepare("SELECT * FROM tb_product WHERE id = :pid AND machine_id = :mid AND status = 'active'");
        $stmt->execute([':pid' => $productId, ':mid' => $machine_id]);
        $product = $stmt->fetch(\PDO::FETCH_ASSOC);

        if (!$product) {
            $this->jsonResponse(['status' => 'error', 'message' => 'ไม่พบสินค้านี้ในตู้'], 404);
        }
        if ($product['stock'] < $quantity) {
            $this->jsonResponse(['status' => 'error', 'message' => 'สินค้าในสต็อกไม่เพียงพอ'], 400);
        }

        $totalPointsNeeded = floatval($product['point_cost']) * $quantity;

        // ตรวจสอบแต้มสมาชิก
        $memStmt = $this->db->prepare("SELECT * FROM tb_member WHERE id = :mid");
        $memStmt->execute([':mid' => $memberId]);
        $member = $memStmt->fetch(\PDO::FETCH_ASSOC);

        if (!$member || floatval($member['point']) < $totalPointsNeeded) {
            $this->jsonResponse(['status' => 'error', 'message' => 'แต้มสะสมของคุณไม่เพียงพอสำหรับการแลก'], 400);
        }

        // ตัดแต้มสมาชิก
        $this->db->prepare("UPDATE tb_member SET point = point - :pts WHERE id = :mid")
                 ->execute([':pts' => $totalPointsNeeded, ':mid' => $memberId]);

        // ลดสต็อกสินค้า
        $this->db->prepare("UPDATE tb_product SET stock = stock - :qty WHERE id = :pid")
                 ->execute([':qty' => $quantity, ':pid' => $productId]);

        // สร้าง Redeem Code 6 หลัก
        $redeemCode = strtoupper(substr(bin2hex(random_bytes(3)), 0, 6));

        $ins = $this->db->prepare(
            "INSERT INTO tb_product_redeem (machine_id, u_id, product_id, redeem_code, quantity, points_used, status) 
             VALUES (:mid, :uid, :pid, :code, :qty, :pts, 'pending')"
        );
        $ins->execute([
            ':mid' => $machine_id,
            ':uid' => $memberId,
            ':pid' => $productId,
            ':code' => $redeemCode,
            ':qty' => $quantity,
            ':pts' => $totalPointsNeeded
        ]);

        $this->jsonResponse([
            'status' => 'success',
            'message' => 'แลกสินค้าสำเร็จ',
            'data' => [
                'redeem_code' => $redeemCode,
                'points_used' => $totalPointsNeeded,
                'remaining_points' => floatval($member['point']) - $totalPointsNeeded
            ]
        ], 200);
    }

    // ดูประวัติการแลกสินค้าของสมาชิก
    public function getMemberProductRedeems()
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        $stmt = $this->db->prepare(
            "SELECT r.*, p.name as product_name, p.image_url, m.name as machine_name 
             FROM tb_product_redeem r 
             JOIN tb_product p ON r.product_id = p.id 
             JOIN tb_machine m ON r.machine_id = m.id 
             WHERE r.u_id = :uid 
             ORDER BY r.created_at DESC"
        );
        $stmt->execute([':uid' => $payload['member_id']]);
        $redeems = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse(['status' => 'success', 'data' => $redeems], 200);
    }
}
