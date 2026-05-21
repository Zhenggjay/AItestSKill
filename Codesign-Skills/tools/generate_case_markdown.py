import json
import sys
from collections import Counter
from pathlib import Path


def main():
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    data = json.loads(input_path.read_text(encoding="utf-8"))
    cases = data["test_cases"]

    module_counts = Counter(case["所属模块"] for case in cases)
    priority_counts = Counter(case["优先级"] for case in cases)

    lines = [
        f"# {data['project_name']} 原型识别与测试用例",
        "",
        f"- 原型地址：{data['source_url']}",
        f"- 原型页面：{', '.join(data['prototype_pages'])}",
        f"- 用例总数：{len(cases)}",
        f"- 优先级分布：P0 {priority_counts['P0']} 条，P1 {priority_counts['P1']} 条，P2 {priority_counts['P2']} 条",
        "",
        "## 原型识别摘要",
        "",
        "本次识别到用户端核心页面包括设置、新对话、自动化任务列表，以及自动化任务的新建/编辑弹窗。主要交互包含用户设置菜单、组织切换、账单跳转、快捷调用智能体或 skill、项目选择、附件上传、自动化任务列表页签、任务创建、项目创建、执行频率配置、钉钉推送和任务编辑。",
        "",
        "## 模块用例统计",
        "",
        "| 模块 | 用例数 |",
        "|---|---:|",
    ]

    for module, count in module_counts.items():
        lines.append(f"| {module} | {count} |")

    lines.extend(["", "## 测试用例清单", ""])

    for case in cases:
        lines.extend(
            [
                f"### {case['用例编号']} {case['用例标题']}",
                "",
                f"- 所属模块：{case['所属模块']}",
                f"- 优先级：{case['优先级']}",
                f"- 前置条件：{case['前置条件']}",
                f"- 测试步骤：{case['测试步骤']}",
                f"- 测试数据：{case['测试数据']}",
                f"- 预期结果：{case['预期结果']}",
                f"- 标签：{case.get('标签', '')}",
                "",
            ]
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
