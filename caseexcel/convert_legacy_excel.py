#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旧格式 Excel → 新格式 Excel 转换器
旧格式列: 需求ID, 前置条件, 用例步骤, 预期结果, 用例类型, 用例状态, 用例等级, 创建人
新格式列: 用例目录, 用例标题, 等级, 前置条件, 步骤描述类型, 步骤描述, 预期结果, 标签, 关联需求
"""

import pandas as pd
import re
import sys
import argparse
from datetime import datetime


def extract_title_from_steps(steps_text):
    """从用例步骤中提取标题"""
    if pd.isna(steps_text) or not str(steps_text).strip():
        return "未命名用例"

    text = str(steps_text).strip()

    # 尝试提取第一行
    first_line = text.split('\n')[0]

    # 去掉常见的步骤前缀
    cleaned = re.sub(r'^步骤[:：]?\s*', '', first_line)
    cleaned = re.sub(r'^\d+[、.\s]+', '', cleaned)

    # 去掉 "预期:" 之后的内容
    cleaned = re.split(r'预期[:：]', cleaned)[0].strip()

    # 限制长度
    if len(cleaned) > 30:
        cleaned = cleaned[:30] + "..."

    return cleaned if cleaned else "未命名用例"


def convert_steps_format(steps_text):
    """将旧格式步骤统一为新格式"""
    if pd.isna(steps_text):
        return ""

    text = str(steps_text).strip()

    # 去掉 "步骤:" 前缀
    text = re.sub(r'^步骤[:：]?\s*', '', text)

    # 统一编号格式：1. xxx -> 1、xxx
    text = re.sub(r'^(\d+)[.\s]+', r'\1、', text, flags=re.MULTILINE)

    # 将 "预期:" 后的内容移到预期结果（这里只清理步骤里的预期）
    text = re.split(r'\n?\s*预期[:：]', text)[0].strip()

    return text


def convert_level(old_level):
    """旧等级(高/中/低) → 新等级(P0/P1/P2)"""
    mapping = {
        '高': 'P0',
        '中': 'P1',
        '低': 'P2'
    }
    return mapping.get(str(old_level).strip(), 'P1')


def detect_step_type(steps_text):
    """自动判断步骤描述类型"""
    if pd.isna(steps_text):
        return "文本"
    text = str(steps_text).strip()
    if re.search(r'^\d+[、.\s]', text):
        return "步骤"
    return "文本"


def convert_excel(input_path, output_path=None, module_name=""):
    """执行转换"""
    print(f"[读取] {input_path}")
    df = pd.read_excel(input_path)

    print(f"[信息] 原列名: {list(df.columns)}")
    print(f"[信息] 共 {len(df)} 条用例")

    # 构建新格式数据
    new_data = []

    for idx, row in df.iterrows():
        # 提取/转换字段
        old_steps = row.get('用例步骤', '')

        new_row = {
            '用例目录': module_name or row.get('所属模块', ''),
            '用例标题': extract_title_from_steps(old_steps),
            '等级': convert_level(row.get('用例等级', '中')),
            '前置条件': row.get('前置条件', ''),
            '步骤描述类型': detect_step_type(old_steps),
            '步骤描述': convert_steps_format(old_steps),
            '预期结果': row.get('预期结果', ''),
            '标签': '',
            '关联需求': str(row.get('需求ID', '')) if pd.notna(row.get('需求ID', '')) else ''
        }
        new_data.append(new_row)

    new_df = pd.DataFrame(new_data)

    # 输出路径
    if not output_path:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"新格式测试用例_{timestamp}.xlsx"

    new_df.to_excel(output_path, index=False, engine='openpyxl')
    print(f"[完成] 新格式已导出: {output_path}")
    print(f"[信息] 新列名: {list(new_df.columns)}")

    return output_path


def main():
    parser = argparse.ArgumentParser(description='旧格式Excel转新格式')
    parser.add_argument('--input', '-i', required=True, help='旧格式Excel文件路径')
    parser.add_argument('--output', '-o', help='输出文件路径（可选）')
    parser.add_argument('--module', '-m', default='', help='用例目录/模块名称（可选）')

    args = parser.parse_args()
    convert_excel(args.input, args.output, args.module)


if __name__ == '__main__':
    main()
