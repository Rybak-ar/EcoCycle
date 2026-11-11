<?php

namespace App\Models\user;
use App\Models\Basemodel;


class User extends Basemodel{
    protected $table = 'tb_user';
    protected $primarykey = 'id';


    public function getByEmail($email){
        $sql =  "SELECT id, email, password, permission, op_name, role FROM {$this->table} WHERE email = :email";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(":email",$email);
        $stmt->execute();
        return $stmt->fetch();
    }

    public function getByIdentifier($identifier){
        $sql =  "SELECT id, email, phonenumber, password, permission, op_name, role FROM {$this->table} WHERE email = :identifier OR phonenumber = :identifier";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(":identifier",$identifier);
        $stmt->execute();
        return $stmt->fetch();
    }
}


?>