---
name: clone-codesign-page
description: >
  从腾讯 CoDesign 设计稿/原型中提取数据、截图和克隆页面。支持页面树识别、路径定位、自适应缩放截图、DOM骨架、交互态采集。
  当用户提供任何 codesign.qq.com 链接时自动触发，包括：
  - https://codesign.qq.com/app/s/xxx（分享链接）
  - https://codesign.qq.com/prototype/xxx（原型链接）
  - https://codesign.qq.com/design/xxx（设计稿链接）
  适用于：理解原型、提取页面、生成测试用例、克隆页面、分析设计、提取设计令牌等场景。
  当用户说"理解原型"、"提取页面"、"生成测试用例"、"看看这个CoDesign设计"、
  "识别原型"、"截图原型"时也使用此技能。
---

# 克隆 CoDesign 页面

使用 Playwright 渐进式采集 CoDesign 页面数据，支持截图、DOM骨架、交互态、设计令牌采集。

**前置条件：** Node.js >= 18（Playwright 首次运行自动安装，优先使用系统 Chrome）

## CoDesign 页面类型

| 类型 | URL 模式 | 特点 |
|------|----------|------|
| 原型 (Prototype) | `codesign.qq.com/prototype/xxx` | 可交互，有页面跳转 |
| 设计稿 (Design) | `codesign.qq.com/design/xxx` | 静态设计，Canvas 渲染 |
| 应用 (App) | `codesign.qq.com/app/s/xxx` | 完整应用原型（分享链接） |

## 采集脚本

从技能目录下的 `scripts/` 运行：

```bash
node scripts/clone.mjs <url> <command> [options]
```

## 🆕 section 命令（推荐 - 用于理解原型/生成测试用例）

提取指定目录路径下所有页面的截图 + DOM骨架 + 文本 + 设计令牌。

```bash
# 提取指定目录下全部页面
node scripts/clone.mjs https://codesign.qq.com/app/s/xxx section --section <目录名> -o ./output

# 提取子目录下的页面（路径表达式）
node scripts/clone.mjs https://codesign.qq.com/app/s/xxx section --section <目录名>/<子目录名> -o ./output

# 仅列出目录结构不截图
node scripts/clone.mjs https://codesign.qq.com/app/s/xxx section --list-only -o ./output
```

**section 命令特性：**
- 通过 icon class 精确区分文件夹(`icon-v2-folder-open`)和页面(`icon-v2-page`)
- 支持多级路径表达式（`目录名/子目录名/页面名`）
- **文件夹节点也截图**（CoDesign 中文件夹点击后也会切换画布显示内容）
- 自适应缩放截图（根据内容尺寸自动计算缩放比例，1张截图装下全部内容）
- 无头模式 + 系统 Chrome（不需要手动启动浏览器）

**输出结构：**
```
output/
├── sitemap.json                    # 页面树结构
└── <目录名>_<子目录名>/
    └── <页面名>/
        ├── screenshot.png           # 自适应缩放截图
        ├── skeleton.json            # DOM 骨架树
        ├── content.md               # 页面文本
        └── theme.json               # 设计令牌
```

## 快速还原模式

适合快速出原型，token 消耗少，几分钟完成。

```bash
node scripts/clone.mjs <codesign-url> quick -o ./clone-data --scroll
```

**数据源优先级：**
1. ⭐⭐⭐⭐⭐ `screenshot.png` — 视觉真相，以它为准
2. ⭐⭐⭐⭐ `theme.json` — 颜色、字体、间距等设计令牌
3. ⭐⭐⭐ `skeleton.json` — DOM 骨架（了解层级和语义标签）

## 高精度还原模式

适合生产环境，还原到像素级别。

```bash
# 先执行 quick
node scripts/clone.mjs <codesign-url> quick -o ./clone-data --scroll

# 逐 section 深入采集样式
node scripts/clone.mjs <codesign-url> styles -o ./clone-data --selector "header"
node scripts/clone.mjs <codesign-url> styles -o ./clone-data --selector "main > section:nth-child(1)"

# 交互态
node scripts/clone.mjs <codesign-url> interact -o ./clone-data --hover "nav a:first-child"

# 响应式截图
node scripts/clone.mjs <codesign-url> responsive -o ./clone-data

# 下载资源
node scripts/clone.mjs <codesign-url> assets -o ./clone-data
```

## 采集命令速查

| 命令 | 用途 | 产出 |
|------|------|------|
| `section` | 🆕 提取指定目录路径下所有页面 | screenshot + skeleton + content + theme |
| `quick` | 快速模式 = init + skeleton | screenshot + meta + theme + skeleton |
| `full` | 全量模式 = init + skeleton + responsive + assets | 上述 + 响应式截图 + 资源 |
| `init` | 截图 + 元信息 + 设计令牌 | screenshot.png, meta.json, theme.json |
| `skeleton` | DOM 骨架（不含样式） | skeleton.json |
| `styles --selector "X"` | 指定区域的完整样式 | sections/X/nodes.json + styles.json + screenshot.png |
| `interact` | 交互态截图 | interactions/*.png + *-styles.json |
| `responsive` | 多 viewport 截图 | responsive/*.png |
| `assets` | 下载图片/字体/SVG | assets/ |

## 选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-o, --output <dir>` | `./clone-data` | 输出目录 |
| `-s, --section <path>` | 无 | 目录路径（如 `模块名`、`模块名/子模块`）|
| `--selector <sel>` | 无 | CSS 选择器（用于 styles）|
| `--viewport WxH` | `1440x900` | 视口大小 |
| `--wait <ms>` | `2000` | 等待时间 |
| `--no-headless` | `false` | 显示浏览器窗口 |
| `--connect-cdp <url>` | 无 | 连接已登录的 Chrome |
| `--list-only` | `false` | 仅列出目录结构 |
| `--verbose` | `false` | 详细日志 |

## CoDesign 特殊处理

### Canvas 渲染检测

CoDesign 设计稿使用 Canvas 渲染，脚本会自动检测。原型页面（`/app/s/xxx`）通常可以提取 DOM。

### 需要登录的页面

```bash
# 方法 1: 连接已登录的 Chrome
start chrome --remote-debugging-port=9222
node scripts/clone.mjs <codesign-url> section --section <目录名> --connect-cdp http://localhost:9222

# 方法 2: 显示浏览器窗口手动登录
node scripts/clone.mjs <codesign-url> section --section <目录名> --no-headless

# 方法 3: 无头模式（推荐，不需要手动启动浏览器）
node scripts/clone.mjs <codesign-url> section --section <目录名>
```

## 提示

- **截图是最终真相** — 如果数据与截图冲突，以截图为准
- **section 命令自适应缩放** — 根据内容尺寸自动计算缩放，1张截图装下全部内容
- **icon class 识别** — 文件夹(`icon-v2-folder-open`) vs 页面(`icon-v2-page`)，精确无误差
- **路径表达式** — 支持 `目录名/子目录名/页面名` 多级路径
- **系统 Chrome** — 优先使用系统 Chrome，避免 Playwright Chromium 版本不匹配
- **渐进式采集** — 先 section 看效果，再按需 styles
- **selector 是桥梁** — skeleton.json 中每个节点都有 CSS selector，用于后续精确定位
