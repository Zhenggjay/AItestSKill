import urllib.request
import urllib.parse
import json
import time
import re
import socket

class HTTPExecutor:
    def __init__(self, base_url=None, default_token=None):
        # 去除末尾斜杠
        self.base_url = base_url.rstrip('/') if base_url else ""
        self.default_token = default_token
        # 上下文变量仓，用于存储提取的 sessionId, executeId 等
        self.context = {}
        if default_token:
            self.context["homingtoken"] = default_token
            self.context["token"] = default_token

    def reset_context(self):
        """重置上下文"""
        self.context = {}
        if self.default_token:
            self.context["homingtoken"] = self.default_token
            self.context["token"] = self.default_token

    def _resolve_placeholders(self, target):
        """递归解析字符串、列表或字典中的 {variable} 占位符"""
        if isinstance(target, str):
            # 查找所有占位符
            placeholders = re.findall(r'\{([a-zA-Z0-9_\-\.]+)\}', target)
            for p in placeholders:
                # 在上下文或环境变量中查找
                val = self.context.get(p)
                if val is not None:
                    # 如果占位符占据了整个字符串且值是数字/布尔，直接返回原类型
                    if target == f"{{{p}}}":
                        return val
                    target = target.replace(f"{{{p}}}", str(val))
            return target
        elif isinstance(target, dict):
            return {k: self._resolve_placeholders(v) for k, v in target.items()}
        elif isinstance(target, list):
            return [self._resolve_placeholders(item) for item in target]
        return target

    def _extract_variables(self, data):
        """递归扫描响应 JSON，自动捕获变量"""
        if not isinstance(data, (dict, list)):
            return

        # 待提取的常见主键名列表
        target_keys = {
            "sessionId", "session_id",
            "executeId", "execute_id", "executeId ", # 兼容 typo 带空格的 key
            "threadId", "thread_id",
            "workspaceId", "workspace_id", "workspaceCode",
            "projectId", "project_id",
            "agentId", "agent_id",
            "token", "homingtoken"
        }

        if isinstance(data, dict):
            for k, v in data.items():
                # 去除键尾空格，如 "executeId " -> "executeId"
                k_clean = k.strip()
                if k_clean in target_keys and v is not None:
                    self.context[k_clean] = v
                    # 同时映射下划线到驼峰，方便互换占位符
                    if "_" in k_clean:
                        camel = ''.join(x.capitalize() or '_' for x in k_clean.split('_'))
                        camel = camel[0].lower() + camel[1:]
                        self.context[camel] = v
                # 递归子对象
                self._extract_variables(v)
        elif isinstance(data, list):
            for item in data:
                self._extract_variables(item)

    def _get_nested_value(self, obj, path):
        """支持点路径表达式（如 data.sessionId）安全获取嵌套对象值"""
        parts = path.split('.')
        current = obj
        for p in parts:
            if isinstance(current, dict):
                current = current.get(p)
            elif isinstance(current, list):
                # 尝试做数组索引解析，如 data.data.0.sessionId
                try:
                    current = current[int(p)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    def run_case(self, case, log_callback=None):
        """运行单个测试用例，并完成参数替换、网络发送、断言校验与变量提取"""
        case_id = case["case_id"]
        api_name = case["api_name"]
        method = case["method"].upper()
        
        # 1. 替换请求路径、Headers 和 Body 中的占位符
        resolved_path = self._resolve_placeholders(case["api_path"])
        # 补全相对路径
        if not resolved_path.startswith('/'):
            resolved_path = '/' + resolved_path
            
        full_url = self.base_url + resolved_path
        
        resolved_headers = self._resolve_placeholders(case["request_headers"] or {})
        # 注入鉴权 token
        if "homingtoken" not in resolved_headers and "homingtoken" in self.context:
            resolved_headers["homingtoken"] = str(self.context["homingtoken"])
        if "Authorization" not in resolved_headers and "token" in self.context:
            resolved_headers["Authorization"] = f"Bearer {self.context['token']}"
            
        resolved_body = self._resolve_placeholders(case["request_body"])

        if log_callback:
            log_callback(f"[INFO] Running {case_id} [{api_name}]: {method} {resolved_path}")

        # 2. 准备网络请求
        req_data = None
        if method in ["POST", "PUT", "DELETE", "PATCH"] and resolved_body is not None:
            # 针对 GET/DELETE，如果参数是 Query，我们在 URL 处理中合并；若 POST，编码为 JSON
            if resolved_headers.get("Content-Type") == "x-www-form-urlencoded" or resolved_headers.get("Content-Type") == "application/x-www-form-urlencoded":
                req_data = urllib.parse.urlencode(resolved_body).encode('utf-8')
            else:
                # 默认 JSON
                req_data = json.dumps(resolved_body).encode('utf-8')
                resolved_headers["Content-Type"] = "application/json"
        elif method == "GET" and resolved_body:
            # GET 参数拼接到 URL
            query_str = urllib.parse.urlencode(resolved_body)
            full_url = f"{full_url}?{query_str}" if '?' not in full_url else f"{full_url}&{query_str}"

        req = urllib.request.Request(full_url, data=req_data, headers=resolved_headers, method=method)
        
        start_time = time.time()
        status_code = None
        res_body = ""
        res_headers = {}
        error_msg = None
        status = "SUCCESS"

        # 3. 发送 HTTP 请求 (设置较短的超时时间，SSE 接口在 Header 返回后立即关闭)
        try:
            # SSE 接口或者流接口：
            is_stream_test = "stream" in resolved_path or resolved_headers.get("Content-Type") == "text/event-stream"
            timeout = 15.0 if not is_stream_test else 5.0
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.status
                res_headers = dict(response.info())
                
                # Option A: 如果是流式响应，我们只需验证头部，防止阻塞
                content_type = res_headers.get("Content-Type", "")
                if "text/event-stream" in content_type:
                    res_body = "STREAMING_CONNECTION_ESTABLISHED_SUCCESS"
                    if log_callback:
                        log_callback(f"[SUCCESS] {case_id} SSE Stream Connected: text/event-stream detected.")
                else:
                    res_body = response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            status_code = e.code
            res_headers = dict(e.info())
            try:
                res_body = e.read().decode('utf-8')
            except Exception:
                res_body = ""
        except socket.timeout:
            status = "ERROR"
            error_msg = "Connection Timeout"
        except Exception as e:
            status = "ERROR"
            error_msg = str(e)

        elapsed = (time.time() - start_time) * 1000.0 # 毫秒

        # 4. 执行结果断言与解析
        res_json = None
        if status == "SUCCESS":
            # 尝试解析 JSON
            try:
                res_json = json.loads(res_body)
            except Exception:
                pass
                
            # 自动提取响应中的 session 变量
            if res_json:
                self._extract_variables(res_json)
                
            # 校验断言
            expected = case.get("expected", {})
            exp_code = expected.get("status_code", 200)
            
            if status_code != exp_code:
                status = "FAIL"
                error_msg = f"HTTP Status Assert Failed: Expected {exp_code}, Got {status_code}"
            else:
                # 校验 JSON 字段级断言
                for ast_rule in expected.get("assertions", []):
                    ast_type = ast_rule.get("type")
                    if ast_type == "json_field":
                        field_path = ast_rule.get("field")
                        op = ast_rule.get("op")
                        expected_val = ast_rule.get("value")
                        
                        actual_val = self._get_nested_value(res_json, field_path) if res_json else None
                        
                        # 兼容布尔、数字的比照
                        if op == "eq":
                            if actual_val != expected_val:
                                status = "FAIL"
                                error_msg = f"Assert Failed: '{field_path}' expected '{expected_val}', got '{actual_val}'"
                                break
                        elif op == "in":
                            if actual_val not in expected_val:
                                status = "FAIL"
                                error_msg = f"Assert Failed: '{field_path}' value '{actual_val}' not in list {expected_val}"
                                break
        
        if log_callback:
            if status == "SUCCESS":
                log_callback(f"[SUCCESS] {case_id} Passed ({elapsed:.1f}ms). Code: {status_code}")
            elif status == "FAIL":
                log_callback(f"[FAIL] {case_id} Failed: {error_msg}")
            else:
                log_callback(f"[ERROR] {case_id} Error: {error_msg}")

        return {
            "case_id": case_id,
            "api_name": api_name,
            "api_path": resolved_path,
            "method": method,
            "case_type": case.get("case_type"),
            "status": status,
            "response_code": status_code,
            "response_time": elapsed,
            "error_message": error_msg,
            "request_headers": resolved_headers,
            "request_body": resolved_body,
            "response_headers": res_headers,
            "response_body": res_body if not res_json else res_json
        }
