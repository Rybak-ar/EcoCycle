<?php

use Dotenv\Dotenv;

require_once __DIR__ . '/vendor/autoload.php';

$dotenv = Dotenv::createImmutable(__DIR__ . '/');
$dotenv->load();


date_default_timezone_set('Asia/Bangkok');

$envOrigins = $_ENV['ALLOWED_ORIGIN'] ?? $_ENV['ALLOW_ORIGIN'] ?? $_ENV['ALLOW_ORIGNIN'] ?? '*';

$allowedOrigins = array_map(function($o) {
    return rtrim(trim($o), '/');
}, explode(',', $envOrigins));

$origin = isset($_SERVER['HTTP_ORIGIN']) ? rtrim(trim($_SERVER['HTTP_ORIGIN']), '/') : '';

if (!empty($origin) && (in_array('*', $allowedOrigins) || in_array($origin, $allowedOrigins))) {
    header("Access-Control-Allow-Origin: " . $origin);
} elseif (!empty($origin)) {
    header("Access-Control-Allow-Origin: " . $origin);
} else {
    header("Access-Control-Allow-Origin: " . (isset($allowedOrigins[0]) ? $allowedOrigins[0] : '*'));
}

header("Access-Control-Allow-Credentials: true");
header("Access-Control-Allow-Headers: Content-Type, Authorization");
header("Content-Type: application/json; charset=UTF-8");
header("Access-Control-Allow-Methods: DELETE, GET, POST, PUT, OPTIONS");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}


// class src auto loading

spl_autoload_register(function ($class) {
    $base_dir = __DIR__ . '/';

    $class = str_replace('App\\', 'src/', $class);
    $class = str_replace('Config\\', 'config/', $class);
    $file = $base_dir . str_replace('\\', '/', $class) . '.php';

    if (file_exists($file)) {
        require $file;
    }
});


//  เรียกใช้งาน api

$router = new \App\Router();

require_once __DIR__ . '/src/Routes/api.php';


$url = isset($_GET['url']) ? rtrim($_GET['url'], '/') : '';
$method = $_SERVER['REQUEST_METHOD'];

$router->dispatch($method, $url);
?>