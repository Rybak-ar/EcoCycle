<?php

global $router;

// ==========================================
// 1. Auth API
// ==========================================
$router->post('/api/login', 'AuthController', 'login');
$router->post('/api/logout', 'AuthController', 'logout');
$router->post('/api/register', 'AuthController', 'register');

// ==========================================
// 2. Central API (Kiosk)
// ==========================================
$router->get('/api/central/prices', 'CentralController', 'getPrices');

// ==========================================
// 3. Machine API
// ==========================================
$router->get('/api/machine/{id}', 'MachineController', 'getMachineByUser');
$router->post('/api/machine', 'MachineController', 'addMachine');
$router->put('/api/machine/{id}', 'MachineController', 'updateMachine');
$router->put('/api/machine/{id}/clear-count', 'MachineController', 'clearMachineCount');
$router->delete('/api/machine/{id}', 'MachineController', 'deleteMachine');
$router->get('/api/machine/{id}/logs', 'MachineController', 'getMachineLogs');

// ==========================================
// 4. Admin API
// ==========================================
$router->get('/api/admin/machines', 'AdminController', 'getMachines');
$router->put('/api/admin/users/{id}/status', 'AdminController', 'updateUserStatus');
$router->put('/api/admin/machines/{id}/status', 'AdminController', 'updateMachineStatus');
$router->put('/api/admin/machines/{id}/approve', 'AdminController', 'approveMachine');
$router->get('/api/admin/dashboard', 'AdminController', 'getDashboardStats');
$router->get('/api/admin/operators', 'AdminController', 'getOperators');
$router->get('/api/admin/issues', 'AdminController', 'getIssueReports');
$router->put('/api/admin/issues/{id}', 'AdminController', 'updateIssueReport');

// ==========================================
// 5. Operator API
// ==========================================
$router->put('/api/operator/machines/{id}/config', 'OperatorController', 'updateMachineConfig');
$router->post('/api/operator/machines/{id}/config', 'OperatorController', 'updateMachineConfig');
$router->get('/api/operator/machines/{id}/config', 'OperatorController', 'getMachineConfig');
$router->put('/api/machine/{id}/config', 'OperatorController', 'updateMachineConfig');
$router->post('/api/machine/{id}/config', 'OperatorController', 'updateMachineConfig');
$router->get('/api/machine/{id}/config', 'OperatorController', 'getMachineConfig');
$router->get('/api/operator/machines/{id}/users', 'OperatorController', 'getMachineUsers');
$router->get('/api/operator/machines/{id}/logs', 'MachineController', 'getMachineLogs');
// $router->get('/api/operator/machines/{id}/redeem-requests', 'OperatorController', 'getRedeemRequests');
// $router->put('/api/operator/redeem-requests/{id}/approve', 'OperatorController', 'approveRedeem');
// $router->put('/api/operator/redeem-requests/{id}/reject', 'OperatorController', 'rejectRedeem');
$router->get('/api/operator/issues', 'OperatorController', 'getIssueReports');
$router->post('/api/operator/issues', 'OperatorController', 'createIssueReport');
$router->put('/api/operator/issues/{id}', 'OperatorController', 'updateIssueReport');
$router->put('/api/operator/machines/{id}/pairing-code', 'OperatorController', 'generatePairingCode');
$router->put('/api/operator/machines/{id}/serial-number', 'OperatorController', 'updateSerialNumber');

// ==========================================
// 6. User / Member API
// ==========================================
$router->post('/api/user/machines/{m_id}/register', 'UserController', 'register');
$router->post('/api/user/machines/{machine_id}/register', 'UserController', 'register');
$router->post('/api/user/machines/{m_id}/login', 'UserController', 'login');
$router->post('/api/user/machines/{machine_id}/login', 'UserController', 'login');
$router->get('/api/user/machines/{m_id}/status', 'UserController', 'getMachineStatus');
$router->get('/api/user/machines/{machine_id}/status', 'UserController', 'getMachineStatus');
$router->post('/api/user/machines/{m_id}/deposit', 'UserController', 'deposit');
$router->post('/api/user/machines/{machine_id}/deposit', 'UserController', 'deposit');
$router->post('/api/user/machines/{m_id}/batch_deposit', 'UserController', 'batch_deposit');
$router->post('/api/user/machines/{machine_id}/batch_deposit', 'UserController', 'batch_deposit');
$router->post('/api/user/machines/{m_id}/redeem', 'UserController', 'redeem');
$router->post('/api/user/machines/{machine_id}/redeem', 'UserController', 'redeem');
$router->get('/api/user/me', 'UserController', 'getProfile');
$router->put('/api/user/me', 'UserController', 'updateProfile');
$router->get('/api/user/profile/{id}', 'UserController', 'getUserProfileById');
$router->get('/api/user/history', 'UserController', 'getHistory');
$router->post('/api/user/issues', 'UserController', 'createIssueReport');
$router->get('/api/user/issues', 'UserController', 'getUserIssues');

// ==========================================
// 7. Machine Shop & Product Redemption API
// ==========================================
$router->get('/api/shop/machines', 'ShopController', 'getShopMachines');
$router->get('/api/machines/{m_id}/products', 'ShopController', 'getMachineProducts');
$router->get('/api/machines/{machine_id}/products', 'ShopController', 'getMachineProducts');
$router->post('/api/operator/machines/{m_id}/products', 'ShopController', 'addProduct');
$router->post('/api/operator/machines/{machine_id}/products', 'ShopController', 'addProduct');
$router->put('/api/operator/products/{id}', 'ShopController', 'updateProduct');
$router->post('/api/operator/products/{id}', 'ShopController', 'updateProduct');
$router->delete('/api/operator/products/{id}', 'ShopController', 'deleteProduct');
$router->get('/api/operator/machines/{m_id}/shop/stats', 'ShopController', 'getShopStats');
$router->get('/api/operator/machines/{machine_id}/shop/stats', 'ShopController', 'getShopStats');
$router->get('/api/operator/machines/{m_id}/product-redeems', 'ShopController', 'getProductRedeems');
$router->get('/api/operator/machines/{machine_id}/product-redeems', 'ShopController', 'getProductRedeems');
$router->post('/api/operator/machines/{m_id}/verify-code', 'ShopController', 'verifyRedeemCode');
$router->post('/api/operator/machines/{machine_id}/verify-code', 'ShopController', 'verifyRedeemCode');
$router->put('/api/operator/product-redeems/{id}/confirm', 'ShopController', 'confirmProductRedeem');
$router->put('/api/operator/product-redeems/{id}/reject', 'ShopController', 'rejectProductRedeem');
$router->post('/api/shop/link-machine', 'ShopController', 'linkMachine');

// User / Member Shop Endpoints
$router->post('/api/user/machines/{m_id}/redeem-product', 'ShopController', 'redeemProduct');
$router->post('/api/user/machines/{machine_id}/redeem-product', 'ShopController', 'redeemProduct');
$router->get('/api/user/product-redeems', 'ShopController', 'getMemberProductRedeems');

?>