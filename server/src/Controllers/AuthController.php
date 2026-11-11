<?php
namespace App\Controllers;

use App\Controllers\BaseController;
use App\Models\user\User;


class AuthController extends BaseController
{

    private $secret_key;


    public function __construct()
    {
        $this->secret_key = $_ENV['JWT_SECRET'];
    }

    public function login()
    {
        $data = $this->getJsonInput();
        
        $identifier = $data['identifier'] ?? $data['email'] ?? null;
        $password = $data['password'] ?? null;

        if (!$identifier || !$password) {
            $this->jsonResponse(['status' => 'error', 'message' => 'กรุณากรอกข้อมูลให้ครบถ้วน'], 400);
            return;
        }

        $user_model = new User();
        $user = $user_model->getByIdentifier($identifier);

        if ($user && password_verify($data['password'], $user['password'])) {

            if ($user['permission'] == 0) {
                $this->jsonResponse([
                    "status" => "error",
                    "message" => "บัญชีถูกปิดใช้งาน"
                ], 403);
                return;
            }

            $payload = [
                "user_id" => $user['id'] ?? null,
                "exp" => time() + (84600 * 30),
            ];

            $header = json_encode(['typ' => 'JWT', 'alg' => 'HS256']);
            $payloadEncoded = json_encode($payload);

            $base64UrlHeader = str_replace(['+', '/', '='], ['-', '_', ''], base64_encode($header));
            $base64UrlPayload = str_replace(['+', '/', '='], ['-', '_', ''], base64_encode($payloadEncoded));

            $signature = hash_hmac('sha256', $base64UrlHeader . "." . $base64UrlPayload, $this->secret_key, true);
            $base64UrlSignature = str_replace(['+', '/', '='], ['-', '_', ''], base64_encode($signature));

            $jwt = $base64UrlHeader . "." . $base64UrlPayload . "." . $base64UrlSignature;



            setcookie(
                "token",
                $jwt,
                time() + (84600 * 30), // 30 days
                "/",
                "",
                false,
                true
            );

            $this->jsonResponse([
                "status" => "success",
                "message" => "เข้าสู่ระบบสำเร็จ",
                "token" => $jwt,
                "user" => [
                    "op_name" => $user['op_name'],
                    "role" => $user['role'] ?? 'user',
                    "email" => $user['email']
                ]
            ]);
        } else {
            $this->jsonResponse([
                "status" => "error",
                "message" => "เบอร์หรือรหัสผ่านไม่ถูกต้อง"
            ], 401);
        }
    }
   
    public function logout(){
        
        setcookie('token','',time()-3600,'/','',false,true);
        $this->jsonResponse([
            'status' => 'success',
            'message' => 'ออกจากระบบสำเร็จ'
        ],200);
    }


    public function register(){
        $data = $this->getJsonInput();
        $this->checkEmpty($data);
        $data['password'] = password_hash($data['password'],PASSWORD_BCRYPT);
        $data['permission'] = 1;
        $data['role'] = 'operator';
        $user = new User();
        $usercreate = $user->Create($data);
        if($usercreate){
            $this->jsonResponse([
            'status' => 'success',
            'message' => 'สมัครสมาชิกสำเร็จ'
        ],200);
        }else{
            $this->jsonResponse([
                'status' => 'error',
                'message' => 'เกิดข้อผิดพลาดในการสมัครสมาชิก'
            ],500);
            return;
        }
        
    }

}


?>