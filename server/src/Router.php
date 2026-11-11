<?php

namespace App;


class Router
{
    private $routes = [];


    public function add($method, $route, $controller, $action)
    {

        $this->routes[] = [
            'method' => strtoupper($method),
            'route' => $route,
            'controller' => $controller,
            'action' => $action
        ];
    }

    public function get($route, $controller, $action)
    {
        $this->add('GET', $route, $controller, $action);
    }
    public function post($route, $controller, $action)
    {
        $this->add('POST', $route, $controller, $action);
    }
    public function PUT($route, $controller, $action)
    {
        $this->add('PUT', $route, $controller, $action);
    }
    public function DELETE($route, $controller, $action)
    {
        $this->add('DELETE', $route, $controller, $action);
    }

    // logic เรียกใช้งาน api 

    public function dispatch($requestMethod, $requestUrl)
    {


        if ($requestMethod === 'POST') {
            if (isset($_SERVER['HTTP_X_HTTP_METHOD_OVERRIDE'])) {
                $requestMethod = strtoupper($_SERVER['HTTP_X_HTTP_METHOD_OVERRIDE']);
            } elseif (isset($_GET['_method'])) {
                $requestMethod = strtoupper($_GET['_method']);
            } elseif (isset($_POST['_method'])) {
                $requestMethod = strtoupper($_POST['_method']);
            } else {
                $rawBody = file_get_contents('php://input');
                if (!empty($rawBody)) {
                    $jsonBody = json_decode($rawBody, true);
                    if (is_array($jsonBody) && isset($jsonBody['_method'])) {
                        $requestMethod = strtoupper($jsonBody['_method']);
                    }
                }
            }
        }


        $requestMethod = strtoupper($requestMethod);


        $requestUrl = '/' . trim($requestUrl, '/');


        $public_routes = [
            '/api/login',
            '/api/logout',
            '/api/register',
            '/api/central/prices',
            '/api/user/machines/{m_id}/login',
            '/api/user/machines/{m_id}/register',
            '/api/user/machines/{m_id}/status',
            '/api/user/machines/{machine_id}/login',
            '/api/user/machines/{machine_id}/register',
            '/api/user/machines/{machine_id}/status',
            '/api/operator/machines/{id}/config',
            '/api/operator/machines/{machine_id}/config',
            '/api/machine/{id}/config',
            '/api/machine/{machine_id}/config',
            '/api/machines/{m_id}/products',
            '/api/machines/{machine_id}/products'
        ];

        $isPublic = false;
        foreach ($public_routes as $pr) {
            $pattern = preg_replace('/\{([a-zA-Z0-9_]+)\}/', '([a-zA-Z0-9_\-]+)', $pr);
            $pattern = "@^" . $pattern . "$@D";
            if (preg_match($pattern, $requestUrl)) {
                $isPublic = true;
                break;
            }
        }

        if (strpos($requestUrl, '/api/') === 0 && !$isPublic) {
            $auth = new \App\Middleware\AuthMiddleware();
            $auth->checkToken();
        }


        foreach ($this->routes as $route) {
            if ($route['method'] === $requestMethod) {

                $pattern = preg_replace('/\{([a-zA-Z0-9_]+)\}/', '([a-zA-Z0-9_\-]+)', $route['route']);
                $pattern = "@^" . $pattern . "$@D";
                if (preg_match($pattern, $requestUrl, $matches)) {
                    array_shift($matches); //เอาค่าตัวแรกออก

                    // สร้าง controller 

                    $controllerName = "App\\Controllers\\" . $route['controller'];
                    if (class_exists($controllerName)) {
                        $controller = new $controllerName();
                        $action = $route['action'];

                        if (method_exists($controller, $action)) {

                            call_user_func_array([$controller, $action], $matches);
                            return;
                        }
                    }
                }

            }
        }

        // กรณีไม่เจอ Route
        http_response_code(404);
        echo json_encode(['status' => 'error', 'message' => "API NOT FOUND (404)", "requestUrl" => $requestUrl, "method" => $requestMethod]);
    }
}

?>