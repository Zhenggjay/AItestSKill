import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from xmindparser import xmind_to_dict
from icecream import ic
# ic.disable()  # 启用ic调试输出
import re
import argparse

# ==============================================================================
# ### 用户配置区域 ###
# 您唯一需要修改的地方就是下面这一行。
# 请将引号内的示例路径，替换为您自己电脑上 XMind 文件的【完整路径】。
# 建议使用 r"..." 格式，这样可以避免 Windows 路径的反斜杠问题。
# ==============================================================================

create_person = "郑国杰_801080"

# --- TAPD 格式列定义 ---
TAPD_COLUMNS = [
    "用例目录", "用例名称", "需求ID", "前置条件", "用例步骤",
    "预期结果", "用例类型", "用例状态", "用例等级", "创建人"
]

# --- 统一格式列定义（test_case_exporter.py 输出格式）---
UNIFIED_COLUMNS = [
    "用例目录", "用例标题", "等级", "前置条件",
    "步骤描述类型", "步骤描述", "预期结果", "标签", "关联需求"
]

DEFAULT_VALUES = {
    "前置条件": "网络正常",
    "用例类型": "功能测试",
    "用例等级": "P1",  # 直接使用P0/P1/P2格式
    "创建人": create_person,
    "用例状态": '正常'
}

# XMind 层级索引映射（提高可读性）
XMIND_INDICES = {
    'MODULE': 0,      # 模块
    'FEATURE': 1,     # 功能
    'SCENARIO': 2,    # 场景
    'CASE_NAME': 3,   # 用例名称
    'STEPS': 4,       # 用例步骤
    'EXPECTED': 5     # 预期结果
}

REQUIRED_PARTS = 6  # 最少需要的层级数

# 列宽配置（TAPD 格式）
TAPD_COLUMN_WIDTHS = {
    'A:F': 20,
    'G:I': 45,
    'J:M': 15
}

# 统一格式列宽配置
UNIFIED_COLUMN_WIDTHS = {
    'A': 22,
    'B': 35,
    'C': 10,
    'D': 30,
    'E': 14,
    'F': 55,
    'G': 55,
    'H': 15,
    'I': 15
}


# --- 核心转换逻辑类 ---
class XmindToExcelConverter:
    """解析 XMind 文件，并将其内容转换为格式化的 Excel 电子表格。"""
    
    def __init__(self, xmind_path: str):
        self.xmind_path = Path(xmind_path)
        if not self.xmind_path.is_file():
            raise FileNotFoundError(
                f"错误：找不到文件，请检查 XMIND_FILE_PATH 的路径是否正确。\n路径: {self.xmind_path}"
            )
        self._root = xmind_to_dict(str(self.xmind_path))[0]['topic']

    def _traverse_and_collect(self, topic: Dict[str, Any], path_str: str, collected_paths: List[str]) -> None:
        """递归遍历 XMind 节点，收集所有叶子节点的完整路径"""
        current_title = topic['title'].replace('\n', '')
        current_path = f"{path_str}&{current_title}" if path_str else current_title
        
        if 'topics' in topic:
            for sub_topic in topic['topics']:
                self._traverse_and_collect(sub_topic, current_path, collected_paths)
        else:
            collected_paths.append(current_path)

    def _extract_cases(self) -> List[List[str]]:
        """提取所有测试用例路径并分割为列表"""
        ic("开始提取用例路径")
        collected_paths = []
        self._traverse_and_collect(self._root, "", collected_paths)
        ic("收集到路径数量", len(collected_paths))
        
        result = [path.split("&") for path in collected_paths]
        ic("解析后的用例数据示例", result[0] if result else "无数据")
        return result

    def _format_worksheet(self, writer: pd.ExcelWriter, dataframe: pd.DataFrame) -> None:
        """格式化 Excel 工作表样式（TAPD格式）"""
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        
        # 表头格式
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'font_name': '宋体',
            'border': 1,
            'bg_color': '#FFD700',
            'font_color': 'white',
            'valign': 'vcenter',
            'align': 'center'
        })
        
        # 单元格格式
        cell_format = workbook.add_format({
            "font_name": "宋体",
            'valign': 'vcenter',
            'align': 'left',
            'font_size': 11,
            'text_wrap': True
        })
        
        # 写入表头
        worksheet.write_row(0, 0, dataframe.columns, header_format)
        
        # 设置列宽（使用TAPD格式的列宽配置）
        for col_idx, col_name in enumerate(dataframe.columns, 1):
            col_letter = chr(64 + col_idx)  # A, B, C...
            if col_name in TAPD_COLUMN_WIDTHS:
                worksheet.set_column(f'{col_letter}:{col_letter}', TAPD_COLUMN_WIDTHS[col_name])
        
        # 设置行高
        worksheet.set_row(0, 30)
        for i in range(len(dataframe)):
            worksheet.set_row(i + 1, 27, cell_format)

    def _detect_step_type(self, steps_text: str) -> str:
        """判断步骤描述类型：包含编号步骤返回'步骤'，否则返回'文本'"""
        if not steps_text:
            return "文本"
        if re.search(r'^\d+[、.\s]', steps_text, re.MULTILINE):
            return "步骤"
        return "文本"

    def _normalize_step_format(self, steps_text: str) -> str:
        """统一步骤编号格式：将 1. 1． 等统一为 1、"""
        if not steps_text:
            return ""
        return re.sub(r'(\d+)[.．]\s*', r'\1、', str(steps_text))

    def _convert_level_to_priority(self, level: str) -> str:
        """将等级（高/中/低）转换为优先级（P0/P1/P2）"""
        mapping = {'高': 'P0', '中': 'P1', '低': 'P2'}
        return mapping.get(str(level).strip(), 'P1')

    def _extract_priority_from_title(self, title: str) -> str:
        """
        从标题中提取优先级（【P0】、【P1】、【P2】）
        
        返回：
        - 如果标题包含【P0】、【P1】、【P2】，返回对应的优先级（P0/P1/P2）
        - 否则返回空字符串
        """
        if not title:
            return ''
        
        # 匹配【P0】、【P1】、【P2】格式
        match = re.search(r'【(P[012])】', str(title))
        if match:
            return match.group(1)
        return ''

    def _build_tapd_row(self, parts: List[str]) -> List[str]:
        """构建 TAPD 格式行数据（支持从标题中提取优先级）"""
        idx = XMIND_INDICES
        
        # 从标题中提取优先级（如果有的话）
        case_name = parts[idx['CASE_NAME']]
        extracted_priority = self._extract_priority_from_title(case_name)
        
        # 如果标题中包含【P0】、【P1】、【P2】，使用提取的优先级
        # 否则使用默认值并转换为P0/P1/P2格式
        if extracted_priority:
            use_level = extracted_priority
        else:
            raw_level = DEFAULT_VALUES["用例等级"]
            use_level = self._convert_level_to_priority(raw_level)
        
        # 构建目录：去掉根节点（MODULE），从FEATURE开始
        # parts结构: [根节点, 模块, 功能, 场景, 用例标题, 步骤, 预期结果]
        # 目录应包含：模块-功能-场景（即去掉根节点和最后两个元素）
        directory_parts = parts[1:-3] if len(parts) > 3 else parts[1:]
        directory = "-".join(directory_parts)
        
        ic("构建TAPD格式行", {
            "目录": directory,
            "名称": case_name,
            "等级": use_level,
            "从标题提取": bool(extracted_priority)
        })
        
        return [
            directory,  # 用例目录（已去掉根节点）
            case_name,                                    # 用例名称（保留【P0】等标记）
            '',                                          # 需求ID（空）
            DEFAULT_VALUES["前置条件"],                  # 前置条件
            parts[idx['STEPS']],                        # 用例步骤
            parts[idx['EXPECTED']],                     # 预期结果
            DEFAULT_VALUES["用例类型"],                  # 用例类型
            DEFAULT_VALUES["用例状态"],                  # 用例状态
            use_level,                                   # 用例等级（从标题提取或使用默认）
            DEFAULT_VALUES["创建人"],                    # 创建人
        ]

    def _build_unified_row(self, parts: List[str]) -> List[str]:
        """构建统一格式行数据（test_case_exporter.py 输出格式，支持从标题中提取优先级）"""
        idx = XMIND_INDICES
        raw_steps = parts[idx['STEPS']] if idx['STEPS'] < len(parts) else ""
        raw_expected = parts[idx['EXPECTED']] if idx['EXPECTED'] < len(parts) else ""
        
        # 统一步骤格式
        normalized_steps = self._normalize_step_format(raw_steps)
        step_type = self._detect_step_type(raw_steps)
        
        # 从标题中提取优先级（如果有的话）
        case_name = parts[idx['CASE_NAME']]
        extracted_priority = self._extract_priority_from_title(case_name)
        
        # 如果标题中包含【P0】、【P1】、【P2】，使用提取的优先级
        # 否则使用默认值并转换
        if extracted_priority:
            priority = extracted_priority
        else:
            raw_level = DEFAULT_VALUES["用例等级"]
            priority = self._convert_level_to_priority(raw_level)
        
        # 构建目录：去掉根节点（MODULE），从FEATURE开始
        directory_parts = parts[1:-3] if len(parts) > 3 else parts[1:]
        directory = "-".join(directory_parts)
        
        ic("构建统一格式行", {
            "目录": directory,
            "标题": case_name,
            "等级": priority,
            "步骤类型": step_type,
            "从标题提取": bool(extracted_priority)
        })
        
        return [
            directory,  # 用例目录（已去掉根节点）
            case_name,                                     # 用例标题（保留【P0】等标记）
            priority,                                      # 等级（从标题提取或使用默认）
            DEFAULT_VALUES["前置条件"],                    # 前置条件
            step_type,                                     # 步骤描述类型（步骤/文本）
            normalized_steps,                              # 步骤描述
            raw_expected,                                  # 预期结果
            '',                                            # 标签（空）
            '',                                            # 关联需求（空）
        ]

    def _format_worksheet_unified(self, output_path: str) -> None:
        """格式化统一格式工作表样式（使用 openpyxl）"""
        from openpyxl import load_workbook
        from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
        from openpyxl.utils import get_column_letter
        
        wb = load_workbook(output_path)
        ws = wb.active
        
        # 表头样式
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_font = Font(bold=True, size=11, color="FFFFFF")
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 设置表头
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        # 设置列宽（统一格式）
        for idx, col_name in enumerate(UNIFIED_COLUMNS, 1):
            col_letter = get_column_letter(idx)
            if col_name in UNIFIED_COLUMN_WIDTHS:
                ws.column_dimensions[col_letter].width = UNIFIED_COLUMN_WIDTHS[col_name]
        
        # 设置数据行样式
        priority_colors = {'P0': 'FF6B6B', 'P1': 'FFA94D', 'P2': '69DB7C'}
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            for idx, cell in enumerate(row, 1):
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
                
                # 等级列居中并着色
                if idx == 3:  # 等级列是第3列
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                    if cell.value in priority_colors:
                        cell.fill = PatternFill(start_color=priority_colors[cell.value], 
                                              end_color=priority_colors[cell.value], 
                                              fill_type='solid')
        
        # 设置行高
        ws.row_dimensions[1].height = 25
        for row_num in range(2, ws.max_row + 1):
            ws.row_dimensions[row_num].height = 50
        
        wb.save(output_path)
        
    def convert(self, output_format: str = "tapd") -> List[str]:
        """执行转换流程：解析 XMind -> 生成 DataFrame -> 导出 Excel
        
        Args:
            output_format: 输出格式，"tapd"、"unified" 或 "both"
        
        Returns:
            List[str]: 生成的文件路径列表
        """
        ic("开始转换流程", output_format)
        
        raw_cases = self._extract_cases()
        ic("原始用例数量", len(raw_cases))
        
        # 根据格式决定需要构建的行类型
        formats_to_generate = []
        if output_format == "both":
            formats_to_generate = ["tapd", "unified"]
        else:
            formats_to_generate = [output_format]
        
        ic("将生成的格式", formats_to_generate)
        
        # 一次性构建所有格式的数据（避免重复解析）
        all_format_data = {fmt: [] for fmt in formats_to_generate}
        skipped_count = 0
        
        for idx, parts in enumerate(raw_cases, 1):
            try:
                if len(parts) < REQUIRED_PARTS:
                    raise ValueError(
                        f"期望至少 {REQUIRED_PARTS} 个层级，但实际得到 {len(parts)} 个"
                    )
                
                # 为每个格式构建行数据
                for fmt in formats_to_generate:
                    if fmt == "unified":
                        row = self._build_unified_row(parts)
                    else:
                        row = self._build_tapd_row(parts)
                    all_format_data[fmt].append(row)
                    
            except (IndexError, ValueError) as e:
                ic("跳过格式错误", idx, str(e), parts)
                print(f"[WARN] 跳过格式错误的第 {idx} 行。原因: {e}。数据: {parts}")
                skipped_count += 1
        
        ic("成功转换数量", len(all_format_data[formats_to_generate[0]]))
        ic("跳过数量", skipped_count)
        
        # 生成时间戳（所有格式使用同一时间戳）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_files = []
        
        # 为每个格式生成 Excel 文件
        for fmt in formats_to_generate:
            # 去掉文件名中的"_智能体平台"（如果存在）
            base_name = re.sub(r'_智能体平台', '', self.xmind_path.stem)
            
            if fmt == "unified":
                columns = UNIFIED_COLUMNS
                format_name = "TAPD用例"  # 统一格式对应TAPD用例文件名
                output_filename = f"{base_name}_TAPD用例_{timestamp}.xlsx"
            else:
                columns = TAPD_COLUMNS
                format_name = "普通用例"  # TAPD格式对应普通用例文件名
                output_filename = f"{base_name}_普通用例_{timestamp}.xlsx"
            
            output_path = self.xmind_path.parent / output_filename
            ic("输出列定义", columns)
            ic("输出文件路径", output_path)
            
            # 创建 DataFrame
            df = pd.DataFrame(all_format_data[fmt], columns=columns)
            ic("DataFrame 形状", df.shape)
            
            # 写入 Excel
            if fmt == "unified":
                # 统一格式使用 openpyxl 以支持样式美化
                with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                    df.to_excel(writer, sheet_name='测试用例', index=False)
                self._format_worksheet_unified(output_path)
            else:
                # TAPD 格式使用 xlsxwriter
                with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
                    df.to_excel(writer, sheet_name='Sheet1', index=False, header=False, startrow=1)
                    self._format_worksheet(writer, df)
            
            output_files.append(str(output_path))
            
            # 输出结果
            ic("转换完成", len(df), format_name)
            print(f'[OK] 成功生成 {len(df)} 条测试用例（{format_name}）')
            if skipped_count > 0:
                print(f'[WARN] 跳过 {skipped_count} 条格式错误的数据')
            print(f'[FILE] 文件已保存至: {output_path}')
        
        print(f"\n[OK] 全部转换完成！共生成 {len(output_files)} 个文件")
        return output_files


# --- 主程序入口 ---
def main(xmind_file_path: str, output_format: str = "tapd") -> List[str]:
    """主函数，读取固定路径并执行转换。
    
    Args:
        xmind_file_path: XMind 文件路径
        output_format: 输出格式，"tapd"、"unified" 或 "both"
    
    Returns:
        List[str]: 生成的文件路径列表
    """
    ic("主函数启动", xmind_file_path, output_format)
    
    if "请在这里替换" in xmind_file_path:
        print("❌ 错误：请先修改脚本顶部的 XMIND_FILE_PATH 变量，填入您要转换的XMind文件路径。")
        return []
    
    try:
        converter = XmindToExcelConverter(xmind_file_path)
        ic("转换器初始化成功")
        output_files = converter.convert(output_format)
        ic("转换流程完成", "生成文件数", len(output_files))
        return output_files
    except FileNotFoundError as e:
        ic("文件未找到错误", str(e))
        print(f"[ERROR] 文件未找到: {e}")
        return []
    except Exception as e:
        ic("发生异常", type(e).__name__, str(e))
        print(f"[ERROR] 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == '__main__':
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='XMind 转 Excel（支持 TAPD 格式、统一格式或同时生成）')
    parser.add_argument('--input', '-i', type=str, help='XMind 文件路径')
    parser.add_argument('--format', '-f', type=str, 
                        choices=['tapd', 'unified', 'both'], default='tapd',
                        help='输出格式：tapd（默认）、unified（统一格式）或 both（同时生成两种格式）')
    
    args = parser.parse_args()
    
    # 如果命令行没有提供文件路径，使用默认路径
    if args.input:
        XMIND_FILE_PATH = args.input
    else:
        XMIND_FILE_PATH = fr"D:\测试用例\智能体\鸿溟+智能体集成\行业大模型S3\智能体集成鸿溟平台S3_智能体平台.xmind"
    
    output_files = main(XMIND_FILE_PATH, args.format)
    
    # 输出生成文件的汇总
    if output_files:
        print(f"\n[FILE] 生成的文件：")
        for file_path in output_files:
            print(f"   - {file_path}")