# Tencent CoDesign Skills

从腾讯 CoDesign 设计稿/原型中提取数据、截图和克隆页面。

## 技能列表

### clone-codesign-page（主技能）

从 CoDesign 原型中提取截图、文本、设计令牌、DOM骨架。

**位置**: `clone-codesign-page/`

**核心功能**:
- `section` 命令：提取指定目录路径下所有页面（推荐）
- `quick` 命令：快速截图 + 元信息 + 设计令牌 + DOM骨架
- `styles` 命令：指定区域完整样式采集
- icon class 精确区分文件夹/页面
- 路径表达式定位（`目录名/子目录名`）
- 自适应缩放截图（1张截图装下全部内容）
- 文件夹节点也截图
- 无头模式 + 系统 Chrome

**使用方法**:
```bash
# 提取指定目录下所有页面
node clone-codesign-page/scripts/clone.mjs <URL> section --section <目录名>/<子目录名> -o ./output

# 仅列出目录结构
node clone-codesign-page/scripts/clone.mjs <URL> section --list-only

# 快速模式（截图+骨架）
node clone-codesign-page/scripts/clone.mjs <URL> quick -o ./output
```

**输出结构**:
```
output/
├── sitemap.json                    # 页面树结构
└── <目录名>_<子目录名>/
    ├── <页面名>/
    │   ├── screenshot.png           # 自适应缩放截图
    │   ├── content.md               # iframe内部文本
    │   ├── skeleton.json            # DOM骨架树
    │   └── theme.json               # 设计令牌
    └── ...
```

## 安装依赖

首次运行自动安装 Playwright（优先使用系统 Chrome，不需要单独安装 Chromium）。

**手动安装**（如果自动安装失败）:
```bash
cd %USERPROFILE%\.cache\codesign-extractor
npm install playwright
```

## CoDesign 特殊处理

### 需要登录的页面

```bash
# 方法1: 无头模式（推荐，不需要手动启动浏览器）
node clone-codesign-page/scripts/clone.mjs <URL> section --section <目录名>

# 方法2: 连接已登录的 Chrome
start chrome --remote-debugging-port=9222
node clone-codesign-page/scripts/clone.mjs <URL> section --section <目录名> --connect-cdp http://localhost:9222

# 方法3: 显示浏览器窗口手动登录
node clone-codesign-page/scripts/clone.mjs <URL> section --section <目录名> --no-headless
```

## 文件清单

```
Codesign-Skills/
├── README.md                           # 本文件
└── clone-codesign-page/
    ├── SKILL.md                        # 技能描述（URL自动触发）
    └── scripts/
        └── clone.mjs                   # 核心脚本（section/quick/styles命令）
```
