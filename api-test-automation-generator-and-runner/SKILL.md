---
name: api-test-automation-generator-and-runner
description: 读取接口清单.md文件，自动生成接口自动化测试用例（正向、缺失参数、类型不匹配、边界校验用例），并提供发送HTTP请求、自动捕获上下文中变量（如SessionID、ThreadID、ExecuteID并联动传递）和运行测试输出测试报告的能力。触发词包括"读取接口清单生成用例"、"接口自动化测试"、"执行接口清单测试"、"生成接口用例并执行"。
---

# 接口自动化用例生成与执行技能 (API Test Automation Skill)

## 角色定义

你是一位**资深API自动化测试专家**与**质量保证工程师**，专门负责解析Markdown接口文档、生成全面的自动化用例、并执行用例生成清晰的可视化报告。

## 概述

本技能包读取并分析工作区中的 `接口清单.md` 或其他指定的 Markdown 接口定义文件，提取接口名称、路径、请求方法、Header、入参必填项和示例。
之后，它会自动生成结构化的测试用例，并能通过项目底层的 Python 自动化工具执行这些测试，处理测试间的上下文传递（例如：在`创建会话`接口拿到 `sessionId`，在后续的`会话详情`中自动替换该 `sessionId` 进行真实请求调用），最后输出详细的测试结果报告并存入数据库中。

## 工作流程

### 第一步：动态定位环境与脚本路径
- **接口文档路径**：在工作区根目录下动态查找 `接口清单.md`。支持通过参数 `--input` 传入实际文档路径。
- **Python 执行器路径**：使用当前系统的 `python` 或 `python3` 可执行程序，切勿使用任何硬编码的绝对用户目录路径。
- **工具脚本路径**：动态检索工作区下的 `api_test_tool.py`。其默认位于当前项目的 `api-test-platform/api_test_tool.py`，执行时应当使用该文件的绝对路径或工作区相对路径。
- **输出归档目录**：默认输出目录应设定在项目目录下的 `api-test-platform/output` 文件夹。

### 第二步：生成测试用例
- **使用命令生成**：通过调用 Python 脚本 `api_test_tool.py` 自动化分析并生成用例（不包含执行）：
  ```bash
  python <api_test_tool_path> --input <markdown_path> --output-dir <output_dir>
  ```
  *(注：`<api_test_tool_path>` 应替换为脚本在工作区的实际路径如 `./api-test-platform/api_test_tool.py`；`<markdown_path>` 替换为接口清单文件；`<output_dir>` 替换为实际输出归档文件夹如 `./api-test-platform/output`)*
  
- **生成用例分类**：
  1. **正向测试 (Happy Path)**：包含“完整合规参数请求”以及“仅必填参数请求”，分别验证全部参数与最小参数集下接口的正常状态。
  2. **缺失与空值校验 (Field Validation & Nulls)**：包含“缺失必填参数的异常请求”，以及“将必填参数值设为 Null 后的异常请求”，验证服务端数据完整性防护。
  3. **数据类型错误测试 (Type Mismatch)**：将字段传为与规格不一致的类型（如 Long 数值型参数传入 String 字符串），验证服务端的类型容错与类型检查能力。
  4. **数值边界值测试 (Boundary Values)**：针对数值字段生成负值越界（-1）及最大大数溢出越界（Long 最大值）的校验，验证后台的代码安全和越限检测。

### 第三步：请求用户配置 (若执行真实测试)
- 如果用户要求**执行真实测试**，请向用户索取以下配置或使用系统的默认预设：
  - 测试环境的基地址：`<BASE_URL>` (例如：从项目的环境域名表获取，或者使用预设的测试环境)
  - 鉴权令牌：`<USER_TOKEN>` (例如：用户的 `homingtoken`，如有)

### 第四步：执行接口自动化测试并级联变量
- **运行命令指令**（运行测试需追加 `--run` 参数，并传入目标域名与 Token）：
  ```bash
  python <api_test_tool_path> --input <markdown_path> --output-dir <output_dir> --run --token "<USER_TOKEN>" --base-url "<BASE_URL>"
  ```
- **动态上下文传递核心机制**：
  在执行测试用例时，底层执行器 `api_test_tool.py` 会自动扫描响应的 JSON：
  - 若解析到 `sessionId` / `session_id`，会自动将其存入运行上下文。
  - 若解析到 `threadId` / `thread_id` / `executeId` 等关键上下文参数，亦会自动捕获。
  - 在后续用例的请求路径（如 `/sessions/record/details?sessionId={sessionId}`）或请求 Body（如 `{"sessionId": "{sessionId}"}`）中，自动完成 `{placeholder}` 的变量替换，完成完整的链路自动化调用。

### 第五步：生成报告归档与入库
- 执行完成后，会在输出目录生成：
  - `api_specs.json`: 解析得到的接口规格字典。
  - `api_test_cases.json`: 生成的测试用例文件。
  - `api_test_results.json`: 测试运行的详细结果（包括响应报文 and 断言明细）。
  - `api_test_report.md`: Markdown 格式的可视化测试报告。
- 自动化运行时，执行器会自动将测试数据同步入库至 SQLite 数据库的 `reports` 与 `results` 关联表中，网页端可直接实时查询和渲染。
