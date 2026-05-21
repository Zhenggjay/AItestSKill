# Tencent CoDesign Skills Package

一套用于提取、克隆和生成腾讯 CoDesign 设计稿的技能包。

## 技能列表

### 1. extract-codesign-data

从 CoDesign 原型/设计稿中提取结构化数据（截图、设计令牌、组件树、标注等）。

**位置**: `extract-codesign-data/`

**核心功能**:
- 📸 页面截图（全页或指定区域）
- 🎨 设计令牌提取（颜色、字体、间距、圆角等）
- 📝 页面文本提取（Markdown 格式）
- 🔗 交互元素收集
- 📦 完整数据包导出

**使用方法**:
```bash
# 基础提取（截图 + 设计令牌）
node extract-codesign-data/scripts/extract.mjs <CODESIGN_URL> --all

# 高级提取（追加组件数据、标注、文本）
node extract-codesign-data/scripts/extract.mjs <CODESIGN_URL> --all --advanced

# 使用 CoDesign API（需要 token）
set CODESIGN_TOKEN=your_token
node extract-codesign-data/scripts/extract.mjs <PROJECT_ID> --all --use-api

# 连接已登录的 Chrome（处理需要登录的原型）
start chrome --remote-debugging-port=9222
node extract-codesign-data/scripts/extract.mjs <URL> --all --connect-cdp http://localhost:9222
```

**输出结构**:
```
codesign-export/
├── sitemap.json           # 页面树
├── meta.json              # 项目元信息
└── pages/{pageName}/
    ├── screenshot.png      # 页面截图
    ├── theme.json          # 设计令牌
    ├── data.json           # 页面数据 (--advanced)
    ├── notes.json          # 组件标注 (--advanced)
    └── content.md         # 页面文本 (--advanced)
```

---

### 2. clone-codesign-page

高精度克隆 CoDesign 页面，使用渐进式采集策略。

**位置**: `clone-codesign-page/`

**核心功能**:
- 🚀 快速还原模式（截图 + 设计令牌 + DOM 骨架）
- 🎨 高精度还原模式（追加指定区域样式、交互态、响应式截图）
- 📐 渐进式采集（分阶段，数据增量追加）
- 🔄 支持交互态采集（hover/click）
- 📱 多视口截图（desktop/tablet/mobile）

**使用方法**:
```bash
# 快速模式（推荐先用这个）
node clone-codesign-page/scripts/clone.mjs <CODESIGN_URL> quick -o ./clone-data --scroll

# 高精度模式（在快速模式基础上）
node clone-codesign-page/scripts/clone.mjs <URL> styles -o ./clone-data --selector "header"
node clone-codesign-page/scripts/clone.mjs <URL> responsive -o ./clone-data
node clone-codesign-page/scripts/clone.mjs <URL> assets -o ./clone-data

# 全量模式
node clone-codesign-page/scripts/clone.mjs <URL> full -o ./clone-data
```

**采集命令**:
| 命令 | 用途 | 产出 |
|------|------|------|
| `quick` | 快速模式 = init + skeleton | screenshot + meta + theme + skeleton |
| `full` | 全量模式 | 上述 + 响应式截图 + 资源 |
| `init` | 截图 + 元信息 + 设计令牌 | screenshot.png, meta.json, theme.json |
| `skeleton` | DOM 骨架（不含样式） | skeleton.json |
| `styles --selector "X"` | 指定区域的完整样式 | sections/X/nodes.json + styles.json |
| `interact` | 交互态截图 | interactions/*.png |
| `responsive` | 多 viewport 截图 | responsive/*.png |
| `assets` | 下载图片/字体 | assets/ |

**输出结构**:
```
clone-data/
├── meta.json              # 元信息
├── screenshot.png         # 全页截图
├── theme.json             # 设计令牌
├── skeleton.json          # DOM 骨架树
├── sections/              # 按 section 的样式
│   └── header/
│       ├── nodes.json     # DOM + selector
│       ├── styles.json    # computedStyle
│       └── screenshot.png
├── interactions/           # 交互态数据
├── responsive/             # 多视口截图
└── assets/                 # 下载的资源
```

---

### 3. generate-codesign-theme

从 CoDesign 设计稿中生成设计规范文档（DESIGN.md）和 Tailwind CSS 主题文件（globals.css）。

**位置**: `generate-codesign-theme/`

**核心功能**:
- 📊 生成 DESIGN.md（Google Stitch 格式，面向 AI 和人类双重可读）
- 🎨 生成 globals.css（Tailwind CSS v4 主题定义）
- 📸 强调截图分析的重要性（CoDesign Canvas 渲染时，截图是唯一真相）
- 🔍 每个 token 类别均有推荐/允许/禁止三级规范
- 📝 可直接放入项目根目录供 AI 编码工具使用

**使用方法**:
```bash
# Step 1: 采集设计数据
node extract-codesign-data/scripts/extract.mjs <CODESIGN_URL> --theme --screenshot -o ./theme-data

# 或使用 API 模式（推荐，数据更精确）
set CODESIGN_TOKEN=your_token
node extract-codesign-data/scripts/extract.mjs <PROJECT_ID> --all --use-api -o ./theme-data

# Step 2: 人工分析截图（最关键的一步）
# 打开 theme-data/screenshot.png，观察：
# - 品牌调性（极简/科技/温暖/高端/活泼）
# - 色彩氛围（亮色系/暗色系）
# - 布局风格（宽松留白/紧凑密集）
# - 组件风格（按钮形状、卡片样式等）

# Step 3: 分析 theme.json
cat theme-data/theme.json

# Step 4: 生成 DESIGN.md 和 globals.css
# （此步骤当前需要人工完成，未来将自动化）
```

**生成产物**:
```
<output>/
├── DESIGN.md            # 设计规范文档
├── globals.css          # Tailwind CSS v4 主题定义
└── screenshots/         # 视觉参考截图
    ├── full-page.png    # 全页截图
    ├── desktop.png      # 桌面视图
    └── mobile.png       # 手机视图
```

**DESIGN.md 包含章节**:
- 视觉风格
- 设计原则
- 色彩系统（基础色板 + 色彩规范）
- 字体系统（字体家族 + 文字样式 + 字体规范）
- 间距系统（间距标尺 + 间距规范）
- 圆角系统（圆角值 + 圆角规范）
- 阴影系统（阴影值 + 阴影规范）
- 动画 & 过渡（过渡 + 动画 + 规范）
- 布局（容器宽度 + 布局规范）
- 组件规范（Button, Card, Input 等）
- 使用约束（推荐/禁止）

---

## 安装依赖

所有技能首次运行时会自动安装 Playwright + Chromium（约 1-2 分钟）。

**手动安装**（如果自动安装失败）:
```bash
# Windows
cd %USERPROFILE%\.cache\codesign-extractor
npm install playwright
npx playwright install chromium

# 如果下载速度慢（国内镜像）
set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
npx playwright install chromium
```

---

## CoDesign 特殊处理

### Canvas 渲染检测

CoDesign 设计稿使用 Canvas/WebGL 渲染，脚本会自动检测：

```
⚠️ 检测到 Canvas 渲染，主题提取可能不完整
```

**Canvas 模式下的策略**:
1. 截图仍然可用（全页截图）
2. 设计令牌可能不完整（从有限 DOM 提取）
3. **推荐使用 CoDesign API 模式**（`--use-api`，需要 token）
4. 或手动在 CoDesign 中导出设计令牌

### 需要登录的页面

```bash
# 方法 1: 连接已登录的 Chrome（推荐）
start chrome --remote-debugging-port=9222
# 在 Chrome 中登录 CoDesign 后运行:
node scripts/clone.mjs <URL> quick --connect-cdp http://localhost:9222

# 方法 2: 显示浏览器窗口手动登录
node scripts/clone.mjs <URL> quick --no-headless
```

### CoDesign API Token

1. 访问 CoDesign 开放平台获取 API token
2. 设置环境变量：
   ```bash
   set CODESIGN_TOKEN=your_api_token
   ```
3. 使用 `--use-api` 参数：
   ```bash
   node scripts/extract.mjs <PROJECT_ID> --all --use-api
   ```

---

## 与 Axure 技能包的对比

| 维度 | Axure 技能包 | CoDesign 技能包 |
|------|--------------|----------------|
| 数据获取 | 静态 JS 文件解析（`data/document.js`） | Playwright 浏览器渲染 + 可选 API |
| DOM 可用性 | 高（标准 HTML） | 低（Canvas 渲染）或 中（原型模式） |
| 设计令牌 | 从 JS 数据提取 | 从 computedStyle 或 API 提取 |
| 交互数据 | 从 `interactionMap` 提取 | 需要 Playwright 交互或 API |
| 推荐方式 | 浏览器 + 静态解析 | **API + 截图**（最佳） |
| 登录处理 | CDP 连接 | CDP 连接 或 API Token |

---

## 技能之间的关系

```
用户提供 CoDesign URL
    │
    ▼
┌─────────────────────┐
│  extract-codesign-  │
│  data               │
│  (提取原始数据)      │
└─────────┬───────────┘
          │
          ├─────────────► 输出: screenshot.png, theme.json, data.json, notes.json
          │
          ▼
┌─────────────────────┐
│  clone-codesign-    │
│  page               │
│  (克隆页面)          │
└─────────┬───────────┘
          │
          ├─────────────► 输出: clone-data/ (渐进式采集结果)
          │
          ▼
┌─────────────────────┐
│  generate-codesign- │
│  theme              │
│  (生成主题文档)      │
└─────────────────────┘
          │
          └─────────────► 输出: DESIGN.md, globals.css
```

---

## 常见问题

### Q: CoDesign 设计稿使用 Canvas 渲染，能提取 DOM 吗？

A: 设计稿页面（`/design/xxx`）通常使用 Canvas 渲染，DOM 提取可能受限。推荐方案：
1. 使用 **CoDesign API 模式**（`--use-api`，需要 token）
2. 或依赖**截图**作为视觉参考
3. 原型页面（`/prototype/xxx`）通常可以提取 DOM

### Q: 如何获取 CoDesign API Token？

A: 访问 CoDesign 开放平台（https://codesign.qq.com/open），按照文档说明申请 API token。

### Q: 截图是空白的怎么办？

A: CoDesign 页面可能需要更长的时间渲染。尝试：
1. 增加等待时间：`--wait 5000`
2. 显示浏览器窗口：`--no-headless`，观察页面加载情况
3. 使用 CDP 连接已登录的 Chrome：`--connect-cdp http://localhost:9222`

### Q: 能和 Axure 技能包一起使用吗？

A: 可以。Axure 技能包处理 Axure 原型，CoDesign 技能包处理 CoDesign 设计稿，两者互不干扰。

---

## 文件清单

```
Codesign-Skills/
├── README.md                                   # 本文件
├── extract-codesign-data/
│   ├── SKILL.md                               # 技能描述
│   └── scripts/
│       ├── extract.mjs                        # 核心提取脚本
│       ├── lib/                              # (预留) 工具库
│       └── inject/                           # (预留) 浏览器注入脚本
├── clone-codesign-page/
│   ├── SKILL.md                               # 技能描述
│   └── scripts/
│       ├── clone.mjs                          # 核心克隆脚本
│       └── lib/                              # (预留) 工具库
└── generate-codesign-theme/
    ├── SKILL.md                               # 技能描述
    └── scripts/                              # (预留) 生成脚本
```

---

## 后续开发计划

1. **完善 API 模式**:
   - 实现完整的 CoDesign Open API 集成
   - 支持获取组件树、标注、设计令牌等

2. **增强错误处理**:
   - 添加更详细的错误报告和重试逻辑
   - 处理网络异常、API 限流等

3. **自动化主题生成**:
   - 实现 `generate-codesign-theme` 的自动化脚本
   - 从 theme.json + 截图分析自动生成 DESIGN.md 和 globals.css

4. **支持更多 CoDesign 功能**:
   - 支持 CoDesign 的版本历史
   - 支持团队协作标注提取
   - 支持设计稿评论提取

---

## 许可证

MIT License

---

**创建日期**: 2026-05-20
**作者**: 鸿溟+智能体集成
**版本**: 1.0.0
