# -*- coding: utf-8 -*-
"""
Excel测试用例批量转换工具

功能：将旧格式Excel测试用例转换为新格式（截图格式）
新格式列: 用例目录, 用例标题, 等级, 前置条件, 步骤描述类型, 步骤描述, 预期结果, 标签, 关联需求

用法:
    python excel_to_tapd.py --input <文件或目录路径> [--output <输出目录>] [--module <模块名>]
"""

from __future__ import annotations

import re
import sys
import argparse
import logging
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量定义
# ---------------------------------------------------------------------------

NEW_FORMAT_COLUMNS: list[str] = [
    "用例目录", "用例标题", "等级", "前置条件",
    "步骤描述类型", "步骤描述", "预期结果", "标签", "关联需求",
]

NEW_COLUMN_WIDTHS: dict[str, int] = {
    "用例目录": 25,
    "用例标题": 35,
    "等级": 10,
    "前置条件": 30,
    "步骤描述类型": 12,
    "步骤描述": 50,
    "预期结果": 50,
    "标签": 15,
    "关联需求": 15,
}

# 旧等级 → 新等级映射
LEVEL_MAPPING: dict[str, str] = {
    "高": "P0", "中": "P1", "低": "P2",
    "P0": "P0", "P1": "P1", "P2": "P2",
}

LEVEL_COLORS: dict[str, str] = {
    "P0": "FF6B6B",
    "P1": "FFA94D",
    "P2": "69DB7C",
}

# 默认值
DEFAULT_LEVEL = "P1"
DEFAULT_TITLE = "未命名用例"
DEFAULT_STEP_TYPE = "文本"
DEFAULT_NA_STR = "nan"

# ---------------------------------------------------------------------------
# Excel 样式预设（懒初始化）
# ---------------------------------------------------------------------------

class ExcelStyles:
    """Excel 样式单例"""
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, size=11, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def safe_str(value: Any, default: str = "") -> str:
    """安全地将值转为字符串，处理 pandas NaN 和 None"""
    if pd.isna(value):
        return default
    result = str(value).strip()
    return "" if result.lower() == DEFAULT_NA_STR else result


def remove_numbering(text: str) -> str:
    """去掉行首序号（如 1. / 1、/ 1)）"""
    return re.sub(r"^\d+[、.\s\)]+", "", text).strip()


def _split_into_lines(text: str) -> list[str]:
    """按换行或分号智能分割文本块"""
    if "\n" in text:
        return [l.strip() for l in text.split("\n") if l.strip()]
    for delimiter in ("；", ";"):
        if delimiter in text:
            return [l.strip() for l in text.split(delimiter) if l.strip()]
    return [text]


def _split_steps_by_numbering(raw_line: str) -> list[str]:
    """将同一行内多个步骤拆开（如 '1. xxx 2. yyy'），排除括号内数字"""
    return [
        part.strip()
        for part in re.split(r"(?<![\w(])(?=\d+[.、)])", raw_line)
        if part.strip()
    ]


def add_numbering_to_lines(lines: list[str]) -> str:
    """给行列表逐行加序号 1. 2. 3. → 返回换行字符串"""
    numbered = []
    for i, line in enumerate(lines, 1):
        numbered.append(f"{i}. {remove_numbering(line)}")
    return "\n".join(numbered)


# ---------------------------------------------------------------------------
# 等级处理
# ---------------------------------------------------------------------------

def convert_level(old_level: Any) -> str:
    """高/中/低 → P0/P1/P2，未知值回退为 DEFAULT_LEVEL"""
    raw = safe_str(old_level)
    return LEVEL_MAPPING.get(raw, DEFAULT_LEVEL)


# ---------------------------------------------------------------------------
# 步骤/预期文本规范化
# ---------------------------------------------------------------------------

def normalize_step_format(steps_text: Any) -> str:
    """对步骤文本逐行加序号，智能拆分同行多步骤，排除括号内数字"""
    text = safe_str(steps_text)
    if not text:
        return ""

    # 按换行分割后再拆分行内多步骤
    lines: list[str] = []
    for raw in text.split("\n"):
        raw = raw.strip()
        if not raw:
            continue
        lines.extend(_split_steps_by_numbering(raw))

    return add_numbering_to_lines(lines)


def normalize_expected_result(expected_text: Any) -> str:
    """对预期结果逐行加序号，支持换行/分号/中文分号分割"""
    text = safe_str(expected_text)
    if not text:
        return ""
    lines = _split_into_lines(text)
    return add_numbering_to_lines(lines)


def detect_step_type(steps_text: Any) -> str:
    """判断步骤描述类型（步骤/文本）"""
    text = safe_str(steps_text)
    if re.search(r"^\d+[、.\s]", text, re.MULTILINE):
        return "步骤"
    return DEFAULT_STEP_TYPE


def extract_title_from_steps(steps_text: Any) -> str:
    """从步骤文本第一行提取用例标题"""
    text = safe_str(steps_text)
    if not text:
        return DEFAULT_TITLE
    first_line = text.split("\n")[0]
    cleaned = remove_numbering(first_line)
    cleaned = re.split(r"预期[:：]", cleaned)[0].strip()
    return cleaned if cleaned else DEFAULT_TITLE


# ---------------------------------------------------------------------------
# 列名自动检测
# ---------------------------------------------------------------------------

_COLUMN_RULES: list[tuple[str, list[str]]] = [
    ("用例标题", ["标题", "用例名称", "name"]),
    ("用例目录", ["模块", "目录", "category"]),
    ("等级", ["优先级", "等级", "priority"]),
    ("前置条件", ["前置", "precondition"]),
    ("步骤描述", ["步骤", "step"]),  # 需排除"预期"
    ("预期结果", ["预期", "expected"]),
    ("关联需求", ["编号", "需求id"]),
    ("标签", ["标签", "tag"]),
]


def detect_column_mapping(df_columns: pd.Index) -> dict[str, str]:
    """根据列名关键词自动检测原文件列名到新格式列的映射"""
    mapping: dict[str, str] = {}
    cols = [str(c).strip() for c in df_columns]

    for col in cols:
        col_lower = col.lower()

        for target, keywords in _COLUMN_RULES:
            if target in mapping:
                continue  # 已匹配过

            # 步骤描述需要排除"预期结果"
            if target == "步骤描述" and "预期" in col:
                continue

            if any(kw in col_lower or kw in col for kw in keywords):
                mapping[target] = col
                break

    return mapping


# ---------------------------------------------------------------------------
# 单行转换数据类
# ---------------------------------------------------------------------------

@dataclass
class ConvertedRow:
    """转换后的一行测试用例"""
    module: str = ""
    title: str = ""
    level: str = DEFAULT_LEVEL
    precondition: str = ""
    step_type: str = DEFAULT_STEP_TYPE
    steps: str = ""
    expected: str = ""
    tags: str = ""
    related_requirement: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "用例目录": self.module,
            "用例标题": self.title,
            "等级": self.level,
            "前置条件": self.precondition,
            "步骤描述类型": self.step_type,
            "步骤描述": self.steps,
            "预期结果": self.expected,
            "标签": self.tags,
            "关联需求": self.related_requirement,
        }


# ---------------------------------------------------------------------------
# 核心转换逻辑
# ---------------------------------------------------------------------------

def _convert_row(row: pd.Series, mapping: dict[str, str], module_name: str) -> ConvertedRow:
    """将一行旧格式数据转换为新格式"""
    result = ConvertedRow()

    # 用例目录
    result.module = safe_str(row.get(mapping.get("用例目录", "")))
    if not result.module:
        result.module = module_name

    # 用例标题
    title_col = mapping.get("用例标题")
    if title_col and pd.notna(row.get(title_col)):
        result.title = str(row.get(title_col)).strip()
    else:
        steps_col = mapping.get("步骤描述")
        steps_text = row.get(steps_col) if steps_col else ""
        result.title = extract_title_from_steps(steps_text)

    # 等级
    level_col = mapping.get("等级")
    result.level = convert_level(row.get(level_col)) if level_col else DEFAULT_LEVEL

    # 前置条件
    precondition_col = mapping.get("前置条件")
    result.precondition = safe_str(row.get(precondition_col)) if precondition_col else ""

    # 步骤描述
    steps_col = mapping.get("步骤描述")
    if steps_col:
        raw = row.get(steps_col)
        result.steps = normalize_step_format(raw)
        result.step_type = detect_step_type(raw)

    # 预期结果
    expected_col = mapping.get("预期结果")
    if expected_col:
        result.expected = normalize_expected_result(row.get(expected_col))

    # 关联需求
    req_col = mapping.get("关联需求")
    if req_col:
        result.related_requirement = safe_str(row.get(req_col))

    # 标签
    tag_col = mapping.get("标签")
    if tag_col:
        result.tags = safe_str(row.get(tag_col))

    return result


def convert_excel_to_new_format(
    input_file: Path,
    output_dir: Path,
    module_name: str = "",
) -> str | None:
    """读取 Excel → 转换为新格式 → 写入新 Excel"""
    logger.info("[处理] %s", input_file.name)

    df = pd.read_excel(input_file, sheet_name=0)
    if df.empty:
        logger.info("  [跳过] 文件为空")
        return None

    mapping = detect_column_mapping(df.columns)
    logger.info("  [列映射] %s", mapping)

    records = [_convert_row(row, mapping, module_name) for _, row in df.iterrows()]

    # 写入新格式 Excel
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{input_file.stem}_{timestamp}.xlsx"

    df_new = pd.DataFrame([r.to_dict() for r in records], columns=NEW_FORMAT_COLUMNS)
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df_new.to_excel(writer, sheet_name="测试用例", index=False)

    beautify_excel(output_file)

    logger.info("  [OK] 已导出: %s (%d 条用例)", output_file.name, len(records))
    return str(output_file)


# ---------------------------------------------------------------------------
# Excel 美化
# ---------------------------------------------------------------------------

def _apply_level_column_style(ws: Worksheet, headers: list[Any]) -> int | None:
    """返回等级列索引（从1开始），找不到返回 None"""
    try:
        return headers.index("等级") + 1
    except ValueError:
        return None


def _style_header_row(ws: Worksheet) -> None:
    """设置表头样式"""
    for cell in ws[1]:
        cell.font = ExcelStyles.header_font
        cell.fill = ExcelStyles.header_fill
        cell.border = ExcelStyles.thin_border
        cell.alignment = ExcelStyles.center_align


def _style_data_rows(ws: Worksheet, level_col_idx: int | None) -> None:
    """设置数据行样式，等级列着色"""
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for idx, cell in enumerate(row, 1):
            cell.border = ExcelStyles.thin_border

            if level_col_idx is not None and idx == level_col_idx:
                cell.alignment = ExcelStyles.center_align
                if cell.value in LEVEL_COLORS:
                    cell.fill = PatternFill(
                        start_color=LEVEL_COLORS[cell.value],
                        end_color=LEVEL_COLORS[cell.value],
                        fill_type="solid",
                    )
            else:
                cell.alignment = ExcelStyles.left_align


def _set_column_widths(ws: Worksheet) -> None:
    """按预设列宽配置"""
    for idx, col_name in enumerate(NEW_FORMAT_COLUMNS, 1):
        col_letter = ws.cell(row=1, column=idx).column_letter
        if col_name in NEW_COLUMN_WIDTHS:
            ws.column_dimensions[col_letter].width = NEW_COLUMN_WIDTHS[col_name]


def _set_row_heights(ws: Worksheet) -> None:
    """设置行高"""
    ws.row_dimensions[1].height = 25
    for row_num in range(2, ws.max_row + 1):
        ws.row_dimensions[row_num].height = 50


def beautify_excel(file_path: Path | str) -> None:
    """美化新生成的 Excel 样式"""
    wb = load_workbook(file_path)
    ws = wb.active

    _set_column_widths(ws)
    _style_header_row(ws)

    headers = [cell.value for cell in ws[1]]
    level_col_idx = _apply_level_column_style(ws, headers)
    _style_data_rows(ws, level_col_idx)
    _set_row_heights(ws)

    wb.save(file_path)


# ---------------------------------------------------------------------------
# 文件收集
# ---------------------------------------------------------------------------

def _collect_excel_files(input_path: Path) -> list[Path]:
    """收集待处理的 Excel 文件"""
    if input_path.is_file():
        return [input_path]
    return [
        f for f in input_path.glob("*.xlsx")
        if not f.name.startswith("~$")
    ]


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Excel测试用例转换为新格式（截图格式）")
    parser.add_argument("--input", "-i", type=str, required=True, help="输入文件或目录路径")
    parser.add_argument("--output", "-o", type=str, default=None, help="输出目录（默认与输入同目录）")
    parser.add_argument("--module", "-m", type=str, default="", help="用例目录/模块名称（可选）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """主入口"""
    args = parse_args(argv)

    input_path = Path(args.input)
    output_dir = Path(args.output) if args.output else (
        input_path.parent if input_path.is_file() else input_path
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    files = _collect_excel_files(input_path)
    if not files:
        logger.error("[ERROR] 未找到可处理的Excel文件")
        sys.exit(1)

    logger.info("[开始] 找到 %d 个文件待处理\n", len(files))

    success_count = 0
    for f in files:
        try:
            result = convert_excel_to_new_format(f, output_dir, args.module)
            if result:
                success_count += 1
        except Exception:
            logger.exception("  [ERROR] 处理失败: %s", f.name)

    logger.info("\n[完成] 成功转换 %d/%d 个文件", success_count, len(files))


if __name__ == "__main__":
    main()
