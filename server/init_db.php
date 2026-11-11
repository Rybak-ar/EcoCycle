<?php

use Dotenv\Dotenv;
use Config\Database;
use App\Database\Schema;

require_once __DIR__ . '/vendor/autoload.php';

// Load .env
$dotenv = Dotenv::createImmutable(__DIR__ . '/');
$dotenv->load();

// Autoloader (Manual for this script since index.php logic is slightly specific)
spl_autoload_register(function($class){
    $base_dir = __DIR__ . '/';
    $classPath = str_replace(['App\\', 'Config\\', '\\'], ['src/', 'config/', '/'], $class);
    $file = $base_dir . $classPath . '.php';
    if(file_exists($file)){
        require $file;
    }
});

echo "Initializing Database...\n";

$dbConfig = new Database();
$db = $dbConfig->connect();

$schema = new Schema($db);


$schema->createTables();

echo "Database initialization completed.\n";
