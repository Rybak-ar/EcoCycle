<?php

namespace App\Controllers;

use App\Models\machine\machine;
use App\Models\user\User;
use App\Models\machine\Config;

class AdminController extends BaseController
{
    protected $machineModel;
    protected $userModel;
    protected $configModel;

    public function __construct()
    {
        $this->machineModel = new machine();
        $this->userModel = new User();
        $this->configModel = new Config();
    }

    public function getMachines()
    {
        $db = (new \Config\Database())->connect();
        $sql = "SELECT m.*, u.op_name, u.email, c.allow, c.type 
                FROM tb_machine m 
                LEFT JOIN tb_user u ON m.op_id = u.id
                LEFT JOIN tb_config c ON m.id = c.machine_id
                ORDER BY u.id, m.id";
        $stmt = $db->query($sql);
        $machines = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse([
            'status' => 'success',
            'data' => $machines
        ], 200);
    }

    public function updateUserStatus($id)
    {
        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['permission']);
        
        $updated = $this->userModel->Update($id, ['permission' => $data['permission']]);
        if ($updated) {
            $this->jsonResponse(['status' => 'success', 'message' => 'อัปเดตสถานะเจ้าของตู้สำเร็จ'], 200);
        }
        $this->jsonResponse(['status' => 'error', 'message' => 'เกิดข้อผิดพลาดในการอัปเดต'], 500);
    }

    // จัดการสถานะตู้ (เช่น เปิด/ปิดตู้โดยแอดมิน)
    public function updateMachineStatus($id)
    {
        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['status']);
        
        $updated = $this->machineModel->Update($id, ['status' => $data['status']]);
        if ($updated) {
            $this->jsonResponse(['status' => 'success', 'message' => 'อัปเดตสถานะตู้สำเร็จ'], 200);
        }
        $this->jsonResponse(['status' => 'error', 'message' => 'เกิดข้อผิดพลาดในการอัปเดต'], 500);
    }

    // อนุมัติการออกตู้ใหม่เพื่อให้ใช้งานได้
    public function approveMachine($id)
    {
        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['allow']); // 1 or 0
        
        $config = $this->configModel->getByMachineId($id);
        if ($config) {
            $this->configModel->Update($config['id'], ['allow' => $data['allow']]);
        } else {
            $this->configModel->Create([
                'machine_id' => $id,
                'allow' => $data['allow'],
                'type' => 'point'
            ]);
        }

        $this->jsonResponse(['status' => 'success', 'message' => 'อนุมัติตู้สำเร็จ'], 200);
    }

    // ดูสรุปผลข้อมูลระบบ
    public function getDashboardStats()
    {
        $db = (new \Config\Database())->connect();
        
        $totalMachines = $db->query("SELECT COUNT(*) FROM tb_machine")->fetchColumn();
        $totalOperators = $db->query("SELECT COUNT(*) FROM tb_user WHERE role='operator'")->fetchColumn();
        $totalBottles = $db->query("SELECT SUM(count) FROM tb_machine")->fetchColumn() ?: 0;
        
        $this->jsonResponse([
            'status' => 'success',
            'data' => [
                'total_machines' => $totalMachines,
                'total_operators' => $totalOperators,
                'total_bottles' => $totalBottles
            ]
        ], 200);
    }

    // ดูรายชื่อผู้ประกอบการทั้งหมด
    public function getOperators()
    {
        $db = (new \Config\Database())->connect();
        $sql = "SELECT id, op_name, email, phonenumber, permission, role, createat FROM tb_user WHERE role IN ('operator', 'shop')";
        $stmt = $db->query($sql);
        $operators = $stmt->fetchAll(\PDO::FETCH_ASSOC);

        $this->jsonResponse([
            'status' => 'success',
            'data' => $operators
        ], 200);
    }

    // รายงานปัญหาสำหรับ Admin
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
}
