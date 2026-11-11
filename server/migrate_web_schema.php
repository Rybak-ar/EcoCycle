<?php

require_once __DIR__ . '/vendor/autoload.php';

// โหลด .env
if (file_exists(__DIR__ . '/.env')) {
    $lines = file(__DIR__ . '/.env', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        if (strpos(trim($line), '#') === 0) continue;
        list($name, $value) = explode('=', $line, 2);
        $_ENV[trim($name)] = trim($value);
    }
}

$dbConfig = new \Config\Database();
$db = $dbConfig->connect();

echo "Connected to database successfully.\n";
echo "Starting Schema migration to match Web specifications...\n";

$schema = new \App\Database\Schema($db);
$schema->createTables();

echo "\nMigration finished successfully!\n";
