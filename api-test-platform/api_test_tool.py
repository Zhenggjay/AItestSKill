import argparse
import os
import json
import datetime
from core.parser import parse_markdown_spec, generate_test_cases
from core.executor import HTTPExecutor

def generate_markdown_report(summary, results):
    """生成漂亮的 Markdown 格式测试报告"""
    timestamp = summary["timestamp"]
    total = summary["total"]
    success = summary["success"]
    failed = summary["failed"]
    pass_rate = summary["pass_rate"]
    avg_time = summary["avg_time"]
    base_url = summary["base_url"]

    md = f"""# API 自动化测试执行报告

## 📊 测试概要 (Summary)

- **执行时间**: {timestamp}
- **请求基地址 (Base URL)**: `{base_url}`
- **用例总数**: {total}
- **成功用例**: {success}
- **失败用例**: {failed}
- **测试通过率**: **{pass_rate:.1f}%**
- **平均耗时**: **{avg_time:.1f}ms**

---

## 📋 用例执行明细 (Details)

| 用例 ID | 接口名称 | 接口路径 | 方法 | 测试类型 | 状态 | 响应码 | 耗时 (ms) | 错误原因 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    
    for r in results:
        status_emoji = "✅ SUCCESS" if r["status"] == "SUCCESS" else ("❌ FAIL" if r["status"] == "FAIL" else "⚠️ ERROR")
        err_msg = r["error_message"] or ""
        # 截短错误原因
        if len(err_msg) > 50:
            err_msg = err_msg[:47] + "..."
            
        md += f"| `{r['case_id']}` | {r['api_name']} | `{r['api_path']}` | `{r['method']}` | `{r['case_type']}` | **{status_emoji}** | {r['response_code'] or '-'} | {r['response_time']:.1f} | {err_msg} |\n"
        
    md += "\n---\n\n## 🔍 失败与异常用例诊断 (Failed / Error Cases Diagnostics)\n\n"
    
    failures = [r for r in results if r["status"] in ["FAIL", "ERROR"]]
    if not failures:
        md += "✨ **太棒了！所有测试用例全部通过！**\n"
    else:
        for idx, f in enumerate(failures, 1):
            md += f"""### {idx}. 用例 `{f['case_id']}` - {f['api_name']} ({f['case_type']})

- **请求 URL**: `{f['method']} {f['api_path']}`
- **错误详情**: `{f['error_message']}`
- **请求 Headers**:
```json
{json.dumps(f['request_headers'], indent=2, ensure_ascii=False)}
```
- **请求 Body**:
```json
{json.dumps(f['request_body'], indent=2, ensure_ascii=False) if isinstance(f['request_body'], dict) else f['request_body']}
```
- **实际响应 Body**:
```json
{json.dumps(f['response_body'], indent=2, ensure_ascii=False) if isinstance(f['response_body'], dict) else f['response_body']}
```

---
"""
    return md

def find_markdown_file():
    """在工作区中动态搜索包含 API 规格的 Markdown 文档"""
    search_keywords = ["接口", "api", "spec", "swagger", "document"]
    start_dirs = [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
    
    for sd in start_dirs:
        current_dir = sd
        for _ in range(3):  # 最多向上两层
            for root, dirs, files in os.walk(current_dir):
                # 排除冗余目录
                dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', '.vscode')]
                for file in files:
                    if file.endswith('.md'):
                        file_lower = file.lower()
                        if any(kw in file_lower for kw in search_keywords):
                            return os.path.abspath(os.path.join(root, file))
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent
            
    # 兜底查找任意 md
    for sd in start_dirs:
        current_dir = sd
        for _ in range(3):
            for root, dirs, files in os.walk(current_dir):
                dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', '.vscode')]
                for file in files:
                    if file.endswith('.md'):
                        return os.path.abspath(os.path.join(root, file))
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent
    return None

def main():
    parser = argparse.ArgumentParser(description="接口自动化用例生成与执行 CLI 工具")
    parser.add_argument("--input", default=None, help="接口定义 Markdown 文件路径")
    parser.add_argument("--output-dir", default="./output", help="结果输出目录")
    parser.add_argument("--run", action="store_true", help="是否立即执行生成的所有测试用例")
    parser.add_argument("--token", default=None, help="全局鉴权令牌 (homingtoken)")
    parser.add_argument("--base-url", default=None, help="请求基地址")
    
    args = parser.parse_args()
    
    # 转换为绝对路径
    input_file = os.path.abspath(args.input) if args.input else None
    output_dir = os.path.abspath(args.output_dir)
    
    if not input_file or not os.path.exists(input_file):
        # 尝试动态查找
        found_file = find_markdown_file()
        if found_file:
            input_file = found_file
            print(f"[INFO] 动态定位到接口定义文档: {input_file}")
        else:
            # 兼容默认相对路径 fallback
            fallback_paths = [
                "../接口清单.md",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "接口清单.md"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "接口清单.md")
            ]
            for p in fallback_paths:
                if os.path.exists(p):
                    input_file = os.path.abspath(p)
                    print(f"[INFO] 找到默认接口定义文档 fallback: {input_file}")
                    break
            
            if not input_file:
                print(f"[ERROR] 找不到任何有效的接口定义文档。请提供 --input 参数指明。")
                return
    else:
        print(f"[INFO] 开始解析接口定义文档: {input_file}")

    try:
        apis = parse_markdown_spec(input_file)
        print(f"[SUCCESS] 解析完成！共提取到 {len(apis)} 个接口规范。")
        
        cases = generate_test_cases(apis)
        print(f"[SUCCESS] 用例生成完成！共自动生成 {len(cases)} 个测试用例。")
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存 api_specs.json
        specs_path = os.path.join(output_dir, "api_specs.json")
        with open(specs_path, 'w', encoding='utf-8') as f:
            json.dump(apis, f, indent=2, ensure_ascii=False)
        print(f"[SAVE] 接口规格文件已保存至: {specs_path}")
        
        # 保存 api_test_cases.json
        cases_path = os.path.join(output_dir, "api_test_cases.json")
        with open(cases_path, 'w', encoding='utf-8') as f:
            json.dump(cases, f, indent=2, ensure_ascii=False)
        print(f"[SAVE] 自动生成用例已保存至: {cases_path}")
        
        if args.run:
            # 动态推断基地址
            envs = getattr(apis, "envs", [])
            base_url = args.base_url
            if not base_url:
                if envs:
                    base_url = envs[0]["base_url"]
                    print(f"[INFO] 未指定 --base-url，动态选择接口文档中的首个环境: '{envs[0]['name']}' ({base_url})")
                else:
                    base_url = "http://127.0.0.1:8000"
                    print(f"[INFO] 未指定 --base-url 且未解析到环境配置，使用默认本地地址: {base_url}")
            else:
                print(f"[INFO] 使用用户指定基地址: {base_url}")
                
            print("\n[START] 开始执行接口自动化测试...")
            executor = HTTPExecutor(base_url=base_url, default_token=args.token)
            
            results = []
            
            # 使用自带的简单终端回调打印日志
            def terminal_log(msg):
                print(msg)
                
            for c in cases:
                res = executor.run_case(c, log_callback=terminal_log)
                results.append(res)
                
            # 统计汇总
            total = len(results)
            success = sum(1 for r in results if r["status"] == "SUCCESS")
            failed = total - success
            pass_rate = (success / total) * 100.0 if total > 0 else 0
            avg_time = sum(r["response_time"] for r in results) / total if total > 0 else 0
            
            summary = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total": total,
                "success": success,
                "failed": failed,
                "pass_rate": pass_rate,
                "avg_time": avg_time,
                "base_url": base_url
            }
            
            # 保存 api_test_results.json
            results_path = os.path.join(output_dir, "api_test_results.json")
            with open(results_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "summary": summary,
                    "results": results
                }, f, indent=2, ensure_ascii=False)
            print(f"[SAVE] 测试结果明细已保存至: {results_path}")
            
            # 生成测试报告 Markdown
            report_md = generate_markdown_report(summary, results)
            report_path = os.path.join(output_dir, "api_test_report.md")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_md)
            print(f"[SAVE] 可视化 Markdown 报告已生成至: {report_path}")
            
            print("\n" + "="*40)
            print(f"[DONE] 测试执行完毕！通过率: {pass_rate:.1f}%, 成功: {success}, 失败: {failed}")
            print("="*40)
        else:
            print("\n[INFO] 提示: 您可以添加 `--run` 参数以执行用例。")
            print("例如: python api_test_tool.py --run --token \"<YOUR_TOKEN>\"")
            
    except Exception as e:
        print(f"[ERROR] 发生异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
