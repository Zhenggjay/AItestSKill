# -*- coding: utf-8 -*-
"""
通用测试用例导出工具 v3.0
支持导出统一格式 Excel（用例目录/用例标题/等级/前置条件/步骤描述类型/步骤描述/预期结果/标签/关联需求）

使用方式：
python test_case_exporter.py --input cases.json --format both --creator "郑国杰_801080"
"""

import json
import sys
import re
import argparse
import pandas as pd
from datetime import datetime
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill


creator = "郑国杰_801080"

# ==================== 样式配置 ====================
DEFAULT_STYLES = {
    'header_fill': '4472C4',
    'header_font_color': 'FFFFFF',
    'priority_colors': {
        'P0': 'FF6B6B',
        'P1': 'FFA94D',
        'P2': '69DB7C',
        'P3': '74C0FC',
    },
    'total_fill': 'E2EFDA',
}

# ==================== 统一 Excel 列定义（截图格式）====================
UNIFIED_COLUMNS = [
    '用例目录', '用例标题', '等级', '前置条件',
    '步骤描述类型', '步骤描述', '预期结果', '标签', '关联需求'
]

UNIFIED_COLUMN_WIDTHS = {
    '用例目录': 22,
    '用例标题': 35,
    '等级': 10,
    '前置条件': 30,
    '步骤描述类型': 14,
    '步骤描述': 55,
    '预期结果': 55,
    '标签': 15,
    '关联需求': 15,
}


def create_styles():
    """创建样式对象"""
    header_fill = PatternFill(
        start_color=DEFAULT_STYLES['header_fill'],
        end_color=DEFAULT_STYLES['header_fill'],
        fill_type='solid'
    )
    header_font = Font(bold=True, size=11, color=DEFAULT_STYLES['header_font_color'])
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left_align = Alignment(horizontal='left', vertical='center', wrap_text=True)

    priority_fills = {
        k: PatternFill(start_color=v, end_color=v, fill_type='solid')
        for k, v in DEFAULT_STYLES['priority_colors'].items()
    }

    total_fill = PatternFill(
        start_color=DEFAULT_STYLES['total_fill'],
        end_color=DEFAULT_STYLES['total_fill'],
        fill_type='solid'
    )

    return {
        'header_fill': header_fill,
        'header_font': header_font,
        'border': thin_border,
        'center_align': center_align,
        'left_align': left_align,
        'priority_fills': priority_fills,
        'total_fill': total_fill,
    }


def get_step_type(steps_text):
    """
    判断步骤描述类型：
    - "步骤"：包含编号步骤（如 1、 1. Step 1 等）
    - "文本"：纯描述性文字
    """
    if not steps_text:
        return '文本'
    text = str(steps_text)
    # 匹配编号步骤模式：1、 1. 1． Step 1 步骤1 等
    pattern = r'(?:^|\s)(?:\d+[、.．]\s*|[Ss]tep\s*\d+\s*|[步驟步骤]\s*\d+\s*)'
    if re.search(pattern, text):
        return '步骤'
    return '文本'


def convert_to_unified_format(test_cases):
    """
    将 JSON 标准格式转换为统一 Excel 格式（截图字段）

    字段映射：
    - 用例目录    <- 所属模块
    - 用例标题    <- 用例标题
    - 等级        <- 优先级（保留 P0/P1/P2）
    - 前置条件    <- 前置条件
    - 步骤描述类型 <- 根据测试步骤内容自动判断
    - 步骤描述    <- 测试步骤（去除编号前缀，统一为"1、xxx 2、xxx"格式）
    - 预期结果    <- 预期结果
    - 标签        <- 空或可扩展
    - 关联需求    <- 空或可扩展
    """
    unified_cases = []
    for case in test_cases:
        steps_raw = case.get('测试步骤', '')
        # 统一步骤编号格式：将 "1. " "1、" 等统一为 "1、"
        steps_formatted = re.sub(r'(\d+)[.．]\s*', r'\1、', str(steps_raw))

        unified_case = {
            '用例目录': case.get('所属模块', ''),
            '用例标题': case.get('用例标题', ''),
            '等级': case.get('优先级', 'P2'),
            '前置条件': case.get('前置条件', ''),
            '步骤描述类型': get_step_type(steps_raw),
            '步骤描述': steps_formatted,
            '预期结果': case.get('预期结果', ''),
            '标签': case.get('标签', ''),
            '关联需求': case.get('关联需求', ''),
        }
        unified_cases.append(unified_case)

    return unified_cases


def generate_summary(test_cases):
    """生成用例汇总统计"""
    stats = {}
    for case in test_cases:
        module = case.get('所属模块', '未分类')
        priority = case.get('优先级', 'P2')

        if module not in stats:
            stats[module] = {'用例数': 0, 'P0': 0, 'P1': 0, 'P2': 0, 'P3': 0}

        stats[module]['用例数'] += 1
        if priority in stats[module]:
            stats[module][priority] += 1

    summary = []
    total = {'用例数': 0, 'P0': 0, 'P1': 0, 'P2': 0, 'P3': 0}

    for module, counts in stats.items():
        summary.append({'分类': module, **counts})
        total['用例数'] += counts['用例数']
        for p in ['P0', 'P1', 'P2', 'P3']:
            total[p] += counts[p]

    summary.append({'分类': '合计', **total})
    return summary


def export_unified_format(test_cases, output_dir, filename_prefix, styles):
    """导出统一格式 Excel（截图字段格式）"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = output_dir / f"{filename_prefix}_{timestamp}.xlsx"

    # 转换为统一格式
    unified_cases = convert_to_unified_format(test_cases)

    df = pd.DataFrame(unified_cases)
    summary = generate_summary(test_cases)
    df_summary = pd.DataFrame(summary)

    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='测试用例', index=False)
        df_summary.to_excel(writer, sheet_name='用例汇总', index=False)

    # 美化
    wb = load_workbook(filename)
    ws = wb['测试用例']

    headers = [cell.value for cell in ws[1]]
    level_col = headers.index('等级') if '等级' in headers else None
    step_type_col = headers.index('步骤描述类型') if '步骤描述类型' in headers else None

    # 设置列宽
    for col_idx, cell in enumerate(ws[1], 1):
        col_letter = cell.column_letter
        header_name = cell.value
        if header_name in UNIFIED_COLUMN_WIDTHS:
            ws.column_dimensions[col_letter].width = UNIFIED_COLUMN_WIDTHS[header_name]

    # 设置表头样式
    for cell in ws[1]:
        cell.font = styles['header_font']
        cell.fill = styles['header_fill']
        cell.border = styles['border']
        cell.alignment = styles['center_align']

    # 设置数据行样式
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for idx, cell in enumerate(row):
            cell.border = styles['border']

            # 等级列着色（P0/P1/P2）
            if level_col is not None and idx == level_col:
                cell.alignment = styles['center_align']
                if cell.value in styles['priority_fills']:
                    cell.fill = styles['priority_fills'][cell.value]
            # 步骤描述类型列居中
            elif step_type_col is not None and idx == step_type_col:
                cell.alignment = styles['center_align']
            # 用例目录列居中
            elif idx == 0:
                cell.alignment = styles['center_align']
            else:
                cell.alignment = styles['left_align']

    # 设置行高
    ws.row_dimensions[1].height = 25
    for row_num in range(2, ws.max_row + 1):
        ws.row_dimensions[row_num].height = 50

    # 汇总表样式
    ws_summary = wb['用例汇总']
    ws_summary.column_dimensions['A'].width = 20
    for col in ['B', 'C', 'D', 'E', 'F']:
        ws_summary.column_dimensions[col].width = 10

    for cell in ws_summary[1]:
        cell.font = styles['header_font']
        cell.fill = styles['header_fill']
        cell.border = styles['border']
        cell.alignment = styles['center_align']

    for row in ws_summary.iter_rows(min_row=2, max_row=ws_summary.max_row):
        for cell in row:
            cell.border = styles['border']
            cell.alignment = styles['center_align']

    last_row = ws_summary.max_row
    for cell in ws_summary[last_row]:
        cell.font = Font(bold=True)
        cell.fill = styles['total_fill']

    wb.save(filename)
    return str(filename)


def main():
    parser = argparse.ArgumentParser(description='测试用例导出工具 v3.0（统一格式）')
    parser.add_argument('--input', '-i', type=str, required=True, help='输入JSON文件路径')
    parser.add_argument('--output', '-o', type=str, default='.', help='输出目录')
    parser.add_argument('--prefix', '-p', type=str, default='测试用例', help='文件名前缀')
    parser.add_argument('--creator', '-c', type=str, default=creator, help='创建人')

    args = parser.parse_args()

    try:
        # 读取JSON
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)

        test_cases = data.get('test_cases', [])
        if not test_cases:
            print("[ERROR] 测试用例列表为空")
            sys.exit(1)

        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        styles = create_styles()
        files = []

        # 导出统一格式
        unified_file = export_unified_format(
            test_cases, output_dir, args.prefix, styles
        )
        files.append(unified_file)
        print(f"[OK] 统一格式已导出: {unified_file}")

        print(f"\n[OK] 共生成 {len(test_cases)} 条测试用例")
        print(f"[OK] 导出文件数: {len(files)}")

    except Exception as e:
        print(f"[ERROR] 导出失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
