#!/usr/bin/env node
/**
 * clone-codesign-page.mjs
 * Progressive page cloning CLI for Tencent Codesign
 *
 * Usage:
 *   node clone.mjs <url> <command> [options]
 *
 * Commands:
 *   init       Phase 1: screenshot + meta + design tokens
 *   skeleton   Phase 2: DOM skeleton tree
 *   styles     Phase 3: section styles
 *   interact   Phase 4: interaction states (hover/click)
 *   responsive Phase 5: multi-viewport screenshots
 *   assets     Phase 6: download images/fonts
 *   quick      quick mode: init + skeleton
 *   full       full mode: all phases
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ============================================================================
// Environment: auto-install playwright
// ============================================================================

function getRunnerDir() {
  const home = process.env.USERPROFILE || process.env.HOME || '.';
  return path.join(home, '.cache', 'codesign-clone');
}

const RUNNER_DIR = getRunnerDir();

async function ensureDependencies() {
  const pkgPath = path.join(RUNNER_DIR, 'node', 'playwright');
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
    throw e;
  }

  try {
    execSync(`${npxCmd} playwright install chromium`, { cwd: RUNNER_DIR, stdio: 'inherit', env });
  } catch (e) {
    console.warn('[警告] Chromium 安装失败，将尝试使用系统浏览器');
  }

  console.log('[完成] Playwright 安装完成');
}

function isPlaywrightAvailable() {
  return fs.existsSync(path.join(RUNNER_DIR, 'node', 'playwright'));
}

async function loadPlaywright() {
  const pwPath = path.join(RUNNER_DIR, 'node', 'playwright', 'index.mjs');
  if (!fs.existsSync(pwPath)) return null;
  return import(pwPath);
}

// ============================================================================
// Browser management
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

// ============================================================================
// Commands
// ============================================================================

async function runInit(playwright, url, outputDir, options = {}) {
  console.log('\n[Phase 1] 初始化：截图 + 元信息 + 设计令牌');
  
  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({
    viewport: options.viewport || { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  try {
    console.log('  [打开]', url);
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 2000);

    // Screenshot
    const screenshotPath = path.join(outputDir, 'screenshot.png');
    await page.screenshot({ path: screenshotPath, fullPage: true, type: 'png' });
    console.log('  [截图] screenshot.png');

    // Meta
    const meta = {
      url: page.url(),
      title: await page.title(),
      timestamp: new Date().toISOString(),
      viewport: options.viewport || { width: 1440, height: 900 },
    };
    fs.writeFileSync(path.join(outputDir, 'meta.json'), JSON.stringify(meta, null, 2));
    console.log('  [元信息] meta.json');

    // Theme tokens
    const theme = await page.evaluate(() => {
      const colors = { bg: new Map(), text: new Map(), border: new Map() };
      const fonts = new Map();
      
      const walk = (node) => {
        if (node.nodeType !== 1) return;
        const s = window.getComputedStyle(node);
        const tag = node.tagName?.toLowerCase();
        
        if (s.backgroundColor && s.backgroundColor !== 'rgba(0, 0, 0, 0)') {
          const v = s.backgroundColor;
          if (!colors.bg.has(v)) colors.bg.set(v, { count: 0, tags: new Set() });
          const item = colors.bg.get(v);
          item.count++;
          if (tag) item.tags.add(tag);
        }
        
        if (s.color && s.color !== 'rgba(0, 0, 0, 0)') {
          const v = s.color;
          if (!colors.text.has(v)) colors.text.set(v, { count: 0, tags: new Set() });
          const item = colors.text.get(v);
          item.count++;
          if (tag) item.tags.add(tag);
        }
        
        if (s.fontFamily) {
          const v = s.fontFamily;
          if (!fonts.has(v)) fonts.set(v, { count: 0 });
          fonts.get(v).count++;
        }
        
        for (const child of node.children) walk(child);
      };
      
      walk(document.body);
      
      const toArray = (m) => [...m.entries()]
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 10)
        .map(([v, { count, tags }]) => ({ value: v, count, tags: [...tags] }));
      
      return {
        colors: {
          background: toArray(colors.bg),
          text: toArray(colors.text),
          border: toArray(colors.border),
        },
        typography: {
          families: toArray(fonts),
        },
      };
    });
    
    fs.writeFileSync(path.join(outputDir, 'theme.json'), JSON.stringify(theme, null, 2));
    console.log('  [主题] theme.json');

    console.log('\n✅ Phase 1 完成');
  } finally {
    await context.close();
  }
}

async function runSkeleton(playwright, url, outputDir, options = {}) {
  console.log('\n[Phase 2] DOM 骨架树');
  
  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({
    viewport: options.viewport || { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 2000);

    const skeleton = await page.evaluate(() => {
      function walk(node, depth = 0) {
        if (depth > 10) return null;
        if (node.nodeType === 3) {
          const text = node.textContent?.trim();
          if (!text) return null;
          return { type: 'text', text: text.slice(0, 100) };
        }
        if (node.nodeType !== 1) return null;
        
        const tag = node.tagName?.toLowerCase();
        if (['script', 'style', 'noscript'].includes(tag)) return null;
        
        const s = window.getComputedStyle(node);
        if (s.display === 'none' || s.visibility === 'hidden') return null;
        
        const item = {
          tag,
          id: node.id || undefined,
          classes: node.className ? node.className.split(' ').filter(Boolean) : undefined,
          text: node.innerText?.trim()?.slice(0, 100) || undefined,
          children: [],
        };
        
        for (const child of node.children) {
          const sub = walk(child, depth + 1);
          if (sub) item.children.push(sub);
        }
        
        if (item.children.length === 0) delete item.children;
        return item;
      }
      
      return walk(document.body);
    });

    fs.writeFileSync(path.join(outputDir, 'skeleton.json'), JSON.stringify(skeleton, null, 2));
    console.log('  [骨架] skeleton.json');
    console.log('\n✅ Phase 2 完成');
  } finally {
    await context.close();
  }
}

async function runStyles(playwright, url, outputDir, options = {}) {
  console.log('\n[Phase 3] 指定区域样式');
  
  const selector = options.selector;
  if (!selector) {
    console.error('  [错误] 需要 --selector 参数');
    return;
  }
  
  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({
    viewport: options.viewport || { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 2000);

    const sectionName = selector.replace(/[^a-zA-Z0-9]/g, '-');
    const sectionDir = path.join(outputDir, 'sections', sectionName);
    fs.mkdirSync(sectionDir, { recursive: true });

    // Screenshot of selector
    try {
      const el = await page.$(selector);
      if (el) {
        const screenshotPath = path.join(sectionDir, 'screenshot.png');
        await el.screenshot({ path: screenshotPath });
        console.log('  [截图]', path.join('sections', sectionName, 'screenshot.png'));
      }
    } catch (e) {
      console.warn('  [警告] 截图失败:', e.message);
    }

    // Extract styles
    const data = await page.evaluate((sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      
      const s = window.getComputedStyle(el);
      const styles = {};
      for (let i = 0; i < s.length; i++) {
        const prop = s[i];
        styles[prop] = s.getPropertyValue(prop);
      }
      
      return {
        selector: sel,
        tag: el.tagName?.toLowerCase(),
        styles,
        bbox: el.getBoundingClientRect(),
        children: [...el.children].slice(0, 20).map(child => ({
          tag: child.tagName?.toLowerCase(),
          id: child.id || undefined,
          classes: child.className ? child.className.split(' ').filter(Boolean) : undefined,
        })),
      };
    }, selector);

    if (data) {
      fs.writeFileSync(path.join(sectionDir, 'data.json'), JSON.stringify(data, null, 2));
      console.log('  [样式]', path.join('sections', sectionName, 'data.json'));
    }

    console.log('\n✅ Phase 3 完成');
  } finally {
    await context.close();
  }
}

// ============================================================================
// CLI
// ============================================================================

function parseArgs(argv) {
  const args = {
    url: null,
    command: null,
    output: './clone-data',
    selector: null,
    viewport: { width: 1440, height: 900 },
    wait: 2000,
    headless: true,
    connectCdp: null,
    verbose: false,
    help: false,
  };

  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') args.help = true;
    else if (arg === '-o' || arg === '--output') args.output = argv[++i];
    else if (arg === '--selector') args.selector = argv[++i];
    else if (arg === '--viewport') {
      const [w, h] = (argv[++i] || '1440x900').split('x').map(Number);
      args.viewport = { width: w || 1440, height: h || 900 };
    }
    else if (arg === '--wait') args.wait = parseInt(argv[++i]) || 2000;
    else if (arg === '--no-headless') args.headless = false;
    else if (arg === '--connect-cdp') args.connectCdp = argv[++i];
    else if (arg === '--verbose') args.verbose = true;
    else if (!arg.startsWith('-')) {
      if (!args.url) args.url = arg;
      else if (!args.command) args.command = arg;
    }
  }

  return args;
}

function showHelp() {
  console.log(`
CoDesign 页面克隆工具

用法:
  node clone.mjs <url> <command> [options]

命令:
  init        截图 + 元信息 + 设计令牌
  skeleton    DOM 骨架树
  styles      指定区域样式 (需要 --selector)
  interact    交互态截图 (开发中)
  responsive  多视口截图 (开发中)
  assets      下载资源 (开发中)
  quick       init + skeleton
  full        init + skeleton + responsive + assets

选项:
  -o, --output DIR    输出目录 (默认: ./clone-data)
  --selector SEL       指定区域 (用于 styles)
  --viewport WxH       视口大小 (默认: 1440x900)
  --wait MS            等待时间 (默认: 2000)
  --no-headless        显示浏览器
  --connect-cdp URL    连接 Chrome (复用登录态)
  --verbose            详细日志
  -h, --help          帮助

示例:
  # 快速模式
  node clone.mjs https://codesign.qq.com/prototype/xxx quick -o ./clone-data

  # 指定区域样式
  node clone.mjs https://codesign.qq.com/prototype/xxx styles --selector "header" -o ./clone-data
`);
}

// ============================================================================
// Main
// ============================================================================

async function main() {
  const args = parseArgs(process.argv);
  if (args.help) { showHelp(); process.exit(0); }
  if (!args.url) { console.error('[错误] 请提供 URL'); showHelp(); process.exit(1); }
  if (!args.command) { console.error('[错误] 请提供命令'); showHelp(); process.exit(1); }

  const outputDir = path.resolve(args.output);
  console.log('[CoDesign 克隆]');
  console.log('  URL:', args.url);
  console.log('  命令:', args.command);
  console.log('  输出:', outputDir);

  await ensureDependencies();
  
  if (!isPlaywrightAvailable()) {
    console.error('[错误] Playwright 不可用');
    process.exit(1);
  }

  const playwright = await loadPlaywright();
  if (!playwright) {
    console.error('[错误] 加载 Playwright 失败');
    process.exit(1);
  }

  fs.mkdirSync(outputDir, { recursive: true });

  const options = {
    headless: args.headless,
    connectCdp: args.connectCdp,
    viewport: args.viewport,
    wait: args.wait,
  };

  try {
    if (args.command === 'init' || args.command === 'quick' || args.command === 'full') {
      await runInit(playwright, args.url, outputDir, options);
    }

    if (args.command === 'skeleton' || args.command === 'quick' || args.command === 'full') {
      await runSkeleton(playwright, args.url, outputDir, options);
    }

    if (args.command === 'styles') {
      await runStyles(playwright, args.url, outputDir, { ...options, selector: args.selector });
    }

    if (args.command === 'full') {
      console.log('\n[提示] interact/responsive/assets 命令开发中...');
    }

    console.log(`\n${'='.repeat(50)}`);
    console.log('✅ 完成！');
    console.log('  输出:', outputDir);
  } finally {
    await closeBrowser();
  }
}

main().catch((e) => {
  console.error('[致命错误]', e);
  closeBrowser().then(() => process.exit(1));
});
