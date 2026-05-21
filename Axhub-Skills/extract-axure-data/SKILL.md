---
name: extract-axure-data
description: 使用 Playwright 从 Axure 原型中提取结构化数据——包括屏幕截图、设计标记、交互图、注释以及页面文本。当用户需要从 Axure 原型中提取数据、重建或克隆 Axure 页面、分析 Axure 设计标记、导出 Axure 内容或处理 Axure 原型网址（即使这些网址没有明确标注“Axure”——寻找 AxShare 链接、/start.html#p= 网址或提及在线托管的线框/原型的内容）时，请使用此功能
---

# Extract Axure Data

从 Axure 原型中提取结构化数据，用于页面重建、内容分析或设计审查。该脚本会自动处理依赖项的安装——只需将其指向一个 URL 即可。

## When to use this

- 用户分享了一个 Axure 原型的网址，并希望对其进行提取或重建
- 用户要求克隆、重建或分析一个线框图/原型
- 用户提到 AxShare、Axure 云或者带有 `start.html#p=` 格式的原型网址
- 用户希望获取原型中的设计标识、截图或交互数据

## How it works

Axure 将页面数据存储在静态的 JS 文件中（如 `data/document.js`、`files/{页面}/data.js`）。该脚本在 Node.js 中直接解析这些文件，无需浏览器即可完成——这种方式速度快，适用于网站地图、交互和注释。而截图和设计标记则需要进行渲染，因此 Playwright 会为这些内容启动一个 Chromium 实例。

## Quick start

Run the extraction script from `scripts/extract.mjs` relative to this skill directory.

```bash
# Basic extraction — screenshot + design tokens (default)
node scripts/extract.mjs <AXURE_URL> --all

# Full extraction — add interactions, annotations, page text
node scripts/extract.mjs <AXURE_URL> --all --advanced

# Specific pages only
node scripts/extract.mjs <AXURE_URL> --pages login,dashboard
```

First run auto-installs Playwright + Chromium to `~/.cache/axure-extractor/`. This takes 1-2 minutes and happens once.

## Parameters

| Flag | What it does | Default |
|---|---|---|
| `<url>` | Axure prototype URL (required) | — |
| `--all` | Process all pages | first page only |
| `--advanced` | Add interactions, annotations, page text | off |
| `-o DIR` | Output directory | `./axure-export` |
| `--pages P1,P2` | Process only named pages | — |
| `--no-screenshot` | Skip screenshots | screenshots on |
| `--no-headless` | Show browser window | headless |
| `--connect-cdp URL` | Attach to running Chrome (for auth) | — |
| `--verbose` | Detailed logging | off |

## Output structure

```
axure-export/
├── sitemap.json           # Page tree and hierarchy (always produced)
└── pages/{pageName}/
    ├── screenshot.png      # Page screenshot
    ├── theme.json          # Design tokens (colors, fonts, spacing, radii)
    ├── data.json           # Page metadata and diagram        (--advanced)
    ├── notes.json          # Component annotations            (--advanced)
    ├── interactions.json   # Event map (clicks, navigations)  (--advanced)
    └── content.md          # Rendered page text as Markdown   (--advanced)
```

## Recommended workflow: page reconstruction

When the goal is to rebuild an Axure prototype as a real web page, use a two-step approach. The reason for splitting is that screenshots + theme tokens are enough for ~80% visual fidelity, and the additional data only helps when fine-tuning details — so extracting everything upfront wastes time if the basic result is already good.

**Step 1 — Basic extraction:**
```bash
node scripts/extract.mjs <URL> --pages <target>
```
Use `screenshot.png` as the visual reference and `theme.json` for exact colors, fonts, and spacing. Build the page.

**Step 2 — Refine if needed:**
```bash
node scripts/extract.mjs <URL> --pages <target> --advanced
```
If interactions are missing or annotations are wrong, the additional files (`interactions.json`, `notes.json`, `content.md`) provide the detail to fix them.

## Authenticated prototypes

Some Axure prototypes require login (AxShare, corporate SSO). Two approaches:

**Connect to an existing Chrome session** (recommended — reuses cookies):

macOS:
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

Windows:
```powershell
start chrome --remote-debugging-port=9222
```

Then log in via that Chrome window and run:
```bash
node scripts/extract.mjs <URL> --all --connect-cdp http://localhost:9222
```

**Show the browser window** (manual login during extraction):
```bash
node scripts/extract.mjs <URL> --all --no-headless
```

## Dependency installation

The script auto-installs on first run. If it fails:

```bash
# Manual install
cd ~/.cache/axure-extractor   # macOS/Linux
# or: cd %USERPROFILE%\.cache\axure-extractor   (Windows)

npm install playwright
npx playwright install chromium

# If Chromium download is slow (e.g. behind GFW):
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright npx playwright install chromium
```

If Playwright can't be installed at all, the script degrades gracefully — it still extracts sitemap, page data, annotations, and interactions (everything that doesn't need a browser), but skips screenshots and theme tokens.

## Output data formats

### theme.json
Design system tokens extracted from computed styles:
```json
{
  "colors": {
    "background": [{"value": "rgb(255,255,255)", "count": 42, "tags": ["div"]}],
    "text": [{"value": "rgb(51,51,51)", "count": 28, "tags": ["p","span"]}],
    "border": [{"value": "rgb(221,221,221)", "count": 12}]
  },
  "typography": {
    "families": [{"value": "\"PingFang SC\", sans-serif", "count": 56}],
    "textStyles": [{"size": "14px", "lineHeight": "22px", "weight": "400", "count": 20}]
  },
  "spacing": [{"value": "16px", "count": 15}],
  "radius": [{"value": "4px", "count": 8}]
}
```

### notes.json
Component annotations authored in Axure:
```json
{
  "page": {"description": "User login page"},
  "id-username-input": {"description": "Username field", "placeholder": "Enter username"},
  "id-submit-btn": {"description": "Login button", "action": "Submit form"}
}
```

### interactions.json
Event mappings defined in Axure's interaction designer:
```json
{
  "onClick": {"targetPage": "dashboard", "action": "navigate"}
}
```

## Playwright 查缺补漏

导出数据基于静态 JS 解析和快照采集，某些动态内容（交互状态、条件面板、动态面板切换等）可能不完整。可使用 Playwright CLI 回到原型页面补充采集。

```bash
# 打开 Axure 原型
playwright-cli open <AXURE_URL>
playwright-cli snapshot

# 点击交互元素查看动态面板切换
playwright-cli click e12
playwright-cli screenshot --filename=panel-state-2.png

# 获取元素的精确样式
playwright-cli eval "el => getComputedStyle(el).cssText" e5

playwright-cli close
```

> **完整命令参考**: [Playwright CLI 官方技能文档](https://github.com/microsoft/playwright-cli/blob/main/skills/playwright-cli/SKILL.md)

### 典型补充场景

| 场景 | Playwright 做什么 |
|------|------------------|
| 动态面板状态 | 点击触发切换后截图 |
| 条件显示/隐藏 | 触发条件后采集 DOM |
| 交互动画 | 录制交互过程 |
| 需要登录的原型 | 复用已登录的 Chrome 会话 |
| Axure 母版内容 | 进入页面后完整采集 |

## Troubleshooting

| Problem | Fix |
|---|---|
| `HTTP 404: .../data/document.js` | URL isn't an Axure prototype, or wrong base URL |
| `Sitemap 提取失败` | Check URL is reachable: `curl -I <url>` |
| Screenshots are blank | Page needs longer to render — try `--no-headless` to watch |
| Need login | Use `--connect-cdp` (see Authenticated prototypes above) |
| Playwright install fails | Manual install, or set `PLAYWRIGHT_DOWNLOAD_HOST` for mirror |
