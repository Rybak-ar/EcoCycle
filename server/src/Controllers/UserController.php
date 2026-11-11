<?php

namespace App\Controllers;

use App\Models\member\Member;

class UserController extends BaseController
{
    protected $memberModel;
    private $secret_key;

    public function __construct()
    {
        $this->memberModel = new Member();
        $this->secret_key = $_ENV['JWT_SECRET'] ?? 'default_secret';
    }

    // ลงทะเบียน แต่ละตู้ 
    public function register($machine_id)
    {
        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['phonenumber', 'fname', 'lname']);

        // ตรวจสอบว่าเคยลงทะเบียนกับตู้นี้หรือยัง
        $existing = $this->memberModel->getByPhoneAndMachine($data['phonenumber'], $machine_id);
        if ($existing) {
            $this->jsonResponse(['status' => 'error', 'message' => 'หมายเลขนี้ลงทะเบียนกับตู้นี้แล้ว'], 400);
        }

        $insertData = [
            'machine_id' => $machine_id,
            'phonenumber' => $data['phonenumber'],
            'fname' => $data['fname'],
            'lname' => $data['lname'],
            'birthday' => $data['birthday'] ?? null,
            'gender' => $data['gender'] ?? null,
            'localtion' => $data['localtion'] ?? null,
            'point' => 0,
            'money' => 0.00
        ];

        $created = $this->memberModel->Create($insertData);

        if ($created) {
            $this->jsonResponse(['status' => 'success', 'message' => 'ลงทะเบียนสำเร็จ'], 201);
        }
        $this->jsonResponse(['status' => 'error', 'message' => 'เกิดข้อผิดพลาดในการลงทะเบียน'], 500);
    }

    // เข้าสู่ระบบหน้าตู้ด้วยหมายเลขโทรศัพท์
    public function login($machine_id)
    {
        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['phonenumber']);

        $member = $this->memberModel->getByPhoneAndMachine($data['phonenumber'], $machine_id);

        if ($member) {
            $payload = [
                "member_id" => $member['id'],
                "machine_id" => $machine_id,
                "m_id" => $machine_id, // คงไว้สำหรับ backward compatibility
                "role" => "user",
                "exp" => time() + (86400 * 30),
            ];

            $header = json_encode(['typ' => 'JWT', 'alg' => 'HS256']);
            $payloadEncoded = json_encode($payload);

            $base64UrlHeader = str_replace(['+', '/', '='], ['-', '_', ''], base64_encode($header));
            $base64UrlPayload = str_replace(['+', '/', '='], ['-', '_', ''], base64_encode($payloadEncoded));

            $signature = hash_hmac('sha256', $base64UrlHeader . "." . $base64UrlPayload, $this->secret_key, true);
            $base64UrlSignature = str_replace(['+', '/', '='], ['-', '_', ''], base64_encode($signature));

            $jwt = $base64UrlHeader . "." . $base64UrlPayload . "." . $base64UrlSignature;

            $this->jsonResponse([
                'status' => 'success',
                'message' => 'เข้าสู่ระบบสำเร็จ',
                'token' => $jwt,
                'data' => [
                    'id' => $member['id'],
                    'fname' => $member['fname'],
                    'lname' => $member['lname'],
                    'point' => $member['point'],
                    'money' => $member['money'] ?? 0
                ]
            ], 200);
        }

        $this->jsonResponse(['status' => 'error', 'message' => 'ไม่พบหมายเลขนี้ในระบบ'], 404);
    }

    // ทำการรับขวดแล้วคำนวณแต้ม/เงิน (รายใบ)
    public function deposit($machine_id)
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        $tokenMachineId = $payload['machine_id'] ?? $payload['m_id'] ?? null;
        if (!isset($payload['member_id']) || $tokenMachineId != $machine_id) {
            $this->jsonResponse(['status' => 'error', 'message' => 'Token ไม่ถูกต้องหรือตู้ไม่ตรงกัน'], 401);
        }

        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['type', 'weight']);

        $type = $data['type']; // clear, opaque, brown
        $weight = floatval($data['weight']);

        $configModel = new \App\Models\machine\Config();
        $config = $configModel->getByMachineId($machine_id);

        if (!$config || !$config['allow']) {
            $this->jsonResponse(['status' => 'error', 'message' => 'ตู้นี้ยังไม่เปิดให้บริการ'], 403);
        }

        $pointrateModel = new \App\Models\machine\Pointrate();
        $rates = $pointrateModel->getByMachineId($machine_id);

        $rateValue = 0;
        foreach ($rates as $r) {
            if ($r['key'] === $type) {
                $rateValue = floatval($r['value']);
                break;
            }
        }

        if ($rateValue <= 0) {
            $this->jsonResponse(['status' => 'error', 'message' => 'ไม่มีการตั้งค่าเรทราคาสำหรับขวดประเภทนี้'], 400);
        }

        $earned = $rateValue * $weight;

        // อัปเดตแต้มของสมาชิก
        $member = $this->memberModel->findById($payload['member_id']);
        $newPoint = floatval($member['point']) + $earned;
        $this->memberModel->Update($member['id'], ['point' => $newPoint]);

        // บันทึกประวัติ (ทีละขวด) ด้วย member_id และ machine_id
        $pointlogModel = new \App\Models\machine\Pointlog();
        $pointlogModel->Create([
            'member_id' => $member['id'],
            'machine_id' => $machine_id,
            'bottle_type' => $type,
            'weight' => $weight,
            'point' => $earned
        ]);

        // อัปเดตยอดจำนวนขวดในตู้
        $machineModel = new \App\Models\machine\machine();
        $machine = $machineModel->findById($machine_id);
        $newCount = intval($machine['count'] ?? 0) + 1;
        $machineModel->Update($machine_id, ['count' => $newCount]);

        $this->jsonResponse([
            'status' => 'success',
            'message' => 'รับขวดสำเร็จ',
            'data' => [
                'earned' => $earned,
                'total_point' => $newPoint
            ]
        ], 200);
    }

    // รับขวดแบบเป็นชุด (Batch Deposit) สำหรับตู้ Kiosk
    public function batch_deposit($machine_id)
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['bottles']);

        $bottles = $data['bottles'];
        if (!is_array($bottles) || empty($bottles)) {
            $this->jsonResponse(['status' => 'error', 'message' => 'ไม่มีข้อมูลขวด'], 400);
        }

        $configModel = new \App\Models\machine\Config();
        $config = $configModel->getByMachineId($machine_id);
        if (!$config || $config['allow'] == 0) {
            $this->jsonResponse(['status' => 'error', 'message' => 'ตู้นี้ยังไม่เปิดให้บริการ'], 403);
        }

        $pointrateModel = new \App\Models\machine\Pointrate();
        $rates = $pointrateModel->getByMachineId($machine_id);
        
        $rateMap = [];
        foreach ($rates as $r) {
            $rateMap[$r['key']] = floatval($r['value']);
        }

        $totalEarned = 0;
        $totalWeight = 0;
        $bottleCount = count($bottles);

        foreach ($bottles as $b) {
            $type = $b['type'] ?? '';
            $weight = isset($b['weight']) ? floatval($b['weight']) : 1.0;
            
            $rateValue = $rateMap[$type] ?? 0;
            if ($rateValue > 0) {
                $totalEarned += ($rateValue * $weight);
                $totalWeight += $weight;
            }
        }

        if ($totalEarned <= 0) {
            $this->jsonResponse(['status' => 'error', 'message' => 'ไม่มีแต้มที่ได้จากรายการขวดนี้'], 400);
        }

        $member = $this->memberModel->findById($payload['member_id']);
        $newPoint = floatval($member['point']) + $totalEarned;
        $this->memberModel->Update($member['id'], ['point' => $newPoint]);

        // บันทึกประวัติทีละขวดแยกแถว ด้วย member_id และ machine_id
        $pointlogModel = new \App\Models\machine\Pointlog();
        foreach ($bottles as $b) {
            $type = $b['type'] ?? '';
            $weight = isset($b['weight']) ? floatval($b['weight']) : 1.0;
            $rateValue = $rateMap[$type] ?? 0;
            if ($rateValue > 0) {
                $earned = $rateValue * $weight;
                $pointlogModel->Create([
                    'member_id' => $member['id'],
                    'machine_id' => $machine_id,
                    'bottle_type' => $type,
                    'weight' => $weight,
                    'point' => $earned
                ]);
            }
        }

        $machineModel = new \App\Models\machine\machine();
        $machine = $machineModel->findById($machine_id);
        $newCount = intval($machine['count'] ?? 0) + $bottleCount;
        $machineModel->Update($machine_id, ['count' => $newCount]);

        $this->jsonResponse([
            'status' => 'success',
            'message' => 'รับขวดสำเร็จ (รวม ' . $bottleCount . ' ขวด)',
            'data' => [
                'earned' => $totalEarned,
                'total_point' => $newPoint
            ]
        ], 200);
    }

    // แลกแต้ม/แลกเงิน
    public function redeem($machine_id)
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        $tokenMachineId = $payload['machine_id'] ?? $payload['m_id'] ?? null;
        if (!isset($payload['member_id']) || $tokenMachineId != $machine_id) {
            $this->jsonResponse(['status' => 'error', 'message' => 'Token ไม่ถูกต้องหรือตู้ไม่ตรงกัน'], 401);
        }

        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['amount']);

        $amount = floatval($data['amount']);
        if ($amount <= 0) {
            $this->jsonResponse(['status' => 'error', 'message' => 'จำนวนที่ต้องการแลกต้องมากกว่า 0'], 400);
        }

        $member = $this->memberModel->findById($payload['member_id']);
        $currentPoint = floatval($member['point']);

        if ($currentPoint < $amount) {
            $this->jsonResponse(['status' => 'error', 'message' => 'แต้ม/ยอดเงิน ไม่เพียงพอสำหรับการแลก'], 400);
        }

        $newPoint = $currentPoint - $amount;
        $this->memberModel->Update($member['id'], ['point' => $newPoint]);

        $pointlogModel = new \App\Models\machine\Pointlog();
        $pointlogModel->Create([
            'member_id' => $member['id'],
            'machine_id' => $machine_id,
            'point' => -$amount
        ]);

        $this->jsonResponse([
            'status' => 'success',
            'message' => 'แลกเปลี่ยนสำเร็จ',
            'data' => [
                'redeemed_amount' => $amount,
                'remaining_point' => $newPoint
            ]
        ], 200);
    }

    // ดูข้อมูลโปรไฟล์ปัจจุบัน
    public function getProfile()
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        if (isset($payload['member_id'])) {
            $member = $this->memberModel->findById($payload['member_id']);
            if ($member) {
                $this->jsonResponse([
                    'status' => 'success',
                    'data' => [
                        'id' => $member['id'],
                        'fname' => $member['fname'],
                        'lname' => $member['lname'],
                        'phonenumber' => $member['phonenumber'],
                        'point' => $member['point'],
                        'money' => $member['money'] ?? 0
                    ]
                ], 200);
            }
        }
        $this->jsonResponse(['status' => 'error', 'message' => 'ไม่พบข้อมูลผู้ใช้'], 404);
    }

    public function updateProfile()
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        if (!isset($payload['member_id'])) {
            $this->jsonResponse(['status' => 'error', 'message' => 'Unauthorized'], 401);
        }

        $data = $this->getJsonInput();
        $updateFields = [];
        foreach (['fname', 'lname', 'gender', 'birthday', 'localtion'] as $f) {
            if (isset($data[$f])) {
                $updateFields[$f] = $data[$f];
            }
        }

        if (!empty($updateFields)) {
            $this->memberModel->Update($payload['member_id'], $updateFields);
        }

        $this->jsonResponse(['status' => 'success', 'message' => 'อัปเดตข้อมูลส่วนตัวสำเร็จ'], 200);
    }

    public function getUserProfileById($id)
    {
        $member = $this->memberModel->findById($id);
        if ($member) {
            $this->jsonResponse([
                'status' => 'success',
                'data' => [
                    'id' => $member['id'],
                    'fname' => $member['fname'],
                    'lname' => $member['lname'],
                    'phonenumber' => $member['phonenumber'],
                    'point' => $member['point'],
                    'money' => $member['money'] ?? 0
                ]
            ], 200);
        }
        $this->jsonResponse(['status' => 'error', 'message' => 'ไม่พบข้อมูลผู้ใช้'], 404);
    }

    // ดูประวัติการหยอดขวดของสมาชิก
    public function getHistory()
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        if (!isset($payload['member_id'])) {
            $this->jsonResponse(['status' => 'error', 'message' => 'Unauthorized'], 401);
        }

        $db = (new \Config\Database())->connect();
        $stmt = $db->prepare(
            "SELECT l.*, m.name as machine_name 
             FROM tb_pointlog l 
             LEFT JOIN tb_machine m ON l.machine_id = m.id 
             WHERE l.member_id = :member_id 
             ORDER BY l.createat DESC LIMIT 50"
        );
        $stmt->execute([':member_id' => $payload['member_id']]);
        $history = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse(['status' => 'success', 'data' => $history], 200);
    }

    public function createIssueReport()
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['title', 'description']);

        $db = (new \Config\Database())->connect();
        $stmt = $db->prepare("INSERT INTO tb_issue_report (user_id, title, description) VALUES (:uid, :title, :desc)");
        $stmt->execute([
            ':uid' => $payload['member_id'] ?? $payload['id'],
            ':title' => $data['title'],
            ':desc' => $data['description']
        ]);

        $this->jsonResponse(['status' => 'success', 'message' => 'แจ้งปัญหาเรียบร้อยแล้ว'], 201);
    }

    public function getUserIssues()
    {
        $auth = new \App\Middleware\AuthMiddleware();
        $payload = $auth->checkToken();

        $uid = $payload['member_id'] ?? $payload['id'];
        $db = (new \Config\Database())->connect();
        $stmt = $db->prepare("SELECT * FROM tb_issue_report WHERE user_id = :uid ORDER BY createat DESC");
        $stmt->execute([':uid' => $uid]);
        $issues = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse(['status' => 'success', 'data' => $issues], 200);
    }

    // ดึงข้อมูลสถานะตู้ (จำนวนขวดและการตั้งค่า) สำหรับ Kiosk & Dashboard
    public function getMachineStatus($machine_id)
    {
        $machineModel = new \App\Models\machine\machine();
        $machine = $machineModel->findById($machine_id);

        if (!$machine) {
            $this->jsonResponse(['status' => 'error', 'message' => 'ไม่พบข้อมูลตู้'], 404);
            return;
        }

        $configModel = new \App\Models\machine\Config();
        $config = $configModel->getByMachineId($machine_id);

        $pointrateModel = new \App\Models\machine\Pointrate();
        $rates = $pointrateModel->getByMachineId($machine_id);
        $rateData = [];
        $isMoney = ($config && $config['type'] === 'money');
        foreach ($rates as $r) {
            $val = floatval($r['value']);
            if ($isMoney) {
                $val = $val / 0.8;
            }
            $rateData[$r['key']] = $val;
        }

        $this->jsonResponse([
            'status' => 'success',
            'data' => [
                'count' => intval($machine['count'] ?? 0),
                'type' => $config ? $config['type'] : 'point',
                'allow' => $config ? boolval($config['allow']) : false,
                'rates' => $rateData,
                'serial_number' => $machine['serial_number'] ?? '',
                'name' => $machine['name'] ?? '',
                'location' => $machine['location'] ?? '',
                'pairing_code' => $machine['pairing_code'] ?? ''
            ]
        ], 200);
    }
}
