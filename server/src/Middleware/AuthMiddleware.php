<?php

namespace App\Middleware;


class AuthMiddleware
{

    private $secret_key;

    public function __construct()
    {
        $this->secret_key = $_ENV['JWT_SECRET'];
    }

    public function checkToken($exitOnError = true)
    {

        $token = null;

        if (!empty($_COOKIE['token'])) {
            $token = trim($_COOKIE['token']);
        }


        if (empty($token)) {
            $headers = null;
            if (isset($_SERVER['Authorization'])) {
                $headers = trim($_SERVER['Authorization']);
            } elseif (isset($_SERVER['HTTP_AUTHORIZATION'])) {
                $headers = trim($_SERVER['HTTP_AUTHORIZATION']);
            } elseif (function_exists('apache_request_headers')) {
                $requestHeaders = apache_request_headers();
                $requestHeaders = array_combine(
                    array_map('ucwords', array_keys($requestHeaders)),
                    array_values($requestHeaders)
                );
                if (isset($requestHeaders['Authorization'])) {
                    $headers = trim($requestHeaders['Authorization']);
                }
            }

            if (!empty($headers)) {
                $token = trim(str_replace('Bearer', '', $headers));
            }


            if (empty($token)) {
                if ($exitOnError) {
                    http_response_code(401);
                    echo json_encode(["status" => "error", "message" => "Unauthorized"]);
                    exit();
                }

                return null;
            }

            $token = trim($token);


            $tokenParts = explode('.', $token);

            if (count($tokenParts) != 3) {
                if ($exitOnError) {
                    http_response_code(401);
                    echo json_encode(["status" => "error", "message" => "Unauthorized"]);
                    exit();
                }
                return null;
            }

            $signature = hash_hmac('sha256', $tokenParts[0] . "." . $tokenParts[1], $this->secret_key, true);

            $base64UrlSignature = str_replace(['+', '/', '='], ['-', '_', ''], base64_encode($signature));

            if ($base64UrlSignature !== $tokenParts[2]) {
                if ($exitOnError) {
                    http_response_code(401);
                    echo json_encode(["status" => "error", "message" => "Unauthorized"]);
                    exit();
                }
                return null;
            }

            //  ดึงข้อมูล payload

            $payloadRaw = str_replace(['-', '_'], ['+', '/'], $tokenParts[1]);
            $payload = json_decode(base64_decode($payloadRaw), true);

            if (isset($payload['exp']) && $payload['exp'] < time()) {
                if ($exitOnError) {
                    http_response_code(401);
                    echo json_encode(["status" => "error", "message" => "Unauthorized"]);
                    exit();
                }
                return null;
            }



            return $payload;
        }
    }
}
