<?php

namespace App\Models;

use Config\Database;
use Exception;




class Basemodel
{


    protected $db;
    protected $table;
    protected $primarykey;

    protected $searchColumns = [];
    public function __construct()
    {
        $db = new Database();
        $this->db = $db->connect();
    }

    // ลบข้อมูล
    public function Delete($id)
    {
        $sql = "DELETE FROM " . $this->table . " WHERE " . $this->primarykey . " = :id";
        $stmt = $this->db->prepare($sql);
        $stmt->execute([':id' => $id]);

        return $stmt->rowCount();
    }


    public function Update($id, $data)
    {
        $sql = "UPDATE " . $this->table . " SET ";
        $sql .= implode(",", array_map(function ($k) { return "`$k` = :$k"; }, array_keys($data)));
        $sql .= " WHERE `" . $this->primarykey . "` = :id";
        $stmt = $this->db->prepare($sql);
        $data['id'] = $id;
        $stmt->execute($data);

        return $stmt->rowCount();
    }


    public function Create($data)
    {
        $sql = "INSERT INTO " . $this->table . " SET ";
        $sql .= implode(",", array_map(function ($k) { return "`$k` = :$k"; }, array_keys($data)));
        $stmt = $this->db->prepare($sql);
        $stmt->execute($data);
        return $stmt->rowCount();
    }

    /**
     * @return array
     */
    public function serachPaginate(string $search = '', int $limit = 10, int $offset = 0): array
    {
        $conditions = [];
        $params = [];
        $colInfo = $this->db
            ->query("SHOW COLUMNS FROM {$this->table}")
            ->fetchAll(\PDO::FETCH_ASSOC);

        $colNames = array_column($colInfo, 'Field');

        // ---- ค้นหาข้อมูล----
        if ($search !== '') {
            if (!empty($this->searchColumns)) {
                $searchCol = $this->searchColumns;
            } else {
                $textTypes = ['varchar', 'text', 'mediumtext', 'longtext', 'char', 'enum'];

                $searchCols = [];
                foreach ($colInfo as $col) {
                    $baseType = strtolower(preg_replace('/\(.*\)/', '', $col['Type']));
                    if (in_array($baseType, $textTypes)) {
                        $searchCols[] = $col['Field'];
                    }
                }
            }

            if (!empty($searchCols)) {
                $likes = array_map(function ($col) { return "{$col} LIKE :search"; }, $searchCols);
                $conditions[] = "(" . implode(" OR ", $likes) . ")";
                $params['search'] = "%{$search}%";
            }
        }

        $where = !empty($conditions) ? 'WHERE' . implode('AND', $conditions) : '';

        // ---count total----
        $countStmt = $this->db->prepare("SELECT COUNT(*) as total FROM{$this->table}{$where}");
        $countStmt->execute($params);
        $total = (int) $countStmt->fetch()["total"];


        // ดึงข้อมูล

        $dataSql = "SELECT * FROM {$this->table}{$where} ORDER BY {$this->primarykey} DESC LIMIT :limit OFFSET :offset";
        $dataStmt = $this->db->prepare($dataSql);


        foreach ($params as $key => $value) {
            $dataStmt->bindValue($key, $value, \PDO::PARAM_STR);
        }
        $dataStmt->bindValue(':limit', $limit, \PDO::PARAM_INT);
        $dataStmt->bindValue(':offset', $offset, \PDO::PARAM_INT);
        $dataStmt->execute();

        return [$dataStmt->fetchAll(\PDO::FETCH_ASSOC), $total];

    }

    public function findById(int $id)
    {
        $stmt = $this->db->prepare("SELECT * FROM {$this->table} WHERE {$this->primarykey} = :id");
        $stmt->execute([':id' => $id]);
        return $stmt->fetch(\PDO::FETCH_ASSOC) ?: null;
    }

    public function getAll()
    {
        $sql = "SELECT * FROM " . $this->table;
        $stmt = $this->db->prepare($sql);
        $stmt->execute();
        return $stmt->fetchAll();
    }
}


?>