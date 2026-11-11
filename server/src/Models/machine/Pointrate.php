<?php

namespace App\Models\machine;
use App\Models\Basemodel;

class Pointrate extends Basemodel{
    protected $table = 'tb_pointrate';
    protected $primarykey = 'id';

    public function getByMachineId($machine_id){
        $sql = "SELECT * FROM {$this->table} WHERE machine_id = :machine_id";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(":machine_id", $machine_id);
        $stmt->execute();
        return $stmt->fetchAll(\PDO::FETCH_ASSOC);
    }
    
    public function deleteByMachineId($machine_id){
        $sql = "DELETE FROM {$this->table} WHERE machine_id = :machine_id";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(":machine_id", $machine_id);
        $stmt->execute();
        return $stmt->rowCount();
    }
}
