# -*- coding: utf-8 -*-
"""
统一格式 Excel 转换为 XMind 可导入格式（Markdown）
支持读取字段：用例目录/用例标题/等级/前置条件/步骤描述类型/步骤描述/预期结果/标签/关联需求

XMind 导入方式：
1. Markdown: XMind → 文件 → 导入 → Markdown
"""

import re
import sys
import argparse
import json
import os
from pathlib import Path
from datetime import datetime
import pandas as pd


class UnifiedToXmindConverter:
    """统一格式用例转换为 XMind 格式"""

    # 默认分隔符
    DEFAULT_DELIMITERS = ['-', '_', '—', '／', '/']

    # 默认列名映射（兼容新格式字段名）
    DEFAULT_COLUMN_MAPPING = {
        '用例目录': ['用例目录', '所属模块', '目录', '模块', 'category'],
        '用例标题': ['用例标题', '用例名称', '标题', '名称', 'title'],
        '步骤描述': ['步骤描述', '用例步骤', '测试步骤', '步骤', 'steps'],
        '预期结果': ['预期结果', '预期', 'expected', 'Expected'],
        '等级': ['等级', '优先级', '用例等级', 'priority'],
    }

    # 等级映射：将"高/中/低"转换为"P0/P1/P2"
    PRIORITY_MAPPING = {
        '高': 'P0',
        '中': 'P1',
        '低': 'P2',
        'P0': 'P0',
        'P1': 'P1',
        'P2': 'P2',
    }

    # 配置文件路径
    CONFIG_FILE = 'config.json'

    def __init__(self, root_name: str = None):
        """
        初始化转换器

        配置优先级（从高到低）：
        1. 显式传入的参数
        2. 环境变量（TAPD_ROOT_NAME）
        3. 配置文件 config.json
        4. 默认值
        """
        self._config = self._load_config()
        self.root_name = root_name or self._get_config('root_name', '项目名称')
        self.delimiters = self._get_config('delimiters', self.DEFAULT_DELIMITERS)
        self.column_mapping = self._get_config('column_mapping', self.DEFAULT_COLUMN_MAPPING)

    def _load_config(self) -> dict:
        """加载配置文件"""
        config_path = Path(__file__).parent / self.CONFIG_FILE
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _get_config(self, key: str, default):
        """
        获取配置项（优先级：环境变量 > 配置文件 > 默认值）
        """
        if key == 'root_name':
            env_value = os.environ.get('TAPD_ROOT_NAME')
            if env_value:
                return env_value

        if key in self._config:
            return self._config[key]

        return default

    def get_column(self, df, key):
        """获取映射的列名"""
        possible_names = self.column_mapping.get(key, [key])
        for name in possible_names:
            if name in df.columns:
                return name
        return None

    def convert_priority(self, priority_value):
        """
        将等级值统一转换为 P0/P1/P2 格式
        
        支持输入：
        - "高"/"中"/"低" → "P0"/"P1"/"P2"
        - "P0"/"P1"/"P2" → 保持不变
        - 其他值 → 原样返回
        """
        if not priority_value or pd.isna(priority_value):
            return ''
        
        priority_str = str(priority_value).strip()
        return self.PRIORITY_MAPPING.get(priority_str, priority_str)

    def parse_directory(self, directory_str):
        """
        解析用例目录字符串，提取层级结构
        
        示例：
        "行业大模型-S1-plugin-列表" → ['行业大模型-S1', 'plugin', '列表']
        "MCP-新增-正常新建MCP" → ['MCP', '新增', '正常新建MCP']
        """
        if not directory_str or pd.isna(directory_str):
            return [self.root_name, '未分类']

        directory_str = str(directory_str).strip()

        # 尝试用多种分隔符拆分
        parts = [directory_str]
        for delim in self.delimiters:
            new_parts = []
            for part in parts:
                new_parts.extend([p.strip() for p in part.split(delim) if p.strip()])
            parts = new_parts

        # 如果根节点不在开头，添加根节点
        if parts and not parts[0].startswith(self.root_name[:5]):
            parts.insert(0, self.root_name)

        return parts if parts else [self.root_name, '未分类']

    def convert_to_markdown(self, df, output_file):
        """
        转换为 Markdown 格式（XMind 支持直接导入）

        结构：
        # 项目名
        ## 项目名
        ### 一级模块
        #### 用例标题【P0】
        - **等级**: P0
        - **步骤**: ...
            - **预期**: ...
        """
        lines = [f"# {self.root_name}", ""]

        # 获取列名
        dir_col = self.get_column(df, '用例目录')
        title_col = self.get_column(df, '用例标题')
        steps_col = self.get_column(df, '步骤描述')
        expected_col = self.get_column(df, '预期结果')
        priority_col = self.get_column(df, '等级')

        # 记录已输出的模块路径，避免重复
        outputted_paths = set()

        # 按用例目录分组
        grouped = df.groupby(dir_col, sort=False)

        for directory, group in grouped:
            levels = self.parse_directory(directory)

            # 构建模块层级
            module_level1 = levels[1] if len(levels) > 1 else ''

            # 检查是否已输出过该一级模块
            if module_level1 and module_level1 not in outputted_paths:
                outputted_paths.add(module_level1)
                lines.append(f"## {self.root_name}")
                lines.append(f"### {module_level1}")
                lines.append("")

            # 添加用例
            for _, row in group.iterrows():
                case_title = str(row.get(title_col, '')).strip() if title_col else ''
                steps = str(row.get(steps_col, '')).strip() if steps_col else ''
                expected = str(row.get(expected_col, '')).strip() if expected_col else ''
                raw_priority = str(row.get(priority_col, '')).strip() if priority_col else ''
                
                # 转换等级为 P0/P1/P2 格式
                priority = self.convert_priority(raw_priority)

                if case_title:
                    # 在用例标题后加上优先级标记（不单独输出等级行）
                    if priority:
                        lines.append(f"#### {case_title} 【{priority}】")
                    else:
                        lines.append(f"#### {case_title}")
                    
                    # 标题后添加空行
                    lines.append("")

                    if steps:
                        steps_clean = steps.replace('\n', ' ')
                        lines.append(f"- **步骤**: {steps_clean}")
                    
                    if expected:
                        # 智能编号：如果预期结果包含编号（如 1、 2、），保留原样
                        # 否则自动添加 1. 前缀
                        expected_clean = expected.replace('\n', ' ')
                        # 检测是否已有编号
                        if not re.search(r'^\d+[、.．]', expected_clean):
                            expected_clean = f"1.{expected_clean}"
                        lines.append(f"    - **预期**: {expected_clean}")
                    
                    lines.append("")

        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return output_file

    def convert(self, input_file, output_dir=None, formats=None):
        """
        主转换方法

        Args:
            input_file: 统一格式 Excel 文件路径
            output_dir: 输出目录
            formats: 输出格式列表 ['markdown'] 或 'all'

        Returns:
            list: 生成的文件路径列表
        """
        input_path = Path(input_file)
        output_dir = Path(output_dir) if output_dir else input_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # 读取 Excel
        df = pd.read_excel(input_file, sheet_name=0)

        if df.empty:
            print(f"[ERROR] 文件为空: {input_file}")
            return []

        # 检查必要列（使用映射后的列名）
        dir_col = self.get_column(df, '用例目录')
        title_col = self.get_column(df, '用例标题')

        if not dir_col:
            print(f"[ERROR] 缺少必要列: 用例目录 或 所属模块")
            print(f"  当前列名: {list(df.columns)}")
            return []

        if not title_col:
            print(f"[ERROR] 缺少必要列: 用例标题 或 用例名称")
            print(f"  当前列名: {list(df.columns)}")
            return []

        # 确定输出格式
        if formats == 'all' or formats is None:
            formats = ['markdown']
        elif isinstance(formats, str):
            formats = [formats]

        output_files = []
        base_name = input_path.stem.replace('_统一格式', '').replace('_标准格式', '').replace('_TAPD格式', '')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Markdown 格式
        if 'markdown' in formats:
            md_file = output_dir / f"{base_name}_XMind_{timestamp}.md"
            self.convert_to_markdown(df, md_file)
            output_files.append(str(md_file))
            print(f"  [OK] Markdown: {md_file.name}")

        return output_files


def batch_convert(input_path, output_dir=None, formats='all', root_name=None):
    """批量转换"""
    converter = UnifiedToXmindConverter(root_name)

    input_path = Path(input_path)
    output_dir = Path(output_dir) if output_dir else (input_path.parent if input_path.is_file() else input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 获取文件列表
    if input_path.is_file():
        files = [input_path]
    else:
        files = list(input_path.glob('*.xlsx'))
        files = [f for f in files if 'XMind' not in f.name and not f.name.startswith('~$')]

    print(f"[开始] 找到 {len(files)} 个文件待转换\n")

    all_outputs = []
    for file in files:
        print(f"[处理] {file.name}")
        try:
            outputs = converter.convert(file, output_dir, formats)
            all_outputs.extend(outputs)
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
        print()

    print(f"[完成] 共生成 {len(all_outputs)} 个文件")
    return all_outputs


def main():
    parser = argparse.ArgumentParser(description='统一格式用例转换为 XMind 格式')
    parser.add_argument('--input', '-i', type=str, required=True, help='输入文件或目录')
    parser.add_argument('--output', '-o', type=str, default=None, help='输出目录')
    parser.add_argument('--format', '-f', type=str, default='all',
                       choices=['all', 'markdown'],
                       help='输出格式')
    parser.add_argument('--root', '-r', type=str, default=None,
                       help='根节点名称（默认从配置文件或环境变量 TAPD_ROOT_NAME 获取）')

    args = parser.parse_args()

    batch_convert(args.input, args.output, args.format, args.root)


if __name__ == '__main__':
    main()
