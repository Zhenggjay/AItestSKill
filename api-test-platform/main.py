import os
import datetime
import json
import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Query, Body, Path
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 导入核心解析执行器和数据库助手
from core.parser import parse_markdown_spec, generate_test_cases
from core.executor import HTTPExecutor
import db_helper

def resolve_base_url(project_id: Optional[int], base_url: Optional[str], env_id: Optional[int] = None) -> str:
    """动态解析获取运行时的基地址"""
    if base_url and base_url.strip():
        return base_url.strip()
        
    if env_id:
        env = db_helper.get_env_domain(env_id)
        if env and env.get("base_url"):
            return env["base_url"]
            
    if project_id:
        envs = db_helper.get_env_domains()
        if envs:
            return envs[0]["base_url"]
            
    return "http://127.0.0.1:8000"

app = FastAPI(title="API 自动化测试与可视化多项目管理平台")

# 初始化数据库结构
db_helper.init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Pydantic 模型定义 ====================

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    md_path: str

class EnvDomainCreate(BaseModel):
    name: str
    base_url: str

class RunCaseRequest(BaseModel):
    case: Dict[str, Any]
    base_url: Optional[str] = None
    token: Optional[str] = None

class RunBatchRequest(BaseModel):
    project_id: int
    case_ids: List[str]
    base_url: Optional[str] = None
    token: Optional[str] = None
    env_id: Optional[int] = None

class MigrateCasesRequest(BaseModel):
    case_ids: List[str]
    target_project_id: int

# ==================== 项目管理 APIs ====================

@app.get("/api/projects")
def get_projects_list():
    """获取所有项目列表"""
    try:
        return {"success": True, "data": db_helper.get_projects()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/{project_id}")
def get_project_by_id(project_id: int):
    """获取单个项目配置"""
    try:
        project = db_helper.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"success": True, "data": project}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects")
def create_project(proj: ProjectCreate):
    """新建测试项目"""
    try:
        # 验证接口文档路径是否存在
        if not os.path.exists(proj.md_path):
            raise HTTPException(status_code=400, detail=f"指定的接口文档路径不存在: {proj.md_path}")
        new_id = db_helper.add_project(proj.name, proj.description, proj.md_path)
        # 一次性解析导入到数据库持久化存储
        db_helper.save_project_apis_and_cases(new_id, proj.md_path)
        return {"success": True, "data": {"id": new_id}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/projects/{project_id}")
def update_project_by_id(project_id: int, proj: ProjectCreate):
    """修改测试项目配置"""
    try:
        if not os.path.exists(proj.md_path):
            raise HTTPException(status_code=400, detail=f"指定的接口文档路径不存在: {proj.md_path}")
        success = db_helper.update_project(project_id, proj.name, proj.description, proj.md_path)
        if not success:
            raise HTTPException(status_code=404, detail="项目不存在或未作修改")
        # 一次性解析更新到数据库持久化存储
        db_helper.save_project_apis_and_cases(project_id, proj.md_path)
        return {"success": True, "message": "修改项目成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/projects/{project_id}")
def delete_project_by_id(project_id: int):
    """删除测试项目（级联删除测试历史报告）"""
    try:
        success = db_helper.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"success": True, "message": "删除项目成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 环境域名管理 APIs ====================

@app.get("/api/envs")
def get_envs_list():
    """获取所有环境域名配置"""
    try:
        return {"success": True, "data": db_helper.get_env_domains()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/envs")
def create_env_domain(env: EnvDomainCreate):
    """新建环境域名"""
    try:
        # 简单清洗 base_url 去除尾部斜杠
        base_url = env.base_url.strip().rstrip('/')
        new_id = db_helper.add_env_domain(env.name, base_url)
        return {"success": True, "data": {"id": new_id}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/envs/{env_id}")
def update_env_domain_by_id(env_id: int, env: EnvDomainCreate):
    """修改环境域名"""
    try:
        base_url = env.base_url.strip().rstrip('/')
        success = db_helper.update_env_domain(env_id, env.name, base_url)
        if not success:
            raise HTTPException(status_code=404, detail="环境域名不存在或未作修改")
        return {"success": True, "message": "修改环境域名成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/envs/{env_id}")
def delete_env_domain_by_id(env_id: int):
    """删除环境域名"""
    try:
        success = db_helper.delete_env_domain(env_id)
        if not success:
            raise HTTPException(status_code=404, detail="环境域名不存在")
        return {"success": True, "message": "删除环境域名成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 接口规格与用例路由 (项目强关联) ====================

@app.get("/")
def read_root():
    """主页托管静态 UI 界面"""
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>API Test Platform Frontend Not Found</h1>")

@app.get("/api/specs")
def get_specs(project_id: int = Query(..., description="绑定的测试项目 ID")):
    """从数据库获取持久化接口规格列表"""
    try:
        project = db_helper.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="测试项目不存在")
        
        apis = db_helper.get_apis_by_project(project_id)
        if not apis:
            # 兜底：如果数据库中接口为空但 md 文件存在，重新解析并存储
            md_path = project["md_path"]
            if os.path.exists(md_path):
                db_helper.save_project_apis_and_cases(project_id, md_path)
                apis = db_helper.get_apis_by_project(project_id)
                
        return {"success": True, "data": apis}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cases")
def get_cases(project_id: int = Query(..., description="绑定的测试项目 ID")):
    """从数据库获取持久化测试用例列表"""
    try:
        project = db_helper.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="测试项目不存在")
            
        cases = db_helper.get_cases_by_project(project_id)
        if not cases:
            # 兜底：如果数据库中用例为空但 md 文件存在，重新解析并存储
            md_path = project["md_path"]
            if os.path.exists(md_path):
                db_helper.save_project_apis_and_cases(project_id, md_path)
                cases = db_helper.get_cases_by_project(project_id)
                
        return {"success": True, "data": cases}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cases/migrate")
def migrate_project_cases(req: MigrateCasesRequest):
    """批量迁移测试用例到另一个项目"""
    try:
        count, results = db_helper.migrate_cases(req.case_ids, req.target_project_id)
        return {
            "success": True,
            "message": f"成功迁移 {count} 个测试用例",
            "data": {
                "count": count,
                "results": results
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/run-case")
def run_single_case(req: RunCaseRequest):
    """PlayGround 单接口运行调试"""
    try:
        project_id = req.case.get("project_id")
        base_url = resolve_base_url(project_id, req.base_url)
        executor = HTTPExecutor(base_url=base_url, default_token=req.token)
        result = executor.run_case(req.case)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/run-batch")
def run_batch_cases(req: RunBatchRequest):
    """批量运行项目用例，通过 SSE 流式实时推送执行日志"""
    
    async def sse_generator():
        try:
            # 1. 验证项目是否存在
            project = db_helper.get_project(req.project_id)
            if not project:
                yield "data: " + json.dumps({'type': 'error', 'message': '指定的测试项目不存在'}) + "\n\n"
                return
                
            md_path = project["md_path"]
            
            # 2. 从数据库读取持久化用例
            all_cases = db_helper.get_cases_by_project(req.project_id)
            if not all_cases:
                # 兜底：若为空且 Markdown 文件存在，自动解析并保存
                if os.path.exists(md_path):
                    db_helper.save_project_apis_and_cases(req.project_id, md_path)
                    all_cases = db_helper.get_cases_by_project(req.project_id)
                else:
                    yield "data: " + json.dumps({'type': 'error', 'message': f'项目用例为空且未找到绑定的接口文档进行解析: {md_path}'}) + "\n\n"
                    return
            
            # 3. 筛选执行用例
            case_map = {c["case_id"]: c for c in all_cases}
            selected_cases = [case_map[cid] for cid in req.case_ids if cid in case_map]
            
            if not selected_cases:
                yield "data: " + json.dumps({'type': 'error', 'message': '未选择任何有效用例'}) + "\n\n"
                return
                
            base_url = resolve_base_url(req.project_id, req.base_url, req.env_id)
            yield "data: " + json.dumps({'type': 'log', 'message': f"[INFO] 开始运行项目 [{project['name']}] 自动化测试，共选择 {len(selected_cases)} 个用例"}) + "\n\n"
            yield "data: " + json.dumps({'type': 'log', 'message': f"[INFO] 运行环境基地址: {base_url}"}) + "\n\n"
            
            executor = HTTPExecutor(base_url=base_url, default_token=req.token)
            results = []
            
            # 4. 链式依次执行
            for idx, case in enumerate(selected_cases, 1):
                case_id = case["case_id"]
                api_name = case["api_name"]
                
                yield "data: " + json.dumps({'type': 'log', 'message': f'[INFO] 正在执行用例 ({idx}/{len(selected_cases)}): [{case_id}] {api_name}'}) + "\n\n"
                
                res = executor.run_case(case)
                results.append(res)
                
                status_emoji = "✅" if res["status"] == "SUCCESS" else ("❌" if res["status"] == "FAIL" else "⚠️")
                log_detail = f"{status_emoji} 用例 [{case_id}] 执行完毕，状态: {res['status']}, 耗时: {res['response_time']:.1f}ms"
                if res["error_message"]:
                    log_detail += f", 失败详情: {res['error_message']}"
                yield "data: " + json.dumps({'type': 'log', 'message': log_detail}) + "\n\n"
                
                progress_data = {
                    'type': 'progress',
                    'case_id': case_id,
                    'status': res['status'],
                    'elapsed': res['response_time'],
                    'progress_pct': (idx / len(selected_cases)) * 100.0,
                    'result': res
                }
                yield "data: " + json.dumps(progress_data, ensure_ascii=False) + "\n\n"
                
                await asyncio.sleep(0.05)

            # 5. 统计与报告归档入库
            total = len(results)
            success = sum(1 for r in results if r["status"] == "SUCCESS")
            failed = total - success
            pass_rate = (success / total) * 100.0 if total > 0 else 0
            avg_time = sum(r["response_time"] for r in results) / total if total > 0 else 0
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            report_id = db_helper.save_report(
                project_id=req.project_id,
                env_id=req.env_id,
                timestamp=timestamp,
                total_cases=total,
                success_cases=success,
                failed_cases=failed,
                pass_rate=pass_rate,
                avg_response_time=avg_time,
                base_url=base_url,
                token=req.token,
                results=results
            )
            
            yield "data: " + json.dumps({'type': 'log', 'message': f'[SUCCESS] 批量测试执行完毕！通过率: {pass_rate:.1f}%, 成功: {success}, 失败: {failed}'}) + "\n\n"
            yield "data: " + json.dumps({'type': 'log', 'message': f'[INFO] 测试报告已成功保存归档至 SQLite 数据库，报告 ID: {report_id}'}) + "\n\n"
            
            complete_data = {
                'type': 'complete',
                'report_id': report_id,
                'summary': {
                    'timestamp': timestamp,
                    'total': total,
                    'success': success,
                    'failed': failed,
                    'pass_rate': pass_rate,
                    'avg_time': avg_time,
                    'base_url': base_url
                }
            }
            yield "data: " + json.dumps(complete_data, ensure_ascii=False) + "\n\n"
            
        except Exception as e:
            yield "data: " + json.dumps({'type': 'error', 'message': f'运行时异常: {str(e)}'}) + "\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

# ==================== 测试报告 APIs ====================

@app.get("/api/reports")
def get_reports(project_id: Optional[int] = Query(None, description="按测试项目过滤历史报告")):
    """获取历史报告归档列表"""
    try:
        reports = db_helper.get_all_reports(project_id)
        return {"success": True, "data": reports}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reports/{report_id}")
def get_report(report_id: int):
    """获取特定报告的详情明细"""
    try:
        report = db_helper.get_report_detail(report_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"报告 #{report_id} 不存在")
        return {"success": True, "data": report}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 静态文件挂载 ====================
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)

@app.get("/assets/{file_name}")
def serve_assets(file_name: str):
    """支持 SPA 路由直接访问时相对基地址的寻址映射"""
    file_path = os.path.join(static_dir, "assets", file_name)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Asset not found")

app.mount("/static", StaticFiles(directory=static_dir), name="static")

