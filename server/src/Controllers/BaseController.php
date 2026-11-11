<?php

namespace App\Controllers;

class BaseController
{
    /**
     * ดึงข้อมูลเข้า (JSON หรือ POST) โดยไม่ Exit ทันทีหากไม่พบ
     */
    protected function getInputData()
    {
        if (!empty($_POST)) return $_POST;
        $json = file_get_contents("php://input");
        if (!empty($json)) {
            $decoded = json_decode($json, true);
            if (is_array($decoded)) return $decoded;
        }
        return [];
    }

    protected function getJsonInput()
    {
        $data = $this->getInputData();
        if (empty($data)) {
            $this->jsonResponse(['status' => 'error', 'message' => 'กรุณาส่งข้อมูลให้ครบถ้วน'], 400);
        }
        return $data;
    }

    /**
     * ส่งข้อมูลกลับไปเป็น JSON พร้อมกำหนด HTTP Status Code
     * 
     * @param array $data ข้อมูลที่จะส่งกลับ
     * @param int $statusCode HTTP Status Code (ค่าเริ่มต้น 200)
     */
    protected function jsonResponse($data, $statusCode = 200)
    {
        http_response_code($statusCode);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode($data);
        exit();
    }


     protected function checkEmpty($data, $required = [])
    {
        if (empty($data)) {
            $this->jsonResponse(['status' => 'error', "message" => "กรุณากรอกข้อมูลให้ครบถ้วน"]);
            return;
        }

        $fieldsToCheck = !empty($required) ? $required : array_keys($data);

        foreach ($fieldsToCheck as $field) {
            if (!isset($data[$field]) || is_null($data[$field]) || $data[$field] === '') {
                $this->jsonResponse(['status' => 'error', "message" => "กรุณากรอกข้อมูลให้ครบถ้วน: $field"]);
                return;
            }
        }
    }
}
