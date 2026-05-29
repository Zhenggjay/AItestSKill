import re
import ast
import json
import os
from urllib.parse import urlparse

class APIList(list):
    def __init__(self, apis, envs=None):
        super().__init__(apis)
        self.envs = envs or []

def extract_environments(overview_text):
    envs = []
    # 匹配各类常见环境标识，支持中文及英文环境名称
    pattern = r'(?:\n|^)([^\n\r\|：:]*?(?:测试|生产|开发|预发|env|environment|url|base_url|地址|域名|test|prod|dev)[^\n\r\|：:]*?)[\s\:\：]*(https?://[a-zA-Z0-9_\-\.\:\/]+)'
    matches = re.findall(pattern, overview_text, re.IGNORECASE)
    seen_urls = set()
    for name, url in matches:
        url_clean = url.strip().rstrip('/')
        if url_clean in seen_urls:
            continue
        seen_urls.add(url_clean)
        
        # 清洗环境名称，去除多余的标点和空格
        name_clean = re.sub(r'[#\*_`\-\s]', '', name).strip()
        if not name_clean:
            name_clean = "默认环境"
        elif not name_clean.endswith("环境") and len(name_clean) <= 4:
            name_clean = name_clean + "环境"
            
        envs.append({
            "name": name_clean,
            "base_url": url_clean
        })
    return envs

def get_path_prefixes(envs):
    prefixes = set()
    for env in envs:
        path = urlparse(env["base_url"]).path.strip('/')
        if path:
            prefixes.add('/' + path)
    return sorted(list(prefixes), key=len, reverse=True)


class RobustJSONParser:
    @staticmethod
    def clean_dirty_json(raw_str):
        """清洗和修复不合规范的 JSON 文本"""
        if not raw_str:
            return None
        
        # 移除 markdown 可能存在的代码块标记
        cleaned = raw_str.strip().strip("`").strip()
        
        # 1. 常见 Typo 修复：数字后面带了孤立的双引号，如 "agentId": 2039"
        cleaned = re.sub(r':\s*(\d+)"\s*([,\}])', r': \1\2', cleaned)
        cleaned = re.sub(r':\s*"(\d+)"\s*([,\}])', r': \1\2', cleaned) # 兼容转换为数字
        
        # 2. 修复单引号为双引号
        if "'" in cleaned and '"' not in cleaned:
            cleaned = cleaned.replace("'", '"')
            
        # 3. 常见 Typo 修复：中文冒号替换为英文冒号
        cleaned = re.sub(r'"\s*：\s*', r'": ', cleaned)
        cleaned = re.sub(r'：', r':', cleaned) # 备用，尽量小心
        
        # 4. 移除 JSON 内部尾部多余逗号，例如 {"a": 1,} -> {"a": 1}
        cleaned = re.sub(r',\s*([\}\]])', r'\1', cleaned)
        
        # 5. 去除换行符和多余空格
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # 6. 使用 ast.literal_eval 备用评估
        try:
            return json.loads(cleaned)
        except Exception:
            try:
                eval_str = cleaned
                eval_str = re.sub(r'\btrue\b', 'True', eval_str)
                eval_str = re.sub(r'\bfalse\b', 'False', eval_str)
                eval_str = re.sub(r'\bnull\b', 'None', eval_str)
                
                parsed_val = ast.literal_eval(eval_str)
                return json.loads(json.dumps(parsed_val))
            except Exception as e:
                return cleaned

    @staticmethod
    def extract_json_from_curl(curl_str):
        """从 curl 命令中提取 JSON 体"""
        data_match = re.search(r'--(?:data|data-raw)\s+([\'"])(.*?)\1', curl_str, re.DOTALL)
        if data_match:
            return RobustJSONParser.clean_dirty_json(data_match.group(2))
        data_match_simple = re.search(r'-d\s+([\'"])(.*?)\1', curl_str, re.DOTALL)
        if data_match_simple:
            return RobustJSONParser.clean_dirty_json(data_match_simple.group(2))
        return None

def parse_markdown_spec(md_path):
    """解析 接口清单.md 文件，提取结构化的 API 规格说明"""
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"Markdown spec file not found at: {md_path}")
        
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 按四级标题分割接口，每个 "#### " 开始是一个接口定义
    sections = re.split(r'\n####\s+', content)
    
    # 提取概述中的环境
    overview = sections[0] if sections else ""
    envs = extract_environments(overview)
    prefixes = get_path_prefixes(envs)
    
    apis = []
    
    # 忽略第一个 #### 之前的概述部分
    for sec in sections[1:]:
        lines = sec.split('\n')
        if not lines:
            continue
            
        # 1. 接口标题
        title_line = ""
        for l in lines:
            if l.strip():
                title_line = l.strip()
                break
        # 清理标题里的 Markdown 井号标记与序号，如 "#### 2.1.1.1 创建会话" -> "创建会话"
        cleaned_title = re.sub(r'^#+\s*', '', title_line).strip()
        api_name = re.sub(r'^[0-9\.\s]+', '', cleaned_title).strip()
        
        sec_text = '\n'.join(lines[1:])
        
        # 2. 请求地址 (Path)
        path = None
        # 常见匹配：**请求地址：**/conversation/create
        # 支持允许包含转义下划线或包含在加粗语法中间的路径 (例如 threads/{thread\_id}/runs)
        path_match = re.search(r'(?:请求地址|接口地址)[\s\*\:\：\`\'"]*([a-zA-Z0-9_\-\/\.\{\}\:\?\&\=\%\~\*\\\\]+)', sec_text)
        if path_match:
            raw_path = path_match.group(1).strip().strip('`').strip("'").strip('"').strip('*').strip()
            path = raw_path.replace("\\", "").replace("*", "")
            # 过滤掉 http(s)://domain 前缀，保留相对路径
            if path.startswith("http"):
                path = re.sub(r'https?://[^/]+', '', path)
            # 动态剥离环境特定的 path 前缀 (如 /agentpaas)
            for prefix in prefixes:
                if path.startswith(prefix):
                    path = path.replace(prefix, "", 1)
                    break
        
        # 3. 请求方式 (Method)
        method = "POST" # 默认 POST
        # 使用更加宽泛的匹配模式，兼容 **请求方式**：get 以及 请求方式：get 等多种排版格式，支持反单引号包裹的请求方式
        method_match = re.search(r'(?:请求方式)[\s\*\:\：\`\'"]*(GET|POST|PUT|DELETE|PATCH|get|post|put|delete|patch)', sec_text)
        if method_match:
            method = method_match.group(1).upper()
            
        # 4. Header 参数表格解析
        headers_spec = []
        header_sec_match = re.search(r'Header\s*参数.*?\n(.*?\n\n|.*?\n$)', sec_text, re.DOTALL | re.IGNORECASE)
        if header_sec_match:
            table_lines = header_sec_match.group(1).strip().split('\n')
            for t_line in table_lines:
                if '|' in t_line and '---' not in t_line and '参数' not in t_line:
                    parts = [p.strip() for p in t_line.split('|')[1:-1]]
                    if parts and parts[0]:
                        headers_spec.append({
                            "name": parts[0],
                            "type": parts[1] if len(parts) > 1 else "string",
                            "required": "Y" in (parts[2] if len(parts) > 2 else ""),
                            "description": parts[3] if len(parts) > 3 else "",
                            "example": parts[4] if len(parts) > 4 else ""
                        })
                        
        # 5. 请求参数表格解析
        params_spec = []
        params_sec_match = re.search(r'请求参数(?!\s*示例)(.*?)(?:\n\s*\*|\n\s*#|\n\s*响应参数|\n\s*响应说明|\n\s*请求示例|$)', sec_text, re.DOTALL)
        if params_sec_match:
            table_lines = params_sec_match.group(1).strip().split('\n')
            for t_line in table_lines:
                if '|' in t_line and '---' not in t_line and '参数' not in t_line and '字段名' not in t_line:
                    parts = [p.strip() for p in t_line.split('|')[1:-1]]
                    if parts and parts[0]:
                        params_spec.append({
                            "name": parts[0].replace('<br />', '').strip(),
                            "type": parts[1] if len(parts) > 1 else "string",
                            "required": any(x in (parts[2] if len(parts) > 2 else "") for x in ["Y", "是", "Y/是", "Y ", "是 "]),
                            "description": parts[3] if len(parts) > 3 else "",
                            "example": parts[4] if len(parts) > 4 else ""
                        })
                        
        # 6. 请求示例解析 (JSON Body 示例)
        req_example = {}
        req_ex_match = re.search(r'(?:请求示例|curl\s+.*?)(.*?)(?:\n\s*\*|\n\s*#|\n\s*响应参数|\n\s*响应示例|$)', sec_text, re.DOTALL)
        if req_ex_match:
            code_blocks = re.findall(r'```(?:json|yaml|plain|plain\s*text|bash|http|)\s*\n(.*?)\n```', req_ex_match.group(0), re.DOTALL)
            if code_blocks:
                first_block = code_blocks[0].strip()
                if first_block.startswith("curl"):
                    req_example = RobustJSONParser.extract_json_from_curl(first_block) or {}
                else:
                    req_example = RobustJSONParser.clean_dirty_json(first_block) or {}
            else:
                json_match = re.search(r'\{[^{}]*\}', req_ex_match.group(0))
                if json_match:
                    req_example = RobustJSONParser.clean_dirty_json(json_match.group(0)) or {}
                    
        # 7. 响应参数及示例解析 (为了解析出 response fields 如 sessionId 自动关联)
        res_example = {}
        res_ex_match = re.search(r'响应示例(.*?)(?:\n\s*\*|\n\s*#|$)', sec_text, re.DOTALL)
        if res_ex_match:
            code_blocks = re.findall(r'```(?:json|yaml|plain|plain\s*text|bash|http|)\s*\n(.*?)\n```', res_ex_match.group(0), re.DOTALL)
            if code_blocks:
                res_example = RobustJSONParser.clean_dirty_json(code_blocks[0].strip()) or {}
                
        # 8. 如果没匹配到 Path，从 curl 请求中解析 Path
        if not path:
            curl_matches = re.findall(r'curl\s+.*?[\'"](https?://[^\'"]+)[\'"]', sec_text)
            if curl_matches:
                url = curl_matches[0]
                url_path = re.sub(r'https?://[^/]+', '', url).split('?')[0]
                # 动态剥离环境特定的 path 前缀 (如 /agentpaas)
                stripped = False
                for prefix in prefixes:
                    if url_path.startswith(prefix):
                        url_path = url_path.replace(prefix, "", 1)
                        stripped = True
                        break
                if not stripped and url_path.startswith("/agentpaas"):
                    url_path = url_path.replace("/agentpaas", "", 1)
                path = url_path

        # 整理输出，如果没有 Path 则不是有效接口
        if path:
            apis.append({
                "api_name": api_name,
                "path": path,
                "method": method,
                "headers": headers_spec,
                "params": params_spec,
                "req_example": req_example,
                "res_example": res_example
            })
            
    # 路径 + 名称 的一个去重再输出
    seen = set()
    deduped_apis = []
    for api in apis:
        key = (api["path"], api["api_name"])
        if key not in seen:
            seen.add(key)
            deduped_apis.append(api)
            
    return APIList(deduped_apis, envs)

def generate_test_cases(apis, project_id=None):
    """根据 API 规格规格，自动生成四类测试用例（排除安全与注入校验）：
    1. Happy Path (正向：包括完整参数、仅必选参数)
    2. Missing / Null Parameter (必填项校验与空值传入校验)
    3. Type Mismatch (参数类型不匹配校验)
    4. Boundary Value (数值边界越界校验)
    """
    cases = []
    case_counter = 1
    proj_prefix = f"P{project_id}-" if project_id is not None else ""
    
    for api in apis:
        api_name = api["api_name"]
        path = api["path"]
        method = api["method"]
        params = api["params"]
        headers_spec = api["headers"]
        req_example = api["req_example"] or {}
        
        # 基础 Header 构造
        default_headers = {h["name"]: h["example"] or "application/json" for h in headers_spec}
        
        # 1. 基础默认请求体构造 (正向基准)
        base_body = {}
        for p in params:
            p_name = p["name"]
            p_type = p["type"].lower()
            p_example = p["example"]
            
            # 自动决定一个合规测试值
            if isinstance(req_example, dict) and p_name in req_example:
                base_body[p_name] = req_example[p_name]
            elif p_example:
                base_body[p_name] = p_example
            else:
                if "int" in p_type or "long" in p_type or "num" in p_type:
                    base_body[p_name] = 2039
                elif "bool" in p_type:
                    base_body[p_name] = True
                elif "array" in p_type or "list" in p_type:
                    base_body[p_name] = []
                else:
                    base_body[p_name] = "test_val"

        # === 1. 正向功能测试 (HAPPY PATH) ===
        # 用例 A: 完整参数请求
        cases.append({
            "case_id": f"CASE-{proj_prefix}{case_counter:03d}",
            "project_id": project_id,
            "api_name": api_name,
            "api_path": path,
            "method": method,
            "case_type": "happy_path",
            "params": params,
            "description": f"【正向】{api_name} - 传入完整合规参数",
            "request_headers": default_headers.copy(),
            "request_body": base_body.copy(),
            "expected": {
                "status_code": 200,
                "assertions": [
                    {"type": "json_field", "field": "success", "op": "eq", "value": True},
                    {"type": "json_field", "field": "errCode", "op": "in", "value": [0, 200]}
                ]
            }
        })
        case_counter += 1

        # 用例 B: 仅必填项请求 (如果有可选参数)
        optional_params = [p for p in params if not p["required"]]
        if optional_params:
            required_only_body = {p["name"]: base_body[p["name"]] for p in params if p["required"] and p["name"] in base_body}
            cases.append({
                "case_id": f"CASE-{proj_prefix}{case_counter:03d}",
                "project_id": project_id,
                "api_name": api_name,
                "api_path": path,
                "method": method,
                "case_type": "happy_path",
                "params": params,
                "description": f"【正向】{api_name} - 仅传入必填参数",
                "request_headers": default_headers.copy(),
                "request_body": required_only_body,
                "expected": {
                    "status_code": 200,
                    "assertions": [
                        {"type": "json_field", "field": "success", "op": "eq", "value": True}
                    ]
                }
            })
            case_counter += 1

        # === 2. 必填与空值缺失校验 (FIELD VALIDATION) ===
        if method in ["POST", "PUT"] and params:
            for p in params:
                p_name = p["name"]
                if p["required"]:
                    # 缺失必填字段
                    test_body_missing = base_body.copy()
                    if p_name in test_body_missing:
                        del test_body_missing[p_name]
                    cases.append({
                        "case_id": f"CASE-{proj_prefix}{case_counter:03d}",
                        "project_id": project_id,
                        "api_name": api_name,
                        "api_path": path,
                        "method": method,
                        "case_type": "missing_param",
                        "params": params,
                        "description": f"【异常】{api_name} - 缺失必填参数 [{p_name}]",
                        "request_headers": default_headers.copy(),
                        "request_body": test_body_missing,
                        "expected": {
                            "status_code": 200,
                            "assertions": [
                                {"type": "json_field", "field": "success", "op": "eq", "value": False}
                            ]
                        }
                    })
                    case_counter += 1

                    # 必填字段传 Null
                    test_body_null = base_body.copy()
                    test_body_null[p_name] = None
                    cases.append({
                        "case_id": f"CASE-{proj_prefix}{case_counter:03d}",
                        "project_id": project_id,
                        "api_name": api_name,
                        "api_path": path,
                        "method": method,
                        "case_type": "invalid_param",
                        "params": params,
                        "description": f"【异常】{api_name} - 必填参数 [{p_name}] 传入 Null",
                        "request_headers": default_headers.copy(),
                        "request_body": test_body_null,
                        "expected": {
                            "status_code": 200,
                            "assertions": [
                                {"type": "json_field", "field": "success", "op": "eq", "value": False}
                            ]
                        }
                    })
                    case_counter += 1

        # === 3. 数据类型不匹配测试 (TYPE MISMATCH) ===
        if method in ["POST", "PUT"] and params:
            for p in params:
                p_name = p["name"]
                p_type = p["type"].lower()
                
                # 如果是数字，发送字符串
                if "int" in p_type or "long" in p_type or "num" in p_type:
                    test_body_mismatch = base_body.copy()
                    test_body_mismatch[p_name] = "invalid_string_type"
                    cases.append({
                        "case_id": f"CASE-{proj_prefix}{case_counter:03d}",
                        "project_id": project_id,
                        "api_name": api_name,
                        "api_path": path,
                        "method": method,
                        "case_type": "type_mismatch",
                        "params": params,
                        "description": f"【异常】{api_name} - 参数 [{p_name}] 类型不匹配 (要求数值，传入字符串)",
                        "request_headers": default_headers.copy(),
                        "request_body": test_body_mismatch,
                        "expected": {
                            "status_code": 200,
                            "assertions": [
                                {"type": "json_field", "field": "success", "op": "eq", "value": False}
                            ]
                        }
                    })
                    case_counter += 1

        # === 4. 数值边界值校验测试 (BOUNDARY VALUES) ===
        if method in ["POST", "PUT"] and params:
            for p in params:
                p_name = p["name"]
                p_type = p["type"].lower()
                
                # 数字型边界值 (负数、大数溢出)
                if "int" in p_type or "long" in p_type or "num" in p_type:
                    # 负数越界
                    test_body_neg = base_body.copy()
                    test_body_neg[p_name] = -1
                    cases.append({
                        "case_id": f"CASE-{proj_prefix}{case_counter:03d}",
                        "project_id": project_id,
                        "api_name": api_name,
                        "api_path": path,
                        "method": method,
                        "case_type": "boundary",
                        "params": params,
                        "description": f"【异常】{api_name} - 参数 [{p_name}] 数值越界 (负数边界 -1)",
                        "request_headers": default_headers.copy(),
                        "request_body": test_body_neg,
                        "expected": {
                            "status_code": 200,
                            "assertions": [
                                {"type": "json_field", "field": "success", "op": "eq", "value": False}
                            ]
                        }
                    })
                    case_counter += 1

                    # 溢出大数
                    test_body_overflow = base_body.copy()
                    test_body_overflow[p_name] = 9223372036854775807 # Long 最大值
                    cases.append({
                        "case_id": f"CASE-{proj_prefix}{case_counter:03d}",
                        "project_id": project_id,
                        "api_name": api_name,
                        "api_path": path,
                        "method": method,
                        "case_type": "boundary",
                        "params": params,
                        "description": f"【异常】{api_name} - 参数 [{p_name}] 数值溢出 (最大正整数越界)",
                        "request_headers": default_headers.copy(),
                        "request_body": test_body_overflow,
                        "expected": {
                            "status_code": 200,
                            "assertions": [
                                {"type": "json_field", "field": "success", "op": "eq", "value": False}
                            ]
                        }
                    })
                    case_counter += 1

    return cases
