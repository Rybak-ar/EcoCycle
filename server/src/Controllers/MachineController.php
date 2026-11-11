<?php

namespace App\Controllers;

use App\Models\machine\machine;
use App\Models\user\User;

class MachineController extends BaseController
{
    protected $machine;

    public function __construct()
    {
        $this->machine = new machine();
    }

    public function getMachineByUser($id)
    {
        $userModel = new User();
        $user = $userModel->findById($id);

        if ($user) {
            $machine = $this->machine->getMachineByuserID($id);

            if ($machine) {
                $this->jsonResponse([
                    'status' => 'success',
                    'data' => $machine
                ], 200);
            } else {
                $this->jsonResponse([
                    'status' => 'error',
                    'message' => 'ไม่พบข้อมูลเครื่องจักร'
                ], 404);
            }
        } else {
            $this->jsonResponse([
                'status' => 'error',
                'message' => 'ไม่พบผู้ใช้'
            ], 404);
        }
    }

    public function addMachine()
    {
        $data = $this->getJsonInput();
        $this->checkEmpty($data, ['name', 'location', 'op_id']);
        
        $machine = $this->machine->Create($data);
        if ($machine) {
            $this->jsonResponse([
                'status' => 'success',
                'message' => 'เพิ่มข้อมูลสำเร็จ'
            ], 200);
        } else {
            $this->jsonResponse([
                'status' => 'error',
                'message' => 'เกิดข้อผิดพลาดในการเพิ่มข้อมูล'
            ], 500);
        }
    }

    public function updateMachine($id)
    {
        $data = $this->getJsonInput();
        $updated = $this->machine->Update($id, $data);
        if ($updated) {
            $this->jsonResponse(['status' => 'success', 'message' => 'อัปเดตข้อมูลตู้สำเร็จ'], 200);
        }
        $this->jsonResponse(['status' => 'error', 'message' => 'ไม่สามารถอัปเดตข้อมูลได้'], 500);
    }

    public function clearMachineCount($id)
    {
        $updated = $this->machine->Update($id, ['count' => 0]);
        if ($updated) {
            $this->jsonResponse(['status' => 'success', 'message' => 'รีเซ็ตจำนวนขวดในตู้เรียบร้อยแล้ว'], 200);
        }
        $this->jsonResponse(['status' => 'error', 'message' => 'เกิดข้อผิดพลาดในการรีเซ็ตจำนวนขวด'], 500);
    }

    public function deleteMachine($id)
    {
        $deleted = $this->machine->Delete($id);
        if ($deleted) {
            $this->jsonResponse(['status' => 'success', 'message' => 'ลบตู้สำเร็จ'], 200);
        }
        $this->jsonResponse(['status' => 'error', 'message' => 'ไม่สามารถลบตู้ได้'], 500);
    }

    // ดึงประวัติการหยอดขวด (Logs) ทั้งหมดของตู้ที่ระบุ
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
}