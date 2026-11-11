<?php

namespace App\Models\machine;
use App\Models\Basemodel;

class Config extends Basemodel{
    protected $table = 'tb_config';
    protected $primarykey = 'id';

    public function getByMachineId($machine_id){
        $sql = "SELECT * FROM {$this->table} WHERE machine_id = :machine_id";
        $stmt = $this->db->prepare($sql);
        $stmt->bindParam(":machine_id", $machine_id);
        $stmt->execute();
        return $stmt->fetch(\PDO::FETCH_ASSOC);
    }
}
