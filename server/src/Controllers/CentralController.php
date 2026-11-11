<?php

namespace App\Controllers;

class CentralController extends BaseController
{
    public function getPrices()
    {
        // ราคากลาง (Base Prices) สำหรับการแลกเปลี่ยนเป็นเงินสด
        $this->jsonResponse([
            'status' => 'success',
            'data' => [
                'clear' => 20.0,
                'opaque' => 15.0,
                'brown' => 10.0
            ]
        ], 200);
    }
}
