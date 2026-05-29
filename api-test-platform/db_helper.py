import sqlite3
import json
import os
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db.sqlite3")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def save_environments_from_apis(conn, apis):
    """从解析出的 APIS 列表中提取环境配置并保存入库"""
    envs = getattr(apis, "envs", [])
    if not envs:
        return
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for env in envs:
        # 检查是否已存在相同 base_url
        cursor.execute("SELECT id FROM env_domains WHERE base_url = ?", (env["base_url"],))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO env_domains (name, base_url, created_time)
            VALUES (?, ?, ?)
            """, (env["name"], env["base_url"], now_str))

def seed_existing_projects_if_needed(conn):
    """如果 apis 或 cases 表为空，但 projects 中有项目，则从其 md_path 自动解析并初始化"""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM apis")
    api_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM cases")
    case_count = cursor.fetchone()[0]
    
    if api_count == 0 and case_count == 0:
        cursor.execute("SELECT id, name, md_path FROM projects")
        projects = [dict(r) for r in cursor.fetchall()]
        if not projects:
            return
            
        print("[DB] Seeding persistent apis and cases for existing projects...")
        from core.parser import parse_markdown_spec, generate_test_cases
        for proj in projects:
            proj_id = proj["id"]
            md_path = proj["md_path"]
            if os.path.exists(md_path):
                try:
                    apis = parse_markdown_spec(md_path)
                    save_environments_from_apis(conn, apis)
                    cases = generate_test_cases(apis, project_id=proj_id)
                    
                    for api in apis:
                        cursor.execute("""
                        INSERT INTO apis (project_id, api_name, path, method, headers, params, req_example, res_example)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            proj_id,
                            api["api_name"],
                            api["path"],
                            api["method"],
                            json.dumps(api.get("headers", [])),
                            json.dumps(api.get("params", [])),
                            json.dumps(api.get("req_example", {})),
                            json.dumps(api.get("res_example", {}))
                        ))
                        
                    for case in cases:
                        cursor.execute("""
                        INSERT INTO cases (project_id, case_id, api_name, api_path, method, case_type, description, params, request_headers, request_body, expected)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            proj_id,
                            case["case_id"],
                            case["api_name"],
                            case["api_path"],
                            case["method"],
                            case["case_type"],
                            case["description"],
                            json.dumps(case.get("params", [])),
                            json.dumps(case.get("request_headers", {})),
                            json.dumps(case.get("request_body", {})),
                            json.dumps(case.get("expected", {}))
                        ))
                    print(f"[DB] Successfully seeded project '{proj['name']}' with {len(apis)} apis and {len(cases)} cases.")
                except Exception as e:
                    print(f"[DB] Failed to seed project '{proj['name']}' from '{md_path}': {e}")
        conn.commit()

def init_db():
    """初始化数据库并创建表结构，自动录入默认数据"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. 项目表 (New)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            md_path TEXT NOT NULL,
            created_time TEXT NOT NULL
        )
        """)
        
        # 2. 环境域名表 (New)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS env_domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            created_time TEXT NOT NULL
        )
        """)
        
        # 3. 批量运行测试报告表 (Add project_id and env_id)
        # SQLite 默认不强行检查 Foreign Key 约束（除非显式启用 PRAGMA foreign_keys = ON）
        # 我们用外键语义保证扩展性，并在业务层做处理
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL DEFAULT 1,
            env_id INTEGER,
            timestamp TEXT NOT NULL,
            total_cases INTEGER NOT NULL,
            success_cases INTEGER NOT NULL,
            failed_cases INTEGER NOT NULL,
            pass_rate REAL NOT NULL,
            avg_response_time REAL NOT NULL,
            base_url TEXT,
            token TEXT,
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
            FOREIGN KEY (env_id) REFERENCES env_domains (id) ON DELETE SET NULL
        )
        """)
        
        # 4. 用例结果明细表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            case_id TEXT NOT NULL,
            api_name TEXT NOT NULL,
            api_path TEXT NOT NULL,
            method TEXT NOT NULL,
            case_type TEXT NOT NULL,
            status TEXT NOT NULL,
            response_code INTEGER,
            response_time REAL,
            error_message TEXT,
            request_headers TEXT,
            request_body TEXT,
            response_headers TEXT,
            response_body TEXT,
            FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
        )
        """)

        # 5. 接口规约表 (New)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS apis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            api_name TEXT NOT NULL,
            path TEXT NOT NULL,
            method TEXT NOT NULL,
            headers TEXT,      -- 序列化的 JSON Header
            params TEXT,       -- 序列化的 JSON 参数表
            req_example TEXT,  -- 序列化的 JSON 请求体示例
            res_example TEXT,  -- 序列化的 JSON 响应体示例
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
        """)

        # 6. 测试用例表 (New)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            case_id TEXT NOT NULL UNIQUE,
            api_name TEXT NOT NULL,
            api_path TEXT NOT NULL,
            method TEXT NOT NULL,
            case_type TEXT NOT NULL,
            description TEXT,
            params TEXT,            -- 序列化的 JSON 参数表
            request_headers TEXT,   -- 序列化的 JSON 头部数据
            request_body TEXT,      -- 序列化的 JSON 请求体模板
            expected TEXT,          -- 序列化的 JSON 期待断言结果
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
        """)
        conn.commit()

        # === 动态数据表结构升级迁移 (ALTER TABLE) ===
        cursor.execute("PRAGMA table_info(reports)")
        columns = [col[1] for col in cursor.fetchall()]
        if "project_id" not in columns:
            try:
                cursor.execute("ALTER TABLE reports ADD COLUMN project_id INTEGER NOT NULL DEFAULT 1")
                conn.commit()
                print("[DB] Migrated: Added project_id column to reports table successfully.")
            except Exception as e:
                print("[DB] Migration error adding project_id column:", e)
        if "env_id" not in columns:
            try:
                cursor.execute("ALTER TABLE reports ADD COLUMN env_id INTEGER")
                conn.commit()
                print("[DB] Migrated: Added env_id column to reports table successfully.")
            except Exception as e:
                print("[DB] Migration error adding env_id column:", e)
        
        # === 自动初始化默认项目数据 (种子数据) ===
        cursor.execute("SELECT COUNT(*) FROM projects")
        if cursor.fetchone()[0] == 0:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 自动定位 workspace 下的 接口清单.md 作为默认文档路径
            workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            default_md = os.path.join(workspace_dir, "接口清单.md")
            cursor.execute("""
            INSERT INTO projects (name, description, md_path, created_time)
            VALUES (?, ?, ?, ?)
            """, ("默认智能体测试项目", "系统自动解析的 workspace 默认文档项目", default_md, now_str))
            conn.commit()
            print("[DB] Initialized default project successfully.")
            
        # === 自动解析现有项目到 apis 和 cases 表，并动态注册环境 ===
        seed_existing_projects_if_needed(conn)
        
        # 兜底：如果依然没有任何环境配置，自动创建默认本地环境
        cursor.execute("SELECT COUNT(*) FROM env_domains")
        if cursor.fetchone()[0] == 0:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
            INSERT INTO env_domains (name, base_url, created_time)
            VALUES (?, ?, ?)
            """, ("本地测试环境", "http://127.0.0.1:8000", now_str))
            conn.commit()
            print("[DB] No environments parsed, seeded default localhost environment.")

# ==================== 项目管理 CRUD (Project Operations) ====================

def get_projects():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]

def get_project(project_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def add_project(name, description, md_path):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO projects (name, description, md_path, created_time)
        VALUES (?, ?, ?, ?)
        """, (name, description, md_path, now_str))
        conn.commit()
        return cursor.lastrowid

def update_project(project_id, name, description, md_path):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE projects
        SET name = ?, description = ?, md_path = ?
        WHERE id = ?
        """, (name, description, md_path, project_id))
        conn.commit()
        return cursor.rowcount > 0

def delete_project(project_id):
    with get_db() as conn:
        cursor = conn.cursor()
        # 删除项目及其测试报告明细、接口与用例
        cursor.execute("DELETE FROM apis WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM cases WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM reports WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        return cursor.rowcount > 0

# ==================== 环境域名管理 CRUD (Env Operations) ====================

def get_env_domains():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM env_domains ORDER BY id ASC")
        return [dict(r) for r in cursor.fetchall()]

def get_env_domain(env_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM env_domains WHERE id = ?", (env_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def add_env_domain(name, base_url):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO env_domains (name, base_url, created_time)
        VALUES (?, ?, ?)
        """, (name, base_url, now_str))
        conn.commit()
        return cursor.lastrowid

def update_env_domain(env_id, name, base_url):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE env_domains
        SET name = ?, base_url = ?
        WHERE id = ?
        """, (name, base_url, env_id))
        conn.commit()
        return cursor.rowcount > 0

def delete_env_domain(env_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM env_domains WHERE id = ?", (env_id,))
        conn.commit()
        return cursor.rowcount > 0

# ==================== 测试报告与结果查询 ====================

def save_report(project_id, timestamp, total_cases, success_cases, failed_cases, pass_rate, avg_response_time, base_url, token, results, env_id=None):
    """保存批量测试报告，强关联 project_id 与 env_id"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO reports (project_id, env_id, timestamp, total_cases, success_cases, failed_cases, pass_rate, avg_response_time, base_url, token)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (project_id, env_id, timestamp, total_cases, success_cases, failed_cases, pass_rate, avg_response_time, base_url, token))
        
        report_id = cursor.lastrowid
        
        for r in results:
            cursor.execute("""
            INSERT INTO results (
                report_id, case_id, api_name, api_path, method, case_type, status,
                response_code, response_time, error_message, request_headers, request_body,
                response_headers, response_body
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id,
                r.get("case_id"),
                r.get("api_name"),
                r.get("api_path"),
                r.get("method"),
                r.get("case_type"),
                r.get("status"),
                r.get("response_code"),
                r.get("response_time"),
                r.get("error_message"),
                json.dumps(r.get("request_headers", {})),
                r.get("request_body") if isinstance(r.get("request_body"), str) else json.dumps(r.get("request_body")),
                json.dumps(r.get("response_headers", {})),
                r.get("response_body") if isinstance(r.get("response_body"), str) else json.dumps(r.get("response_body"))
            ))
        conn.commit()
        return report_id

def get_all_reports(project_id=None):
    """获取历史报告，支持按项目进行过滤"""
    with get_db() as conn:
        cursor = conn.cursor()
        if project_id is not None:
            cursor.execute("""
                SELECT reports.*, projects.name as project_name 
                FROM reports 
                LEFT JOIN projects ON reports.project_id = projects.id 
                WHERE reports.project_id = ? 
                ORDER BY reports.id DESC
            """, (project_id,))
        else:
            cursor.execute("""
                SELECT reports.*, projects.name as project_name 
                FROM reports 
                LEFT JOIN projects ON reports.project_id = projects.id 
                ORDER BY reports.id DESC
            """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def get_report_detail(report_id):
    """获取某个特定报告的明细结果"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
        report = cursor.fetchone()
        if not report:
            return None
            
        cursor.execute("SELECT * FROM results WHERE report_id = ?", (report_id,))
        results = cursor.fetchall()
        
        detail_results = []
        for r in results:
            res_dict = dict(r)
            try:
                res_dict["request_headers"] = json.loads(res_dict["request_headers"]) if res_dict["request_headers"] else {}
            except Exception:
                pass
            try:
                res_dict["response_headers"] = json.loads(res_dict["response_headers"]) if res_dict["response_headers"] else {}
            except Exception:
                pass
            detail_results.append(res_dict)
            
        return {
            "summary": dict(report),
            "results": detail_results
        }

def save_project_apis_and_cases(project_id, md_path):
    """根据 markdown 文件路径解析并存储项目的 apis 和 cases"""
    if not os.path.exists(md_path):
        return False
        
    from core.parser import parse_markdown_spec, generate_test_cases
    try:
        apis = parse_markdown_spec(md_path)
        cases = generate_test_cases(apis, project_id=project_id)
        
        with get_db() as conn:
            cursor = conn.cursor()
            # 动态同步解析出的环境
            save_environments_from_apis(conn, apis)
            # 清空原有的接口规约与用例
            cursor.execute("DELETE FROM apis WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM cases WHERE project_id = ?", (project_id,))
            
            for api in apis:
                cursor.execute("""
                INSERT INTO apis (project_id, api_name, path, method, headers, params, req_example, res_example)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    project_id,
                    api["api_name"],
                    api["path"],
                    api["method"],
                    json.dumps(api.get("headers", [])),
                    json.dumps(api.get("params", [])),
                    json.dumps(api.get("req_example", {})),
                    json.dumps(api.get("res_example", {}))
                ))
                
            for case in cases:
                cursor.execute("""
                INSERT INTO cases (project_id, case_id, api_name, api_path, method, case_type, description, params, request_headers, request_body, expected)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    project_id,
                    case["case_id"],
                    case["api_name"],
                    case["api_path"],
                    case["method"],
                    case["case_type"],
                    case["description"],
                    json.dumps(case.get("params", [])),
                    json.dumps(case.get("request_headers", {})),
                    json.dumps(case.get("request_body", {})),
                    json.dumps(case.get("expected", {}))
                ))
            conn.commit()
        return True
    except Exception as e:
        print(f"[DB] Error saving apis/cases for project {project_id}: {e}")
        return False

def get_apis_by_project(project_id):
    """根据项目 ID 获取所有持久化接口规约"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM apis WHERE project_id = ? ORDER BY id ASC", (project_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            api = dict(r)
            try:
                api["headers"] = json.loads(api["headers"]) if api["headers"] else []
            except Exception:
                api["headers"] = []
            try:
                api["params"] = json.loads(api["params"]) if api["params"] else []
            except Exception:
                api["params"] = []
            try:
                api["req_example"] = json.loads(api["req_example"]) if api["req_example"] else {}
            except Exception:
                api["req_example"] = {}
            try:
                api["res_example"] = json.loads(api["res_example"]) if api["res_example"] else {}
            except Exception:
                api["res_example"] = {}
            result.append(api)
        return result

def get_cases_by_project(project_id):
    """根据项目 ID 获取所有持久化测试用例"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cases WHERE project_id = ? ORDER BY id ASC", (project_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            case = dict(r)
            try:
                case["params"] = json.loads(case["params"]) if case["params"] else []
            except Exception:
                case["params"] = []
            try:
                case["request_headers"] = json.loads(case["request_headers"]) if case["request_headers"] else {}
            except Exception:
                case["request_headers"] = {}
            try:
                case["request_body"] = json.loads(case["request_body"]) if case["request_body"] else {}
            except Exception:
                pass
            try:
                case["expected"] = json.loads(case["expected"]) if case["expected"] else {}
            except Exception:
                case["expected"] = {}
            result.append(case)
        return result

def migrate_cases(case_ids, target_project_id):
    """批量迁移测试用例到另一个项目，并按顺序重命名防止冲突"""
    if not case_ids:
        return 0, []
        
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. 验证目标项目是否存在
        cursor.execute("SELECT id, name FROM projects WHERE id = ?", (target_project_id,))
        proj_row = cursor.fetchone()
        if not proj_row:
            raise ValueError(f"目标项目 ID {target_project_id} 不存在")
            
        # 2. 查询目标项目现有的最大数字编号
        cursor.execute("SELECT case_id FROM cases WHERE project_id = ?", (target_project_id,))
        target_cases = cursor.fetchall()
        
        max_counter = 0
        prefix_pattern = f"CASE-P{target_project_id}-"
        for tc in target_cases:
            cid = tc["case_id"]
            if cid.startswith(prefix_pattern):
                try:
                    num_str = cid[len(prefix_pattern):]
                    counter = int(num_str)
                    if counter > max_counter:
                        max_counter = counter
                except ValueError:
                    pass
                    
        # 3. 逐个迁移用例
        migration_results = []
        proj_prefix = f"P{target_project_id}-"
        
        for case_id in case_ids:
            cursor.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,))
            row = cursor.fetchone()
            if not row:
                continue
                
            orig_case = dict(row)
            old_project_id = orig_case["project_id"]
            if old_project_id == target_project_id:
                # 已经是目标项目，跳过
                continue
                
            max_counter += 1
            new_case_id = f"CASE-{proj_prefix}{max_counter:03d}"
            
            # 更新用例的 project_id, case_id
            cursor.execute("""
            UPDATE cases
            SET project_id = ?, case_id = ?
            WHERE case_id = ?
            """, (target_project_id, new_case_id, case_id))
            
            migration_results.append({
                "old_case_id": case_id,
                "new_case_id": new_case_id
            })
            
        conn.commit()
        return len(migration_results), migration_results

if __name__ == "__main__":
    init_db()
    print("Upgraded SQLite database initialized successfully at:", DB_PATH)
    print("Existing projects:", get_projects())
    print("Existing environment presets:", get_env_domains())
