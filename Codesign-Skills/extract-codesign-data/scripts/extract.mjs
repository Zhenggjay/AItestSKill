#!/usr/bin/env node
/**
 * extract-codesign-data.mjs
 * Extract data from Tencent Codesign prototypes
 * Usage: node extract.mjs <url|project-id> [options]
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ============================================================================
// Phase 0: Environment check & auto-install
// ============================================================================

function getRunnerDir() {
  const home = os.homedir();
  return path.join(home, '.cache', 'codesign-extractor');
}

const RUNNER_DIR = getRunnerDir();

async function ensureDependencies() {
  const pkgPath = path.join(RUNNER_DIR, 'node_modules', 'playwright');
  if (fs.existsSync(pkgPath)) return;

  console.log('[安装] 首次运行，正在安装 Playwright...');
  fs.mkdirSync(RUNNER_DIR, { recursive: true });
  fs.writeFileSync(
    path.join(RUNNER_DIR, 'package.json'),
    JSON.stringify({ type: 'module', private: true }, null, 2)
  );

  const env = {
    ...process.env,
    PLAYWRIGHT_DOWNLOAD_HOST:
      process.env.PLAYWRIGHT_DOWNLOAD_HOST || 'https://npmmirror.com/mirrors/playwright',
  };

  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const npxCmd = process.platform === 'win32' ? 'npx.cmd' : 'npx';

  try {
    execSync(`${npmCmd} install playwright`, { cwd: RUNNER_DIR, stdio: 'inherit', env });
  } catch (e) {
    console.error('[错误] Playwright 安装失败:', e.message);
    console.log('手动安装: cd "' + RUNNER_DIR + '" && npm install playwright');
    return;
  }

  try {
    execSync(`${npxCmd} playwright install chromium`, { cwd: RUNNER_DIR, stdio: 'inherit', env });
  } catch (e) {
    console.warn('[警告] Chromium 安装失败，将尝试使用系统浏览器');
  }

  console.log('[完成] Playwright 安装完成');
}

function isPlaywrightAvailable() {
  return fs.existsSync(path.join(RUNNER_DIR, 'node_modules', 'playwright'));
}

async function loadPlaywright() {
  const pwPath = path.join(RUNNER_DIR, 'node_modules', 'playwright', 'index.mjs');
  if (!fs.existsSync(pwPath)) return null;
  // Windows 上需要使用 file:// URL 格式
  const pwUrl = pathToFileURL(pwPath).href;
  return import(pwUrl);
}

// ============================================================================
// Codesign API Client
// ============================================================================

function getApiToken(options = {}) {
  return options.apiToken || process.env.CODESIGN_TOKEN || process.env.CODESIGN_API_TOKEN || null;
}

async function apiRequest(endpoint, options = {}) {
  const token = getApiToken(options);
  if (!token) throw new Error('需要 API token。请设置 CODESIGN_TOKEN 环境变量或使用 --api-token');

  const baseUrl = 'https://codesign.qq.com/openapi/v1';
  const url = endpoint.startsWith('http') ? endpoint : `${baseUrl}${endpoint}`;

  const response = await fetch(url, {
    method: options.method || 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`API ${response.status}: ${text}`);
  }

  return response.json();
}

// ============================================================================
// Playwright browser layer
// ============================================================================

let _browser = null;

async function getBrowser(playwright, options = {}) {
  if (_browser) return _browser;
  const { headless = true, connectCdp } = options;

  if (connectCdp) {
    console.log('[CDP] 连接到 Chrome:', connectCdp);
    _browser = await playwright.chromium.connectOverCDP(connectCdp);
  } else {
    _browser = await playwright.chromium.launch({
      headless,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
  }
  return _browser;
}

async function closeBrowser() {
  if (_browser) { await _browser.close().catch(() => {}); _browser = null; }
}

async function captureScreenshot(playwright, url, outputPath, options = {}) {
  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({
    viewport: options.viewport || { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  try {
    console.log('  [截图] 正在捕获:', url);
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 2000);
    await page.screenshot({ path: outputPath, fullPage: true, type: 'png' });
    console.log('  [完成] 截图已保存:', outputPath);
    return outputPath;
  } finally { await context.close(); }
}

async function captureScrollableScreenshots(playwright, url, outputDir, baseName, options = {}) {
  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({
    viewport: options.viewport || { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  try {
    console.log('  [滚动截图] 正在捕获:', url);
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 2000);

    // Get page dimensions - 增强检测逻辑
    const dimensions = await page.evaluate(() => {
      let maxScrollHeight = 0;
      let maxScrollableElement = null;

      // 检查主文档
      const docScrollHeight = Math.max(
        document.documentElement.scrollHeight,
        document.body.scrollHeight,
        document.documentElement.offsetHeight,
        document.body.offsetHeight
      );
      maxScrollHeight = Math.max(maxScrollHeight, docScrollHeight);

      // 检查所有可滚动元素
      const allElements = document.querySelectorAll('*');
      allElements.forEach(el => {
        if (el.scrollHeight > el.clientHeight) {
          if (el.scrollHeight > maxScrollHeight) {
            maxScrollHeight = el.scrollHeight;
            maxScrollableElement = el;
          }
        }
      });

      // 检查 iframe
      const iframes = document.querySelectorAll('iframe');
      if (iframes.length > 0) {
        // 如果有 iframe，尝试获取其内容的高度
        try {
          iframes.forEach(iframe => {
            const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
            if (iframeDoc) {
              const iframeHeight = Math.max(
                iframeDoc.documentElement.scrollHeight,
                iframeDoc.body.scrollHeight
              );
              if (iframeHeight > maxScrollHeight) {
                maxScrollHeight = iframeHeight;
              }
            }
          });
        } catch (e) {
          // 跨域限制，忽略
        }
      }

      return {
        scrollHeight: maxScrollHeight,
        viewportHeight: window.innerHeight,
        hasScrollableContainer: maxScrollableElement !== null,
      };
    });

    let totalHeight = dimensions.scrollHeight;
    const viewportHeight = dimensions.viewportHeight;

    // 如果检测到的高度等于视口高度，可能是 CoDesign 使用了特殊渲染
    // 尝试逐步滚动来探测实际高度
    if (totalHeight <= viewportHeight) {
      console.log('  [滚动截图] 未检测到滚动内容，尝试逐步滚动探测...');

      // 尝试滚动一下，看看页面是否真的可以滚动
      const scrollTest = await page.evaluate(() => {
        const originalScrollY = window.scrollY;
        window.scrollBy(0, 100);
        const newScrollY = window.scrollY;
        window.scrollTo(0, originalScrollY);

        return {
          canScroll: newScrollY > originalScrollY,
          scrollHeight: document.documentElement.scrollHeight,
        };
      });

      if (scrollTest.canScroll || scrollTest.scrollHeight > viewportHeight) {
        totalHeight = scrollTest.scrollHeight;
      }
    }

    const numScreenshots = Math.ceil(totalHeight / viewportHeight);

    console.log(`  [滚动截图] 页面总高度: ${totalHeight}px, 视口高度: ${viewportHeight}px, 需要截取 ${numScreenshots} 张图片`);

    if (numScreenshots <= 1) {
      console.log('  [滚动截图] 页面无需滚动，使用普通截图模式');
      const screenshotPath = path.join(outputDir, `${baseName}_1.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true, type: 'png' });
      console.log(`  [完成] 截图 1/1 已保存: ${path.basename(screenshotPath)}`);
      return [screenshotPath];
    }

    const screenshots = [];

    for (let i = 0; i < numScreenshots; i++) {
      const scrollY = i * viewportHeight;

      // Scroll to position
      await page.evaluate((y) => {
        window.scrollTo(0, y);
      }, scrollY);

      // Wait for scroll to complete and content to load
      await page.waitForTimeout(800);

      // Take screenshot
      const screenshotPath = path.join(outputDir, `${baseName}_${i + 1}.png`);
      await page.screenshot({ path: screenshotPath, type: 'png' });
      screenshots.push(screenshotPath);
      console.log(`  [完成] 截图 ${i + 1}/${numScreenshots} 已保存: ${path.basename(screenshotPath)}`);
    }

    // Scroll back to top
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);

    return screenshots;
  } finally { await context.close(); }
}

async function extractThemeTokens(playwright, url, options = {}) {
  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({
    viewport: options.viewport || { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 2000);

    // Check if Canvas rendering
    const hasCanvas = await page.evaluate(() => {
      return !!document.querySelector('canvas') ||
             !!document.querySelector('[class*="canvas"]') ||
             !!document.querySelector('[class*="renderer"]');
    });

    if (hasCanvas) {
      console.log('  [警告] 检测到 Canvas 渲染，主题提取可能不完整');
    }

    return await page.evaluate(() => {
      const bucket = () => new Map();

      const add = (b, v, t) => {
        if (!v) return;
        if (!b.has(v)) b.set(v, { count: 0, tags: new Set() });
        const item = b.get(v);
        item.count++;
        if (t) item.tags.add(t);
      };

      const isClear = (v) => {
        if (!v) return false;
        const l = v.trim().toLowerCase();
        return l === 'transparent' || l === 'rgba(0, 0, 0, 0)' || l === 'rgba(0,0,0,0)';
      };

      const isZero = (v) => {
        if (!v) return false;
        const t = v.trim();
        return t === '0' || t === '0px';
      };

      const colors = { bg: bucket(), text: bucket(), border: bucket() };
      const typo = { family: bucket(), style: bucket() };
      const spacing = bucket(), radius = bucket();

      // Get CSS variables
      const cssVars = {};
      try {
        const rootStyle = getComputedStyle(document.documentElement);
        for (let i = 0; i < rootStyle.length; i++) {
          const prop = rootStyle[i];
          if (prop.startsWith('--')) {
            cssVars[prop] = rootStyle.getPropertyValue(prop).trim();
          }
        }
      } catch (e) {}

      // Walk DOM
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
      let el = walker.currentNode;
      let count = 0;
      while (el && count < 3000) {
        const tag = el.tagName?.toLowerCase() || '';
        const s = getComputedStyle(el);

        if (s.backgroundColor && !isClear(s.backgroundColor)) add(colors.bg, s.backgroundColor, tag);
        if (s.color && !isClear(s.color)) add(colors.text, s.color, tag);
        if (s.borderColor && !isClear(s.borderColor)) add(colors.border, s.borderColor, tag);

        add(typo.family, s.fontFamily, tag);
        if (s.fontSize && s.fontWeight && s.lineHeight) {
          add(typo.style, `${s.fontSize}|${s.lineHeight}|${s.fontWeight}`, tag);
        }

        if (s.margin && !isZero(s.margin)) add(spacing, s.margin, tag);
        if (s.padding && !isZero(s.padding)) add(spacing, s.padding, tag);
        if (s.borderRadius && !isZero(s.borderRadius)) add(radius, s.borderRadius, tag);

        el = walker.nextNode();
        count++;
      }

      const sort = (b) => [...b.entries()]
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 10)
        .map(([v, { count, tags }]) => ({ value: v, count, tags: [...tags] }));

      return {
        colors: {
          background: sort(colors.bg),
          text: sort(colors.text),
          border: sort(colors.border),
        },
        typography: {
          families: sort(typo.family),
          textStyles: sort(typo.style).map(({ value, count, tags }) => {
            const [size, lineHeight, weight] = value.split('|');
            return { size, lineHeight, weight, count, tags };
          }),
        },
        spacing: sort(spacing),
        radius: sort(radius),
        cssVariables: Object.keys(cssVars).length > 0 ? cssVars : undefined,
      };
    });
  } finally { await context.close(); }
}

// ============================================================================
// Page discovery & navigation
// ============================================================================

async function discoverPages(page) {
  console.log('  [发现] 正在分析页面结构...');

  // 调试：打印页面中的所有可能的相关元素
  if (true) { // 总是执行，可以改为 if (args.verbose)
    const debugInfo = await page.evaluate(() => {
      const info = {
        title: document.title,
        url: window.location.href,
        iframes: [],
        sidebars: [],
        possiblePageItems: [],
      };

      // 检查 iframes
      const iframes = document.querySelectorAll('iframe');
      iframes.forEach((iframe, i) => {
        info.iframes.push({
          index: i,
          src: iframe.src,
          id: iframe.id,
          class: iframe.className,
        });
      });

      // 检查可能的侧边栏
      const sidebarSelectors = ['[class*="sidebar"]', '[class*="toc"]', '[class*="directory"]', '[class*="nav"]'];
      sidebarSelectors.forEach(selector => {
        const el = document.querySelector(selector);
        if (el) {
          info.sidebars.push({
            selector: selector,
            text: el.innerText?.substring(0, 200),
            childCount: el.children.length,
          });
        }
      });

      // 检查可能的页面项
      const pageItemSelectors = ['[class*="page-item"]', '[class*="artboard"]', '[class*="screen"]', '[data-page-id]'];
      pageItemSelectors.forEach(selector => {
        const items = document.querySelectorAll(selector);
        if (items.length > 0) {
          items.forEach((item, i) => {
            info.possiblePageItems.push({
              selector: `${selector}:nth-child(${i + 1})`,
              text: item.innerText?.trim().substring(0, 50),
              dataPageId: item.getAttribute('data-page-id'),
              dataName: item.getAttribute('data-name'),
            });
          });
        }
      });

      return info;
    });

    console.log('  [调试] 页面信息:', JSON.stringify(debugInfo, null, 2).substring(0, 500));
  }

  const pages = await page.evaluate(() => {
    const results = [];

    // Method 1: 查找导航菜单中的链接
    const navLinks = document.querySelectorAll('nav a, [class*="nav"] a, [class*="menu"] a, [class*="sidebar"] a');
    navLinks.forEach((link, index) => {
      const href = link.href || link.getAttribute('href');
      const text = link.innerText || link.textContent || '';
      if (href && text.trim() && !href.startsWith('#')) {
        results.push({
          name: text.trim(),
          url: href,
          method: 'nav-link',
          index: index,
          selector: `[href="${href}"]`,
        });
      }
    });

    // Method 2: 查找页面切换器 / 标签页
    const tabButtons = document.querySelectorAll('[role="tab"], [class*="tab"], [class*="page-switcher"] button');
    if (tabButtons.length > 0) {
      tabButtons.forEach((btn, index) => {
        const text = btn.innerText || btn.textContent || '';
        if (text.trim()) {
          results.push({
            name: text.trim(),
            selector: btn.id ? `#${btn.id}` : `[role="tab"]:nth-child(${index + 1})`,
            method: 'tab-button',
            index: index,
          });
        }
      });
    }

    // Method 3: 查找 Axure 原型特有的页面列表
    const pageListItems = document.querySelectorAll('[id*="pageList"] li, [class*="page-list"] li, [class*="sitemap"] a, [class*="sitemap"] li');
    if (pageListItems.length > 0) {
      pageListItems.forEach((item, index) => {
        const text = item.innerText || item.textContent || '';
        const onclick = item.getAttribute('onclick') || '';
        const dataPage = item.getAttribute('data-page') || item.getAttribute('data-id') || '';
        if (text.trim()) {
          results.push({
            name: text.trim(),
            action: onclick,
            dataPage: dataPage,
            method: 'page-list',
            index: index,
            selector: `[data-index="${index}"]`,
          });
        }
      });
    }

    // Method 4: 查找 CoDesign 特有的页面导航 - 增强版
    // 查找所有可能是页面项的元素
    const possiblePageItems = document.querySelectorAll(`
      [class*="page-item"],
      [class*="artboard"],
      [class*="screen"],
      [class*="canvas-item"],
      [data-page-id],
      [data-artboard-id],
      [class*="thumbnail"],
      [class*="sidebar"] [class*="item"]
    `);

    if (possiblePageItems.length > 0) {
      possiblePageItems.forEach((item, index) => {
        const text = item.getAttribute('data-name') ||
                     item.getAttribute('aria-label') ||
                     item.innerText ||
                     item.textContent ||
                     '';
        const pageId = item.getAttribute('data-page-id') ||
                       item.getAttribute('data-artboard-id') ||
                       item.getAttribute('data-id') ||
                       '';
        const isClickable = item.onclick ||
                           item.getAttribute('onclick') ||
                           item.tagName === 'BUTTON' ||
                           item.getAttribute('role') === 'button' ||
                           item.style.cursor === 'pointer';

        if ((text.trim() || pageId) && isClickable) {
          results.push({
            name: text.trim() || `Page-${pageId}`,
            pageId: pageId,
            method: 'codesign-page',
            index: index,
            selector: item.id ? `#${item.id}` : `[data-index="${index}"]`,
            clickable: true,
          });
        }
      });
    }

    // Method 5: 查找包含页面名称的目录/侧边栏 - 增强版
    // 查找所有可点击的侧边栏项
    const sidebar = document.querySelector('[class*="sidebar"], [class*="toc"], [class*="directory"], [class*="nav"]');
    if (sidebar) {
      const sidebarItems = sidebar.querySelectorAll('[class*="item"], [class*="link"], [class*="page"], button, a');
      sidebarItems.forEach((item, index) => {
        const text = item.innerText || item.textContent || '';
        const dataPage = item.getAttribute('data-page') ||
                       item.getAttribute('data-id') ||
                       item.getAttribute('href') ||
                       '';
        if (text.trim() && text.trim().length < 50) { // 避免匹配到长文本
          results.push({
            name: text.trim(),
            pageId: dataPage,
            method: 'sidebar-item',
            index: index,
            selector: item.id ? `#${item.id}` : `${item.tagName.toLowerCase()}[data-index="${index}"]`,
            clickable: true,
          });
        }
      });
    }

    // Method 6: 从页面文本中提取页面名称 (降级方案)
    // 查找类似 "用户端" "设置列表" "新对话" 这样的文本
    const bodyText = document.body.innerText || '';
    const pageNames = ['用户端', '设置列表', '新对话', '自动化', '新建弹窗', '资料库', '源文件'];
    pageNames.forEach((name, index) => {
      if (bodyText.includes(name) && !results.some(r => r.name === name)) {
        results.push({
          name: name,
          method: 'text-extraction',
          index: index,
          selector: null, // 需要通过其他方式定位
        });
      }
    });

    // 去重（基于名称）
    const uniqueResults = [];
    const seenNames = new Set();
    results.forEach(item => {
      if (!seenNames.has(item.name)) {
        seenNames.add(item.name);
        uniqueResults.push(item);
      }
    });

    return uniqueResults;
  });

  console.log(`  [发现] 找到 ${pages.length} 个页面`);
  pages.forEach((p, i) => {
    console.log(`    ${i + 1}. ${p.name} (${p.method}) ${p.selector ? `- selector: ${p.selector}` : ''}`);
  });

  return pages;
}

// ============================================================================
// Text extraction
// ============================================================================

async function extractPageText(playwright, url, options = {}) {
  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({
    viewport: options.viewport || { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 2000);

    const textContent = await page.evaluate(() => {
      // Remove script and style elements
      const clone = document.body.cloneNode(true);
      clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());

      // Get text content
      const text = clone.innerText || clone.textContent || '';

      // Clean up: remove empty lines and excessive whitespace
      return text
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .join('\n');
    });

    return textContent;
  } finally { await context.close(); }
}

// ============================================================================
// CLI
// ============================================================================

function parseArgs(argv) {
  const args = {
    url: null,
    output: './codesign-export',
    all: false,
    advanced: false,
    useApi: false,
    apiToken: null,
    screenshot: true,
    headless: true,
    connectCdp: null,
    viewport: { width: 1440, height: 900 },
    wait: 2000,
    verbose: false,
    help: false,
    text: false,
    scrollScreenshots: false,
  };

  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--help' || a === '-h') args.help = true;
    else if (a === '-o' || a === '--output') args.output = argv[++i];
    else if (a === '--all') args.all = true;
    else if (a === '--advanced') args.advanced = true;
    else if (a === '--use-api') args.useApi = true;
    else if (a === '--api-token') args.apiToken = argv[++i];
    else if (a === '--no-screenshot') args.screenshot = false;
    else if (a === '--no-headless') args.headless = false;
    else if (a === '--connect-cdp') args.connectCdp = argv[++i];
    else if (a === '--viewport') {
      const [w, h] = (argv[++i] || '1440x900').split('x').map(Number);
      args.viewport = { width: w || 1440, height: h || 900 };
    }
    else if (a === '--wait') args.wait = parseInt(argv[++i]) || 2000;
    else if (a === '--verbose') args.verbose = true;
    else if (a === '--text') args.text = true;
    else if (a === '--scroll-screenshots') args.scrollScreenshots = true;
    else if (!a.startsWith('-') && !args.url) args.url = a;
  }
  return args;
}

function showHelp() {
  console.log(`
Codesign 原型数据提取工具

用法:
  node extract.mjs <url|project-id> [options]

模式:
  默认          截图 + 设计主题
  --advanced   追加组件数据、标注、文本

选项:
  -o, --output DIR    输出目录 (默认: ./codesign-export)
  --all               提取全部
  --advanced          高级模式
  --use-api           使用 Codesign Open API (需要 token)
  --api-token TOKEN   API token
  --no-screenshot     跳过截图
  --no-headless       显示浏览器
  --connect-cdp URL   连接 Chrome (复用登录态)
  --viewport WxH      视口大小 (默认: 1440x900)
  --wait MS           等待时间 (默认: 2000)
  --text              提取页面文本
  --scroll-screenshots  滚动截图(适用于长页面)
  --verbose           详细日志
  -h, --help          帮助

示例:
  node extract.mjs https://codesign.qq.com/prototype/xxx --all
  set CODESIGN_TOKEN=xxx & node extract.mjs project_id --all --use-api
  node extract.mjs https://codesign.qq.com/app/s/xxx --text
  node extract.mjs https://codesign.qq.com/app/s/xxx --scroll-screenshots
`);
}

// ============================================================================
// Main
// ============================================================================

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) { showHelp(); process.exit(0); }
  if (!args.url) { console.error('[错误] 请提供 URL 或项目 ID'); showHelp(); process.exit(1); }

  const outputDir = path.resolve(args.output);
  console.log('[Codesign] 数据提取工具');
  console.log('  URL:', args.url);
  console.log('  输出:', outputDir);

  await ensureDependencies();

  let playwright = null;
  if (isPlaywrightAvailable()) {
    playwright = await loadPlaywright();
    console.log('  [OK] Playwright 已加载');
  } else if (!args.useApi) {
    console.error('[错误] Playwright 不可用，请使用 --use-api 或安装 Playwright');
    process.exit(1);
  }

  fs.mkdirSync(outputDir, { recursive: true });

  // Try API mode first if requested
  if (args.useApi && getApiToken(args)) {
    console.log('\n[API] 使用 Codesign Open API 模式');
    try {
      // TODO: Implement API extraction
      console.log('  [提示] API 模式开发中，暂使用浏览器模式');
    } catch (e) {
      console.error('  [错误] API 模式失败:', e.message);
    }
  }

  // Browser mode
  if (playwright) {
    console.log('\n[浏览器] 使用 Playwright 模式');
    const browserOpts = {
      headless: args.headless,
      connectCdp: args.connectCdp,
      viewport: args.viewport,
      wait: args.wait,
    };

    const baseUrl = args.url.startsWith('http') ? args.url : `https://codesign.qq.com/prototype/${args.url}`;

    // Step 1: Open the initial page and discover all pages
    console.log('\n[发现] 正在发现原型中的所有页面...');
    const browser = await getBrowser(playwright, browserOpts);
    const context = await browser.newContext({
      viewport: browserOpts.viewport || { width: 1440, height: 900 },
    });
    const page = await context.newPage();

    try {
      await page.goto(baseUrl, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForTimeout(browserOpts.wait || 2000);

      const pages = await discoverPages(page);

      if (pages.length === 0) {
        console.log('  [警告] 未发现其他页面，仅处理当前页面');
        pages.push({
          name: '首页',
          url: baseUrl,
          method: 'default',
          index: 0,
        });
      }

      console.log(`\n[处理] 共发现 ${pages.length} 个页面，开始逐个处理...`);

      // Step 2: Process each page
      for (let i = 0; i < pages.length; i++) {
        const p = pages[i];
        console.log(`\n${'='.repeat(50)}`);
        console.log(`[页面 ${i + 1}/${pages.length}] ${p.name}`);

        const pageDir = path.join(outputDir, `${i + 1}_${p.name.replace(/[\/\\:*?"<>|]/g, '_')}`);
        fs.mkdirSync(pageDir, { recursive: true });

        let pageUrl = p.url || baseUrl;

        // Navigate to the page
        try {
          if (p.method === 'nav-link' && p.url) {
            console.log(`  [导航] 通过链接导航到: ${p.url}`);
            await page.goto(p.url, { waitUntil: 'networkidle', timeout: 60000 });
          } else if (p.method === 'tab-button' && p.selector) {
            console.log(`  [导航] 通过点击标签页导航: ${p.selector}`);
            await page.click(p.selector);
          } else if (p.method === 'page-list' && p.action) {
            console.log(`  [导航] 通过页面列表导航: ${p.action}`);
            await page.evaluate((action) => {
              eval(action);
            }, p.action);
          } else {
            console.log(`  [导航] 使用默认 URL: ${pageUrl}`);
            if (page.url() !== pageUrl) {
              await page.goto(pageUrl, { waitUntil: 'networkidle', timeout: 60000 });
            }
          }

          await page.waitForTimeout(browserOpts.wait || 2000);

          // Step 3: Capture screenshots (with scrolling if needed)
          if (args.screenshot) {
            console.log(`  [截图] 捕获页面截图...`);
            try {
              if (args.scrollScreenshots) {
                // 滚动截图模式：截取多张图片
                const baseName = `screenshot`;
                const screenshots = await captureScrollableScreenshots(
                  playwright,
                  page.url(),
                  pageDir,
                  baseName,
                  { ...browserOpts, page: page }
                );
                console.log(`    [完成] 共截取 ${screenshots.length} 张图片`);
              } else {
                // 普通截图模式：截取单张全页图
                const screenshotPath = path.join(pageDir, 'screenshot.png');
                await page.screenshot({ path: screenshotPath, fullPage: true, type: 'png' });
                console.log(`    [完成] 截图已保存: ${path.basename(screenshotPath)}`);
              }
            } catch (e) {
              console.error(`    [错误] 截图失败:`, e.message);
            }
          }

          // Step 4: Extract theme tokens
          console.log(`  [主题] 提取设计 Token...`);
          try {
            const tokens = await page.evaluate(() => {
              // (Same theme extraction logic as extractThemeTokens)
              const bucket = () => new Map();

              const add = (b, v, t) => {
                if (!v) return;
                if (!b.has(v)) b.set(v, { count: 0, tags: new Set() });
                const item = b.get(v);
                item.count++;
                if (t) item.tags.add(t);
              };

              const isClear = (v) => {
                if (!v) return false;
                const l = v.trim().toLowerCase();
                return l === 'transparent' || l === 'rgba(0, 0, 0, 0)' || l === 'rgba(0,0,0,0)';
              };

              const isZero = (v) => {
                if (!v) return false;
                const t = v.trim();
                return t === '0' || t === '0px';
              };

              const colors = { bg: bucket(), text: bucket(), border: bucket() };
              const typo = { family: bucket(), style: bucket() };
              const spacing = bucket(), radius = bucket();

              // Get CSS variables
              const cssVars = {};
              try {
                const rootStyle = getComputedStyle(document.documentElement);
                for (let i = 0; i < rootStyle.length; i++) {
                  const prop = rootStyle[i];
                  if (prop.startsWith('--')) {
                    cssVars[prop] = rootStyle.getPropertyValue(prop).trim();
                  }
                }
              } catch (e) {}

              // Walk DOM
              const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
              let el = walker.currentNode;
              let count = 0;
              while (el && count < 3000) {
                const tag = el.tagName?.toLowerCase() || '';
                const s = getComputedStyle(el);

                if (s.backgroundColor && !isClear(s.backgroundColor)) add(colors.bg, s.backgroundColor, tag);
                if (s.color && !isClear(s.color)) add(colors.text, s.color, tag);
                if (s.borderColor && !isClear(s.borderColor)) add(colors.border, s.borderColor, tag);

                add(typo.family, s.fontFamily, tag);
                if (s.fontSize && s.fontWeight && s.lineHeight) {
                  add(typo.style, `${s.fontSize}|${s.lineHeight}|${s.fontWeight}`, tag);
                }

                if (s.margin && !isZero(s.margin)) add(spacing, s.margin, tag);
                if (s.padding && !isZero(s.padding)) add(spacing, s.padding, tag);
                if (s.borderRadius && !isZero(s.borderRadius)) add(radius, s.borderRadius, tag);

                el = walker.nextNode();
                count++;
              }

              const sort = (b) => [...b.entries()]
                .sort((a, b) => b[1].count - a[1].count)
                .slice(0, 10)
                .map(([v, { count, tags }]) => ({ value: v, count, tags: [...tags] }));

              return {
                colors: {
                  background: sort(colors.bg),
                  text: sort(colors.text),
                  border: sort(colors.border),
                },
                typography: {
                  families: sort(typo.family),
                  textStyles: sort(typo.style).map(({ value, count, tags }) => {
                    const [size, lineHeight, weight] = value.split('|');
                    return { size, lineHeight, weight, count, tags };
                  }),
                },
                spacing: sort(spacing),
                radius: sort(radius),
                cssVariables: Object.keys(cssVars).length > 0 ? cssVars : undefined,
              };
            });

            fs.writeFileSync(path.join(pageDir, 'theme.json'), JSON.stringify(tokens, null, 2));
            console.log(`    [OK] 主题 → theme.json`);
          } catch (e) {
            console.error(`    [错误] 主题提取失败:`, e.message);
          }

          // Step 5: Extract page text
          if (args.text || args.advanced) {
            console.log(`  [文本] 提取页面文本...`);
            try {
              const textContent = await page.evaluate(() => {
                const clone = document.body.cloneNode(true);
                clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());

                const text = clone.innerText || clone.textContent || '';

                return text
                  .split('\n')
                  .map(line => line.trim())
                  .filter(line => line.length > 0)
                  .join('\n');
              });

              fs.writeFileSync(path.join(pageDir, 'content.md'), textContent);
              console.log(`    [OK] 文本 → content.md`);
            } catch (e) {
              console.error(`    [错误] 文本提取失败:`, e.message);
            }
          }

        } catch (e) {
          console.error(`  [错误] 处理页面失败:`, e.message);
        }
      }

      await context.close();
    } catch (e) {
      console.error('[错误] 页面发现失败:', e.message);
    }

    await closeBrowser();
  }

  console.log(`\n${'='.repeat(50)}`);
  console.log('[完成] 提取完成！');
  console.log('  输出:', outputDir);
}

main().catch((e) => {
  console.error('[致命错误]', e);
  closeBrowser().then(() => process.exit(1));
});
