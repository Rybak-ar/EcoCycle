<?php
    
namespace Config;


class Database {

    private $host;
    private $user;
    private $password;
    private $dbname;


    // ป้องกันการเรียกใช้งานซ้ำๆ
    protected static $conn = null;



    public function __construct()
    {
        $this->host = $_ENV['host'] ?? $_ENV['DB_HOST'] ?? 'localhost';
        $this->user = $_ENV['user'] ?? $_ENV['DB_USER'] ?? 'root';
        $this->password = $_ENV['password'] ?? $_ENV['DB_PASS'] ?? $_ENV['DB_PASSWORD'] ?? '';
        $this->dbname = $_ENV['dbname'] ?? $_ENV['DB_NAME'] ?? 'ecocycle_db';
        $this->port = $_ENV['port'] ?? $_ENV['DB_PORT'] ?? '3306';
    }


    public function connect(){
        if(self::$conn !== null){
            return self::$conn;
        }

        $dns = "mysql:host=".$this->host.";port=".$this->port.";dbname=".$this->dbname. ";charset=utf8mb4";


        try{
            self::$conn = new \PDO($dns,$this->user,$this->password);
            self::$conn->setAttribute(\PDO::ATTR_ERRMODE,\PDO::ERRMODE_EXCEPTION);
            self::$conn->setAttribute(\PDO::ATTR_DEFAULT_FETCH_MODE,\PDO::FETCH_ASSOC);
            self::$conn->exec("SET time_zone ='+07:00'");
        }catch(\PDOException  $e){
            die("Connection failed:" . $e->getMessage());
        }
        return self::$conn;
    }

    public function getMessage($content,$status){
        return json_encode(['message'=>$content,'error'=>$status]);
    }


}



?>