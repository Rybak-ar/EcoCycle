<?php

namespace App\Models\machine;

use App\Models\Basemodel;

class machine extends Basemodel
{
    protected $table = 'tb_machine';
    protected $primarykey = 'id';

    public function getMachineByuserID($id): array
    {
        $sql = "SELECT * FROM {$this->table} WHERE op_id = :op_id";
        $stmt = $this->db->prepare($sql);
        $stmt->execute([':op_id' => $id]);
        return $stmt->fetchAll();
    }

    public function getDetailMachine($id)
    {
        $sql = "SELECT 
                    m.*, 
                    c.type AS config_type, 
                    c.allow AS config_allow,
                    p.id AS rate_id,
                    p.key AS rate_key,
                    p.value AS rate_value
                FROM {$this->table} m
                LEFT JOIN tb_config c ON m.id = c.machine_id
                LEFT JOIN tb_pointrate p ON m.id = p.machine_id
                WHERE m.id = :id";

        $stmt = $this->db->prepare($sql);
        $stmt->execute([':id' => $id]);
        return $stmt->fetchAll(\PDO::FETCH_ASSOC);
    }
}