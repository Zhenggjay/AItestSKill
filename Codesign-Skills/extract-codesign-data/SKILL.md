---
name: extract-codesign-data
description: Extract structured data from Tencent CoDesign prototypes using Playwright and CoDesign Open API — screenshots, design tokens, component trees, annotations, and page text. Use this skill whenever the user wants to extract data from a CoDesign prototype, reconstruct or clone a CoDesign page, analyze CoDesign design tokens, export CoDesign content, or work with CoDesign URLs (look for codesign.qq.com links, CoDesign project/page IDs, or mentions of Tencent design prototypes).
---

# Extract CoDesign Data

Extract structured data from Tencent CoDesign prototypes for page reconstruction, design analysis, or content review. Supports both Playwright browser rendering and CoDesign Open API (when available).

## When to use this

- User shares a CoDesign prototype URL (`codesign.qq.com`) and wants to extract or rebuild it
- User asks to clone, reconstruct, or analyze a CoDesign design
- User mentions CoDesign, Tencent design platform, or prototype URLs with `codesign.qq.com`
- User wants design tokens, screenshots, or component data from a CoDesign prototype
- User wants to extract CoDesign design system tokens for theme generation

## How it works

CoDesign prototypes can be accessed in two ways:
1. **Playwright Browser Rendering** (default): Launch Chromium, navigate to CoDesign URL, capture screenshot and extract design tokens from rendered page
2. **CoDesign Open API** (optional, when API token is configured): Fetch design data directly via API for more accurate component tree and annotations

The script automatically chooses the best method based on available credentials.

## Quick start

Run the extraction script from `scripts/extract.mjs` relative to this skill directory.

```bash
# Basic extraction — screenshot + design tokens (default)
node scripts/extract.mjs <CODESIGN_URL> --all

# Full extraction — add component tree, annotations, page text
node scripts/extract.mjs <CODESIGN_URL> --all --advanced

# Use CoDesign API (requires CODESIGN_TOKEN env variable)
CODESIGN_TOKEN=your_token node scripts/extract.mjs <PROJECT_ID> --all --use-api

# Specific pages only
node scripts/extract.mjs <CODESIGN_URL> --pages login,dashboard

# CoDesign prototype URL examples:
# https://codesign.qq.com/prototype/xxx (prototype link)
# https://codesign.qq.com/design/xxx (design file link)
```

First run auto-installs Playwright + Chromium to `~/.cache/codesign-extractor/`. This takes 1-2 minutes and happens once.

## Parameters

| Flag | What it does | Default |
|---|---|---|
| `<url>` or `<project-id>` | CoDesign URL or project ID (required) | — |
| `--all` | Process all pages | first page only |
| `--advanced` | Add component tree, annotations, page text | off |
| `--use-api` | Use CoDesign Open API (requires token) | browser mode |
| `--api-token TOKEN` | CoDesign API token (or set `CODESIGN_TOKEN` env) | — |
| `-o DIR` | Output directory | `./codesign-export` |
| `--pages P1,P2` | Process only named pages | — |
| `--no-screenshot` | Skip screenshots | screenshots on |
| `--no-headless` | Show browser window | headless |
| `--connect-cdp URL` | Attach to running Chrome (for auth) | — |
| `--viewport WxH` | Viewport size | `1440x900` |
| `--wait MS` | Extra wait after page load (ms) | `2000` |
| `--scroll` | Scroll page to trigger lazy content | off |
| `--verbose` | Detailed logging | off |

## Output structure

```
codesign-export/
├── sitemap.json           # Page tree and hierarchy (always produced)
├── meta.json              # Project metadata (name, creator, version)
└── pages/{pageName}/
    ├── screenshot.png      # Page screenshot
    ├── theme.json          # Design tokens (colors, fonts, spacing, radii)
    ├── data.json           # Page metadata and component tree  (--advanced)
    ├── notes.json          # Component annotations            (--advanced, API mode)
    ├── interactions.json   # Event map (clicks, navigations)  (--advanced)
    └── content.md         # Rendered page text as Markdown   (--advanced)
```

## CoDesign URL formats

| URL Pattern | Type | Extraction Method |
|---|---|---|
| `https://codesign.qq.com/prototype/xxx` | Prototype (interactive) | Playwright + API |
| `https://codesign.qq.com/design/xxx` | Design file (static) | Playwright + API |
| `https://codesign.qq.com/app/xxx` | Application prototype | Playwright |
| Project ID (e.g., `xxx`) | API access | CoDesign Open API |

## Authenticated prototypes

CoDesign prototypes may require login (Tencent account, corporate SSO). Two approaches:

**Connect to an existing Chrome session** (recommended — reuses cookies):

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

**Use CoDesign API token** (most reliable for design files):
```bash
# Set environment variable
set CODESIGN_TOKEN=your_api_token
node scripts/extract.mjs <PROJECT_ID> --all --use-api

# Or pass token directly
node scripts/extract.mjs <PROJECT_ID> --all --use-api --api-token your_token
```

## CoDesign Open API

If you have a CoDesign API token, you can access design data directly:

1. **Get project info**: `GET /openapi/v1/projects/{projectId}`
2. **List pages**: `GET /openapi/v1/projects/{projectId}/pages`
3. **Get component tree**: `GET /openapi/v1/pages/{pageId}/components`
4. **Get annotations**: `GET /openapi/v1/pages/{pageId}/annotations`
5. **Download assets**: `GET /openapi/v1/assets/{assetId}`

Set the API token via environment variable `CODESIGN_TOKEN` or `--api-token` parameter.

API base URL: `https://codesign.qq.com/openapi/v1`

## Playwright extraction (browser mode)

When API is not available, the script uses Playwright to:
1. Navigate to CoDesign URL
2. Wait for page rendering (CoDesign uses Canvas/WebGL rendering)
3. Capture screenshot
4. Extract design tokens from computed styles (if DOM is available)
5. Extract page text as Markdown

**Note**: CoDesign uses Canvas/WebGL for rendering. Screenshots work well, but DOM-based extraction (theme tokens, Markdown) may be limited. Use API mode for best results.

## Recommended workflow: page reconstruction

When the goal is to rebuild a CoDesign prototype as a real web page, use a two-step approach:

**Step 1 — Basic extraction:**
```bash
node scripts/extract.mjs <URL> --pages <target>
```
Use `screenshot.png` as the visual reference and `theme.json` for exact colors, fonts, and spacing. Build the page.

**Step 2 — Refine if needed:**
```bash
node scripts/extract.mjs <URL> --pages <target> --advanced
```
If component details are missing or annotations are wrong, the additional files (`data.json`, `notes.json`, `content.md`) provide the detail to fix them.

## Dependency installation

The script auto-installs on first run. If it fails:

```bash
# Manual install
cd %USERPROFILE%\.cache\codesign-extractor   (Windows)
# or: cd ~/.cache/codesign-extractor   (macOS/Linux)

npm install playwright
npx playwright install chromium

# If Chromium download is slow (e.g. behind GFW):
PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright npx playwright install chromium
```

If Playwright can't be installed at all, the script degrades gracefully — it tries to use CoDesign API (if token is available), but skips screenshots and theme tokens.

## Output data formats

### theme.json
Design system tokens extracted from computed styles or CoDesign design system:

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
  "radius": [{"value": "4px", "count": 8}],
  "shadow": {
    "box": [{"value": "0 2px 8px rgba(0,0,0,0.1)", "count": 5}]
  },
  "cssVariables": {
    "--color-primary": "#0052D9",
    "--radius": "0.5rem"
  }
}
```

### data.json
Page component tree (from API or browser extraction):

```json
{
  "pageId": "xxx",
  "pageName": "Login",
  "components": [
    {"id": "c1", "type": "Button", "text": "登录", "position": {"x": 100, "y": 200}},
    {"id": "c2", "type": "Input", "placeholder": "请输入用户名"}
  ],
  "annotations": [
    {"componentId": "c1", "text": "主操作按钮，使用品牌色"}
  ]
}
```

## Playwright 查缺补漏

CoDesign 原型基于 Canvas/WebGL 渲染，某些动态内容（交互状态、条件面板、动态面板切换等）可能不完整。可使用 Playwright CLI 回到原型页面补充采集。

```bash
# 打开 CoDesign 原型
playwright-cli open <CODESIGN_URL>
playwright-cli snapshot

# 点击交互元素查看动态面板切换
playwright-cli click e12
playwright-cli screenshot --filename=panel-state-2.png

# 获取元素的精确样式（如果 DOM 可用）
playwright-cli eval "el => getComputedStyle(el).cssText" e5

playwright-cli close
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `HTTP 401: Unauthorized` | Check CODESIGN_TOKEN is valid, or use --connect-cdp for browser auth |
| `Screenshot is blank/white` | Page needs longer to render — add `--wait 5000` |
| `Canvas rendering detected` | Expected for CoDesign — screenshot still works, but theme extraction may be limited |
| `Need login` | Use `--connect-cdp` (see Authenticated prototypes above) |
| `Playwright install fails` | Manual install, or set `PLAYWRIGHT_DOWNLOAD_HOST` for mirror |
| `API rate limit` | Reduce request frequency, or use browser mode |
