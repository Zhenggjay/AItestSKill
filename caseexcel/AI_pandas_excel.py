import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List
from xmindparser import xmind_to_dict
from icecream import ic

# ==============================================================================
# ### 用户配置区域 ###
# 您唯一需要修改的地方就是下面这一行。
# 请将引号内的示例路径，替换为您自己电脑上 XMind 文件的【完整路径】。
# 建议使用 r"..." 格式，这样可以避免 Windows 路径的反斜杠问题。
# ==============================================================================

# ==============================================================================


# --- 常量定义 ---
COLUMNS = [
    "分组", "标题", "关联需求", "所属标签", "用例说明",
    "前置条件", "类型", "步骤", "预期结果", "等级",
    "评估工时", "评审状态", "导入说明:"
]
DEFAULT_VALUES = {"前置条件": "网络正常", "类型": "文本", "等级": "P1"}


# --- 核心转换逻辑类 (无需修改) ---
class XmindToExcelConverter:
    """解析 XMind 文件，并将其内容转换为格式化的 Excel 电子表格。"""
    def __init__(self, xmind_path: str):
        self.xmind_path = Path(xmind_path)
        if not self.xmind_path.is_file():
            raise FileNotFoundError(f"错误：找不到文件，请检查 XMIND_FILE_PATH 的路径是否正确。\n路径: {self.xmind_path}")
        self._root = xmind_to_dict(str(self.xmind_path))[0]['topic']

    def _traverse_and_collect(self, topic: dict, path_str: str, collected_paths: list):
        current_path = f"{path_str}&{topic['title']}" if path_str else topic['title']
        if 'topics' in topic:
            for sub_topic in topic['topics']:
                self._traverse_and_collect(sub_topic, current_path, collected_paths)
        else:
            collected_paths.append(current_path.replace('\n', ''))

    def _extract_cases(self) -> List[List[str]]:
        collected_paths = []
        self._traverse_and_collect(self._root, "", collected_paths)
        return [path.split("&") for path in collected_paths]

    def _format_worksheet(self, writer: pd.ExcelWriter, dataframe: pd.DataFrame):
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        header_format = workbook.add_format({
            'bold': True, 'font_size': 12, 'font_name': '宋体', 'border': 1,
            'bg_color': '#FFD700', 'font_color': 'white', 'valign': 'vcenter', 'align': 'center'
        })
        cell_format = workbook.add_format({
            "font_name": "宋体", 'valign': 'vcenter', 'align': 'left',
            'font_size': 11, 'text_wrap': True
        })
        worksheet.write_row(0, 0, dataframe.columns, header_format)
        worksheet.set_column('A:F', 20)
        worksheet.set_column('G:I', 45)
        worksheet.set_column('J:M', 15)
        worksheet.set_row(0, 30)
        for i in range(len(dataframe)):
            worksheet.set_row(i + 1, 27, cell_format)

    def convert(self):
        raw_cases = self._extract_cases()
        excel_data = []
        for idx, parts in enumerate(raw_cases, 1):
            try:
                if len(parts) < 6:
                    raise ValueError(f"期望至少6个部分，但实际得到 {len(parts)} 个")
                row = [
                    f"{parts[0]}/{parts[1]}/{parts[2]}", parts[3], '', '', '',
                    DEFAULT_VALUES["前置条件"], DEFAULT_VALUES["类型"],
                    parts[4], parts[5], DEFAULT_VALUES["等级"], '', '', ''
                ]
                excel_data.append(row)
            except (IndexError, ValueError) as e:
                print(f"跳过格式错误的第 {idx} 行。原因: {e}。 数据: {parts}")
        df = pd.DataFrame(excel_data, columns=COLUMNS)
        timestamp = datetime.now().strftime('%Y%m%d')
        output_filename = f"{self.xmind_path.stem}_用例_{timestamp}.xlsx"
        output_path = self.xmind_path.parent / output_filename
        with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name='Sheet1', index=False, header=False, startrow=1)
            self._format_worksheet(writer, df)
        ic(f'成功生成 {len(df)} 条测试用例。')
        ic(f'文件已保存至: {output_path}')
        print("\n转换完成！Excel 文件已保存在与源文件相同的文件夹下。")


# --- 主程序入口 (无需修改) ---
def main(XMIND_FILE_PATH):
    """主函数，读取固定路径并执行转换。"""
    if "请在这里替换" in XMIND_FILE_PATH:
        print("错误：请先修改脚本顶部的 XMIND_FILE_PATH 变量，填入您要转换的XMind文件路径。")
        return

    try:
        converter = XmindToExcelConverter(XMIND_FILE_PATH)
        converter.convert()
    except Exception as e:
        ic(f"发生错误: {e}")
        print(f"\n处理失败，请检查错误信息。")


if __name__ == '__main__':
    XMIND_FILE_PATH = fr"D:\测试用例\智能体\鸿溟+智能体集成\行业大模型S3\智能体集成鸿溟平台S3_智能体平台.xmind"
    main(XMIND_FILE_PATH)