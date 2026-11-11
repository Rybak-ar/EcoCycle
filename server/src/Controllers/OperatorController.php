<?php

namespace App\Controllers;

use App\Models\machine\Config;
use App\Models\machine\Pointrate;
use App\Models\member\Member;

class OperatorController extends BaseController
{
    protected $configModel;
    protected $pointrateModel;
    protected $memberModel;

    public function __construct()
    {
        $this->configModel = new Config();
        $this->pointrateModel = new Pointrate();
        $this->memberModel = new Member();
    }

    // ตั้งค่าตู้ rate / config
    public function updateMachineConfig($machine_id)
    {
        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['type']); // type: point or money

        $config = $this->configModel->getByMachineId($machine_id);
        $db = (new \Config\Database())->connect();
        
        // ตรวจสอบว่ามีเครื่องใน tb_machine หรือไม่ หากไม่มีให้สร้างอัตโนมัติเพื่อป้องกัน Foreign Key error
        $checkMachine = $db->prepare("SELECT id FROM tb_machine WHERE id = :mid");
        $checkMachine->execute([':mid' => $machine_id]);
        if (!$checkMachine->fetch()) {
            $insMachine = $db->prepare("INSERT INTO tb_machine (id, name, status) VALUES (:mid, :name, 'active')");
            $insMachine->execute([':mid' => $machine_id, ':name' => "EcoCycle Pro #{$machine_id}"]);
        }

        if ($config) {
            $stmt = $db->prepare("UPDATE tb_config SET `type` = :type WHERE `id` = :id");
            $stmt->execute([':type' => $data['type'], ':id' => $config['id']]);
        } else {
            $stmt = $db->prepare("INSERT INTO tb_config (`machine_id`, `type`, `allow`) VALUES (:machine_id, :type, 0)");
            $stmt->execute([':machine_id' => $machine_id, ':type' => $data['type']]);
        }

        // กรณี money ให้คิดเรทเงินประมาณ 80% ของราคาขายขวดต่อน้ำหนัก 1 กรัม 
        if ($data['type'] === 'money' && isset($data['base_prices'])) {
            $this->pointrateModel->deleteByMachineId($machine_id);
            foreach ($data['base_prices'] as $key => $price) {
                $rateValue = floatval($price) * 0.8;
                $this->pointrateModel->Create([
                    'machine_id' => $machine_id,
                    'key' => $key,
                    'value' => $rateValue
                ]);
            }
        } elseif ($data['type'] === 'point' && isset($data['rates'])) {
            $this->pointrateModel->deleteByMachineId($machine_id);
            foreach ($data['rates'] as $key => $value) {
                $this->pointrateModel->Create([
                    'machine_id' => $machine_id,
                    'key' => $key,
                    'value' => floatval($value)
                ]);
            }
        }

        if (isset($data['serial_number'])) {
            $machineModel = new \App\Models\machine\machine();
            $machineModel->Update($machine_id, ['serial_number' => trim($data['serial_number'])]);
        }

        $this->jsonResponse(['status' => 'success', 'message' => 'อัปเดตการตั้งค่าสำเร็จ'], 200);
    }

    // อัปเดตเฉพาะ Serial Number
    public function updateSerialNumber($machine_id)
    {
        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['serial_number']);

        $machineModel = new \App\Models\machine\machine();
        $machineModel->Update($machine_id, ['serial_number' => trim($data['serial_number'])]);

        $this->jsonResponse(['status' => 'success', 'message' => 'บันทึก Serial Number สำเร็จ'], 200);
    }

    // ดูการตั้งค่าตู้
    public function getMachineConfig($machine_id)
    {
        $config = $this->configModel->getByMachineId($machine_id);
        $rates = $this->pointrateModel->getByMachineId($machine_id);

        $rateData = [];
        foreach ($rates as $r) {
            $rateData[$r['key']] = floatval($r['value']);
        }

        $machineModel = new \App\Models\machine\machine();
        $machine = $machineModel->findById($machine_id);

        $this->jsonResponse([
            'status' => 'success',
            'data' => [
                'type' => $config ? $config['type'] : 'point',
                'allow' => $config ? boolval($config['allow']) : false,
                'rates' => $rateData,
                'serial_number' => $machine['serial_number'] ?? '',
                'name' => $machine['name'] ?? '',
                'pairing_code' => $machine['pairing_code'] ?? ''
            ]
        ], 200);
    }

    // ดูรายชื่อและแต้มสะสมของผู้ใช้ในตู้
    public function getMachineUsers($machine_id)
    {
        $db = (new \Config\Database())->connect();
        
        $sql = "SELECT m.id, m.phonenumber, m.fname, m.lname, m.point, m.money, m.createat 
                FROM tb_member m 
                WHERE m.machine_id = :machine_id";
        $stmt = $db->prepare($sql);
        $stmt->execute([':machine_id' => $machine_id]);
        $users = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $totalUsers = count($users);

        $this->jsonResponse([
            'status' => 'success',
            'data' => [
                'total_users' => $totalUsers,
                'members' => $users
            ]
        ], 200);
    }

    // ดึงประวัติการหยอดขวด (Logs) ทั้งหมดเรียงตามเวลาล่าสุด
    public function getMachineLogs($machine_id)
    {
        $db = (new \Config\Database())->connect();
        
        $sql = "SELECT l.id, l.machine_id, l.bottle_type, l.weight, l.point, l.createat, m.phonenumber, m.fname, m.lname
                FROM tb_pointlog l
                LEFT JOIN tb_member m ON l.member_id = m.id
                WHERE l.machine_id = :machine_id
                ORDER BY l.createat DESC";
        $stmt = $db->prepare($sql);
        $stmt->execute([':machine_id' => $machine_id]);
        $logs = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse([
            'status' => 'success',
            'total_count' => count($logs),
            'data' => $logs
        ], 200);
    }

    // ดูคำขอแลกแต้ม/เงิน
    public function getRedeemRequests($machine_id)
    {
        $db = (new \Config\Database())->connect();
        $sql = "SELECT r.*, m.fname, m.lname, m.phonenumber 
                FROM tb_redeem_request r 
                LEFT JOIN tb_member m ON r.u_id = m.id 
                WHERE r.machine_id = :machine_id 
                ORDER BY r.createat DESC";
        $stmt = $db->prepare($sql);
        $stmt->execute([':machine_id' => $machine_id]);
        $requests = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse(['status' => 'success', 'data' => $requests], 200);
    }

    public function approveRedeem($id)
    {
        $db = (new \Config\Database())->connect();
        $stmt = $db->prepare("UPDATE tb_redeem_request SET status = 'approved' WHERE id = :id");
        $stmt->execute([':id' => $id]);
        $this->jsonResponse(['status' => 'success', 'message' => 'อนุมัติคำขอสำเร็จ'], 200);
    }

    public function rejectRedeem($id)
    {
        $db = (new \Config\Database())->connect();
        $stmt = $db->prepare("UPDATE tb_redeem_request SET status = 'rejected' WHERE id = :id");
        $stmt->execute([':id' => $id]);
        $this->jsonResponse(['status' => 'success', 'message' => 'ปฏิเสธคำขอสำเร็จ'], 200);
    }

    // จัดการรายงานปัญหา (Issue Reports)
    public function getIssueReports()
    {
        $db = (new \Config\Database())->connect();
        $sql = "SELECT i.*, u.op_name, u.phonenumber 
                FROM tb_issue_report i 
                LEFT JOIN tb_user u ON i.user_id = u.id 
                ORDER BY i.createat DESC";
        $stmt = $db->query($sql);
        $issues = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse(['status' => 'success', 'data' => $issues], 200);
    }

    public function createIssueReport()
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['title', 'description']);

        $db = (new \Config\Database())->connect();
        $stmt = $db->prepare("INSERT INTO tb_issue_report (user_id, title, description) VALUES (:user_id, :title, :desc)");
        $stmt->execute([
            ':user_id' => $payload['id'] ?? $payload['user_id'],
            ':title' => $data['title'],
            ':desc' => $data['description']
        ]);

        $this->jsonResponse(['status' => 'success', 'message' => 'ส่งรายงานปัญหาสำเร็จ'], 201);
    }

    public function updateIssueReport($id)
    {
        $data = $this->getJsonInput();
        $db = (new \Config\Database())->connect();
        
        $fields = [];
        $params = [':id' => $id];

        if (isset($data['status'])) {
            $fields[] = "`status` = :status";
            $params[':status'] = $data['status'];
        }
        if (isset($data['admin_result'])) {
            $fields[] = "`admin_result` = :admin_result";
            $params[':admin_result'] = $data['admin_result'];
        }

        if (empty($fields)) {
            $this->jsonResponse(['status' => 'error', 'message' => 'ไม่มีข้อมูลสำหรับอัปเดต'], 400);
        }

        $sql = "UPDATE tb_issue_report SET " . implode(', ', $fields) . " WHERE id = :id";
        $stmt = $db->prepare($sql);
        $stmt->execute($params);

        $this->jsonResponse(['status' => 'success', 'message' => 'อัปเดตรายงานปัญหาสำเร็จ'], 200);
    }

    // สร้าง Pairing Code สำหรับผูกตู้
    public function generatePairingCode($id)
    {
        $code = strtoupper(substr(bin2hex(random_bytes(4)), 0, 8));
        $db = (new \Config\Database())->connect();
        $stmt = $db->prepare("UPDATE tb_machine SET pairing_code = :code WHERE id = :id");
        $stmt->execute([':code' => $code, ':id' => $id]);

        $this->jsonResponse([
            'status' => 'success',
            'data' => [
                'pairing_code' => $code
            ]
        ], 200);
    }
}
