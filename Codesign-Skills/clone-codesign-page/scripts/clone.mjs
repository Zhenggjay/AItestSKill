#!/usr/bin/env node
/**
 * clone-codesign-page.mjs v2
 *
 * 改进：
 *   - 新增 section 命令：提取指定目录路径下所有页面
 *   - icon class 识别文件夹/页面（icon-v2-folder-open vs icon-v2-page）
 *   - 路径表达式支持（S9/MCP服务）
 *   - 自适应缩放截图（根据内容尺寸自动计算缩放）
 *   - 系统 Chrome 无头模式（不需要手动启动浏览器）
 *
 * Usage:
 *   node clone.mjs <url> <command> [options]
 *
 * Commands:
 *   section    🆕 提取指定目录路径下所有页面（截图+skeleton+文本+主题）
 *   init       截图 + 元信息 + 设计令牌
 *   skeleton   DOM 骨架树
 *   styles     指定区域样式
 *   interact   交互态截图 (开发中)
 *   responsive 多视口截图 (开发中)
 *   assets     下载资源 (开发中)
 *   quick      init + skeleton
 *   full       init + skeleton + responsive + assets
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
  return path.join(home, '.cache', 'codesign-extractor');
}

const RUNNER_DIR = getRunnerDir();

async function ensureDependencies() {
  // 优先使用 codesign-extractor 的 Playwright（已安装）
  const extractorPw = path.join(RUNNER_DIR, 'node_modules', 'playwright', 'index.mjs');
  if (fs.existsSync(extractorPw)) return;

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
  try {
    execSync(`${npmCmd} install playwright`, { cwd: RUNNER_DIR, stdio: 'inherit', env });
  } catch (e) {
    console.error('[错误] Playwright 安装失败:', e.message);
    throw e;
  }
  console.log('[完成] Playwright 安装完成');
}

function isPlaywrightAvailable() {
  return fs.existsSync(path.join(RUNNER_DIR, 'node_modules', 'playwright', 'index.mjs'));
}

async function loadPlaywright() {
  const pwPath = path.join(RUNNER_DIR, 'node_modules', 'playwright', 'index.mjs');
  if (!fs.existsSync(pwPath)) return null;
  // Windows 上需要 file:// URL 格式
  const { pathToFileURL } = await import('node:url');
  return import(pathToFileURL(pwPath).href);
}

// ============================================================================
// 改进1：系统 Chrome 支持
// ============================================================================

function findSystemChrome() {
  const paths = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Users\\801080\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe',
  ];
  for (const p of paths) {
    if (fs.existsSync(p)) return p;
  }
  return null;
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
    // 改进：优先使用系统 Chrome
    const chromePath = findSystemChrome();
    const launchOpts = {
      headless,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    };
    if (chromePath) {
      launchOpts.executablePath = chromePath;
      console.log('[浏览器] 使用系统 Chrome:', chromePath);
    }
    _browser = await playwright.chromium.launch(launchOpts);
  }
  return _browser;
}

async function closeBrowser() {
  if (_browser) { await _browser.close().catch(() => {}); _browser = null; }
}

// ============================================================================
// 改进2：icon class 识别节点类型
// ============================================================================

const IDENTIFY_JS = `
(() => {
  const items = document.querySelectorAll('.t-tree__item');
  const results = [];
  items.forEach((item, i) => {
    const lines = (item.innerText || '').trim().split(/\\r?\\n/).map(l => l.trim()).filter(l => l);
    const name = lines[0] || '';
    if (!name || name.length >= 60) return;

    // 精确匹配 icon class
    const folderIcon = item.querySelector('.icon-v2-folder-open, .icon-v2-folder');
    const pageIcon = item.querySelector('.icon-v2-page');
    let type = 'page';
    if (pageIcon) type = 'page';
    else if (folderIcon) type = 'folder';

    const style = getComputedStyle(item);
    const indent = parseInt(style.paddingLeft || style.marginLeft || '0', 10);
    results.push({ index: i, name, type, indent });
  });
  return results;
})()
`;

// ============================================================================
// 改进3：路径表达式解析
// ============================================================================

function resolveSectionPath(tree, sectionPath) {
  const segments = sectionPath.split('/').map(s => s.trim()).filter(s => s);
  let searchStart = 0;
  let searchEnd = tree.length;
  let lastFound = null;  // 路径终点节点（文件夹或页面）

  for (const seg of segments) {
    const found = tree.find(n =>
      n.index >= searchStart && n.index < searchEnd && n.name === seg
    );
    if (!found) {
      const available = tree
        .filter(n => n.index >= searchStart && n.index < searchEnd)
        .map(n => `${n.type === 'folder' ? '📁' : '📄'} ${n.name}`);
      throw new Error(`路径段 "${seg}" 未找到。可用:\n  ${available.join('\n  ')}`);
    }
    lastFound = found;
    searchStart = found.index + 1;
    searchEnd = tree.length;
    for (let i = found.index + 1; i < tree.length; i++) {
      if (tree[i].indent <= found.indent) {
        searchEnd = i;
        break;
      }
    }
  }

  const pages = tree.filter(n => n.index >= searchStart && n.index < searchEnd && n.type === 'page');
  const folders = tree.filter(n => n.index >= searchStart && n.index < searchEnd && n.type === 'folder');
  return { pages, folders, sectionNode: lastFound };
}

// ============================================================================
// 改进4+5：section 命令（自适应缩放截图 + 逐页提取）
// ============================================================================

async function runSection(playwright, url, outputDir, options = {}) {
  console.log('\n[Section] 提取指定目录路径下所有页面');

  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({
    viewport: options.viewport || { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  try {
    console.log('  [打开]', url);
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 3000);
    console.log('  [标题]', await page.title());

    // 识别页面树
    console.log('\n  [识别] 页面树结构...');
    const tree = await page.evaluate(IDENTIFY_JS);
    const folders = tree.filter(n => n.type === 'folder');
    const pages = tree.filter(n => n.type === 'page');
    console.log(`  总节点: ${tree.length}（文件夹: ${folders.length}, 页面: ${pages.length}）`);

    // 仅列出模式
    if (options.listOnly) {
      fs.mkdirSync(outputDir, { recursive: true });
      fs.writeFileSync(path.join(outputDir, 'sitemap.json'), JSON.stringify(tree, null, 2), 'utf-8');
      console.log('\n[完成] sitemap.json 已保存');
      return;
    }

    // 解析 section 路径
    let targetPages, targetFolders, sectionNode;
    if (options.section) {
      try {
        const resolved = resolveSectionPath(tree, options.section);
        targetPages = resolved.pages;
        targetFolders = resolved.folders;
        sectionNode = resolved.sectionNode;  // 路径终点节点（文件夹或页面）
        console.log(`\n  ${options.section} 下: ${targetFolders.length} 文件夹, ${targetPages.length} 页面`);
        if (sectionNode) console.log(`  路径终点: ${sectionNode.type === 'folder' ? '📁' : '📄'} ${sectionNode.name}`);
        targetPages.forEach(p => console.log(`    📄 ${p.name}`));
        targetFolders.forEach(f => console.log(`    📁 ${f.name}`));
      } catch (e) {
        console.error(`[错误] ${e.message}`);
        return;
      }
    } else {
      targetPages = pages;
      targetFolders = folders;
      console.log(`\n  提取全部 ${pages.length} 个页面`);
    }

    // 截图列表 = 路径终点节点（文件夹或页面都要截图） + 所有子页面 + 所有子文件夹（也截图）
    let screenshotNodes = [];
    // 路径终点节点（无论文件夹还是页面，都要截图——CoDesign中文件夹点击后也会切换画布）
    if (sectionNode) {
      screenshotNodes.push({ ...sectionNode, isSectionNode: true });
    }
    // 子文件夹也截图
    targetFolders.forEach(f => {
      if (!sectionNode || f.index !== sectionNode.index) screenshotNodes.push(f);
    });
    // 子页面截图
    targetPages.forEach(p => {
      if (!sectionNode || p.index !== sectionNode.index) screenshotNodes.push(p);
    });

    // 展开文件夹
    if (targetFolders.length > 0) {
      const folderIndices = targetFolders.map(f => f.index);
      await page.evaluate((indices) => {
        const items = document.querySelectorAll('.t-tree__item');
        indices.forEach(idx => { if (items[idx]) items[idx].click(); });
      }, folderIndices);
      await page.waitForTimeout(2000);
    }

    // 逐页提取（包括文件夹节点）
    const sectionName = options.section ? options.section.replace(/[\\/:*?"<>|]/g, '_') : 'all';
    const pagesDir = path.join(outputDir, sectionName);

    for (let i = 0; i < screenshotNodes.length; i++) {
      const pg = screenshotNodes[i];
      const safeName = pg.name.replace(/[\\/:*?"<>|]/g, '_');
      const nodeType = pg.type === 'folder' ? '📁' : '📄';
      console.log(`\n  [${i + 1}/${screenshotNodes.length}] ${nodeType} ${pg.name}`);

      // 点击页面节点
      await page.evaluate((idx) => {
        const items = document.querySelectorAll('.t-tree__item');
        if (items[idx]) items[idx].click();
      }, pg.index);
      await page.waitForTimeout(options.wait || 3000);

      const pageDir = path.join(pagesDir, safeName);
      fs.mkdirSync(pageDir, { recursive: true });

      // 改进4：自适应缩放截图
      console.log('    [截图] 自适应缩放...');
      try {
        const frames = page.frames();
        const protoFrame = frames.find(f => f.url().includes('blob:') || f.url().includes('prototype'));

        if (protoFrame) {
          // 获取 iframe 原始内容尺寸
          const rawDims = await protoFrame.evaluate(() => ({
            scrollW: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
            scrollH: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight),
            clientW: document.documentElement.clientWidth,
            clientH: document.documentElement.clientHeight,
          }));

          // 计算自适应缩放
          const MIN_ZOOM = 0.3;
          const zoomW = rawDims.clientW / rawDims.scrollW;
          const zoomH = rawDims.clientH / rawDims.scrollH;
          let autoZoom = Math.min(zoomW, zoomH, 1.0);
          autoZoom = Math.max(autoZoom, MIN_ZOOM);

          await protoFrame.evaluate(z => { document.body.style.zoom = String(z); }, autoZoom);
          await page.waitForTimeout(800);

          // 获取 iframe 在页面中的位置
          const iframeRect = await page.evaluate(() => {
            const iframe = document.querySelector('iframe');
            if (!iframe) return null;
            const r = iframe.getBoundingClientRect();
            return { x: r.x, y: r.y, width: r.width, height: r.height };
          });

          if (iframeRect) {
            await page.screenshot({
              path: path.join(pageDir, 'screenshot.png'),
              type: 'png',
              clip: { x: iframeRect.x, y: iframeRect.y, width: iframeRect.width, height: iframeRect.height },
            });
          } else {
            await page.screenshot({ path: path.join(pageDir, 'screenshot.png'), fullPage: true, type: 'png' });
          }

          const visualW = Math.round(rawDims.scrollW * autoZoom);
          const visualH = Math.round(rawDims.scrollH * autoZoom);
          console.log(`    [完成] 缩放=${autoZoom.toFixed(2)} (${rawDims.scrollW}x${rawDims.scrollH} → ${visualW}x${visualH})`);
        } else {
          await page.screenshot({ path: path.join(pageDir, 'screenshot.png'), fullPage: true, type: 'png' });
          console.log('    [完成] fullPage模式');
        }
      } catch (e) {
        console.error(`    [错误] 截图失败:`, e.message);
      }

      // 提取页面文本（优化：优先从 iframe 内部提取，获取真实原型内容）
      try {
        const frames = page.frames();
        const protoFrame = frames.find(f => f.url().includes('blob:') || f.url().includes('prototype'));
        let text = '';
        if (protoFrame) {
          // 从 iframe 内部提取文本（真实原型内容，不是外层导航树）
          try {
            text = await protoFrame.evaluate(() => {
              const clone = document.body.cloneNode(true);
              clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
              return (clone.innerText || '').split('\n').map(l => l.trim()).filter(l => l.length > 0).join('\n');
            });
          } catch (e) {
            // iframe 跨域时降级为外层文本
            console.log('    [提示] iframe跨域，降级为外层文本');
          }
        }
        if (!text) {
          text = await page.evaluate(() => {
            const clone = document.body.cloneNode(true);
            clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
            return (clone.innerText || '').split('\n').map(l => l.trim()).filter(l => l.length > 0).join('\n');
          });
        }
        fs.writeFileSync(path.join(pageDir, 'content.md'), text, 'utf-8');
        console.log(`    [文本] ${text.length} 字符${protoFrame ? ' (iframe内部)' : ' (外层)'}`);
      } catch (e) {
        console.error(`    [错误] 文本提取失败:`, e.message);
      }

      // 提取设计令牌
      try {
        const theme = await page.evaluate(() => {
          const colors = { bg: new Map(), text: new Map() };
          const fonts = new Map();
          const walk = (node) => {
            if (node.nodeType !== 1) return;
            const s = window.getComputedStyle(node);
            const tag = node.tagName?.toLowerCase();
            if (s.backgroundColor && s.backgroundColor !== 'rgba(0, 0, 0, 0)') {
              if (!colors.bg.has(s.backgroundColor)) colors.bg.set(s.backgroundColor, { count: 0, tags: new Set() });
              colors.bg.get(s.backgroundColor).count++;
              if (tag) colors.bg.get(s.backgroundColor).tags.add(tag);
            }
            if (s.color && s.color !== 'rgba(0, 0, 0, 0)') {
              if (!colors.text.has(s.color)) colors.text.set(s.color, { count: 0, tags: new Set() });
              colors.text.get(s.color).count++;
              if (tag) colors.text.get(s.color).tags.add(tag);
            }
            if (s.fontFamily) {
              if (!fonts.has(s.fontFamily)) fonts.set(s.fontFamily, 0);
              fonts.set(s.fontFamily, fonts.get(s.fontFamily) + 1);
            }
            for (const child of node.children) walk(child);
          };
          walk(document.body);
          const toArray = (m) => [...m.entries()].sort((a, b) => b[1].count - a[1].count).slice(0, 10).map(([v, { count, tags }]) => ({ value: v, count, tags: tags ? [...tags] : [] }));
          const fontsArray = [...fonts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([v, count]) => ({ value: v, count }));
          return { colors: { background: toArray(colors.bg), text: toArray(colors.text) }, typography: { families: fontsArray } };
        });
        fs.writeFileSync(path.join(pageDir, 'theme.json'), JSON.stringify(theme, null, 2), 'utf-8');
        console.log('    [主题] theme.json');
      } catch (e) {
        console.error(`    [错误] 主题提取失败:`, e.message);
      }

      // 优化2：交互态截图（--interact 选项）
      // 自动检测 iframe 内部可 hover 的卡片/按钮，截图交互态
      if (options.interact) {
        console.log('    [交互态] 检测可hover元素...');
        try {
          const frames = page.frames();
          const protoFrame = frames.find(f => f.url().includes('blob:') || f.url().includes('prototype'));
          if (protoFrame) {
            // 查找 iframe 内部可 hover 的元素（卡片、行、按钮）
            const hoverTargets = await protoFrame.evaluate(() => {
              const targets = [];
              // 常见可 hover 元素：卡片、列表项、操作按钮
              const selectors = [
                '[class*="card"]', '[class*="item"]', '[class*="row"]',
                'button', '[class*="btn"]', '[class*="action"]',
                '[class*="hover"]', '[class*="operate"]'
              ];
              const seen = new Set();
              for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                els.forEach((el, i) => {
                  const rect = el.getBoundingClientRect();
                  // 只选可见且有尺寸的元素
                  if (rect.width > 50 && rect.height > 20 && rect.width < 2000) {
                    const key = `${sel}_${i}`;
                    if (!seen.has(key) && targets.length < 5) {  // 最多截5个交互态
                      seen.add(key);
                      targets.push({ selector: sel, index: i, x: rect.x + rect.width/2, y: rect.y + rect.height/2 });
                    }
                  }
                });
              }
              return targets;
            }).catch(() => []);

            if (hoverTargets.length > 0) {
              const interactDir = path.join(pageDir, 'interactions');
              fs.mkdirSync(interactDir, { recursive: true });
              const iframeRect = await page.evaluate(() => {
                const iframe = document.querySelector('iframe');
                if (!iframe) return null;
                const r = iframe.getBoundingClientRect();
                return { x: r.x, y: r.y, width: r.width, height: r.height };
              });

              for (let h = 0; h < Math.min(hoverTargets.length, 3); h++) {
                const target = hoverTargets[h];
                try {
                  // 在 iframe 内部 hover 元素
                  await protoFrame.evaluate(({ selector, index }) => {
                    const els = document.querySelectorAll(selector);
                    if (els[index]) {
                      els[index].dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                      els[index].dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                    }
                  }, { selector: target.selector, index: target.index });
                  await page.waitForTimeout(1000);

                  if (iframeRect) {
                    await page.screenshot({
                      path: path.join(interactDir, `hover_${h + 1}.png`),
                      type: 'png',
                      clip: { x: iframeRect.x, y: iframeRect.y, width: iframeRect.width, height: iframeRect.height },
                    });
                  }
                  console.log(`    [交互态] hover_${h + 1}.png (${target.selector}[${target.index}])`);

                  // 移除 hover
                  await protoFrame.evaluate(({ selector, index }) => {
                    const els = document.querySelectorAll(selector);
                    if (els[index]) {
                      els[index].dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
                    }
                  }, { selector: target.selector, index: target.index });
                  await page.waitForTimeout(500);
                } catch (e) {
                  // 忽略单个交互态失败
                }
              }
            } else {
              console.log('    [交互态] 未检测到可hover元素');
            }
          }
        } catch (e) {
          console.log(`    [交互态] 跳过: ${e.message.substring(0, 80)}`);
        }
      }
    }

    // 保存 sitemap
    const folderCount = screenshotNodes.filter(n => n.type === 'folder').length;
    const pageCount = screenshotNodes.filter(n => n.type === 'page').length;
    fs.writeFileSync(path.join(outputDir, 'sitemap.json'), JSON.stringify({
      section: options.section,
      sectionNode: sectionNode || null,
      folders: targetFolders,
      pages: targetPages,
      screenshotNodes: screenshotNodes.map(n => ({ name: n.name, type: n.type, index: n.index })),
      summary: { total: screenshotNodes.length, folders: folderCount, pages: pageCount },
    }, null, 2), 'utf-8');

    console.log(`\n${'='.repeat(50)}`);
    console.log(`✅ 完成！共截图 ${screenshotNodes.length} 个节点（${folderCount} 文件夹 + ${pageCount} 页面）`);
    console.log('  输出:', pagesDir);
  } finally {
    await context.close();
  }
}

// ============================================================================
// 原有命令：init / skeleton / styles
// ============================================================================

async function runInit(playwright, url, outputDir, options = {}) {
  console.log('\n[Phase 1] 初始化：截图 + 元信息 + 设计令牌');
  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({ viewport: options.viewport || { width: 1440, height: 900 } });
  const page = await context.newPage();
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 2000);
    const screenshotPath = path.join(outputDir, 'screenshot.png');
    await page.screenshot({ path: screenshotPath, fullPage: true, type: 'png' });
    console.log('  [截图] screenshot.png');
    const meta = { url: page.url(), title: await page.title(), timestamp: new Date().toISOString() };
    fs.writeFileSync(path.join(outputDir, 'meta.json'), JSON.stringify(meta, null, 2));
    console.log('  [元信息] meta.json');
    console.log('\n✅ Phase 1 完成');
  } finally { await context.close(); }
}

async function runSkeleton(playwright, url, outputDir, options = {}) {
  console.log('\n[Phase 2] DOM 骨架树');
  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({ viewport: options.viewport || { width: 1440, height: 900 } });
  const page = await context.newPage();
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 2000);
    const skeleton = await page.evaluate(() => {
      function walk(node, depth = 0) {
        if (depth > 10) return null;
        if (node.nodeType === 3) { const text = node.textContent?.trim(); if (!text) return null; return { type: 'text', text: text.slice(0, 100) }; }
        if (node.nodeType !== 1) return null;
        const tag = node.tagName?.toLowerCase();
        if (['script', 'style', 'noscript'].includes(tag)) return null;
        const s = window.getComputedStyle(node);
        if (s.display === 'none' || s.visibility === 'hidden') return null;
        const item = { tag, id: node.id || undefined, classes: node.className ? node.className.split(' ').filter(Boolean) : undefined, text: node.innerText?.trim()?.slice(0, 100) || undefined, children: [] };
        for (const child of node.children) { const sub = walk(child, depth + 1); if (sub) item.children.push(sub); }
        if (item.children.length === 0) delete item.children;
        return item;
      }
      return walk(document.body);
    });
    fs.writeFileSync(path.join(outputDir, 'skeleton.json'), JSON.stringify(skeleton, null, 2));
    console.log('  [骨架] skeleton.json');
    console.log('\n✅ Phase 2 完成');
  } finally { await context.close(); }
}

async function runStyles(playwright, url, outputDir, options = {}) {
  console.log('\n[Phase 3] 指定区域样式');
  const selector = options.selector;
  if (!selector) { console.error('  [错误] 需要 --selector 参数'); return; }
  const browser = await getBrowser(playwright, options);
  const context = await browser.newContext({ viewport: options.viewport || { width: 1440, height: 900 } });
  const page = await context.newPage();
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(options.wait || 2000);
    const sectionName = selector.replace(/[^a-zA-Z0-9]/g, '-');
    const sectionDir = path.join(outputDir, 'sections', sectionName);
    fs.mkdirSync(sectionDir, { recursive: true });
    try {
      const el = await page.$(selector);
      if (el) { await el.screenshot({ path: path.join(sectionDir, 'screenshot.png') }); console.log('  [截图] sections/' + sectionName + '/screenshot.png'); }
    } catch (e) { console.warn('  [警告] 截图失败:', e.message); }
    const data = await page.evaluate((sel) => {
      const el = document.querySelector(sel); if (!el) return null;
      const s = window.getComputedStyle(el); const styles = {};
      for (let i = 0; i < s.length; i++) { const prop = s[i]; styles[prop] = s.getPropertyValue(prop); }
      return { selector: sel, tag: el.tagName?.toLowerCase(), styles, bbox: el.getBoundingClientRect(), children: [...el.children].slice(0, 20).map(c => ({ tag: c.tagName?.toLowerCase(), id: c.id || undefined, classes: c.className ? c.className.split(' ').filter(Boolean) : undefined })) };
    }, selector);
    if (data) { fs.writeFileSync(path.join(sectionDir, 'data.json'), JSON.stringify(data, null, 2)); console.log('  [样式] sections/' + sectionName + '/data.json'); }
    console.log('\n✅ Phase 3 完成');
  } finally { await context.close(); }
}

// ============================================================================
// CLI
// ============================================================================

function parseArgs(argv) {
  const args = {
    url: null, command: null, output: './clone-data',
    section: null, selector: null, listOnly: false, interact: false,
    viewport: { width: 1440, height: 900 }, wait: 2000,
    headless: true, connectCdp: null, verbose: false, help: false,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--help' || a === '-h') args.help = true;
    else if (a === '-o' || a === '--output') args.output = argv[++i];
    else if (a === '-s' || a === '--section') args.section = argv[++i];
    else if (a === '--selector') args.selector = argv[++i];
    else if (a === '--list-only' || a === '-l') args.listOnly = true;
    else if (a === '--interact') args.interact = true;
    else if (a === '--viewport') { const [w, h] = (argv[++i] || '1440x900').split('x').map(Number); args.viewport = { width: w || 1440, height: h || 900 }; }
    else if (a === '--wait') args.wait = parseInt(argv[++i]) || 2000;
    else if (a === '--no-headless') args.headless = false;
    else if (a === '--connect-cdp') args.connectCdp = argv[++i];
    else if (a === '--verbose') args.verbose = true;
    else if (!a.startsWith('-')) { if (!args.url) args.url = a; else if (!args.command) args.command = a; }
  }
  return args;
}

function showHelp() {
  console.log(`
CoDesign 页面克隆工具 v2

用法:
  node clone.mjs <url> <command> [options]

命令:
  section     🆕 提取指定目录路径下所有页面（推荐）
  init        截图 + 元信息 + 设计令牌
  skeleton    DOM 骨架树
  styles      指定区域样式 (需要 --selector)
  quick       init + skeleton
  full        init + skeleton + responsive + assets

选项:
  -o, --output <dir>     输出目录 (默认: ./clone-data)
  -s, --section <path>   目录路径 (如 S9、S9/MCP服务)
  --selector <sel>        CSS 选择器 (用于 styles)
  --viewport WxH          视口大小 (默认: 1440x900)
  --wait <ms>             等待时间 (默认: 2000)
  --no-headless           显示浏览器
  --connect-cdp <url>     连接 Chrome (复用登录态)
  -l, --list-only         仅列出目录结构
  --verbose               详细日志
  -h, --help              帮助

示例:
  # 提取 S9/智能专家 下所有页面
  node clone.mjs https://codesign.qq.com/app/s/xxx section --section S9/智能专家 -o ./output

  # 仅列出目录结构
  node clone.mjs https://codesign.qq.com/app/s/xxx section --list-only

  # 快速模式
  node clone.mjs https://codesign.qq.com/prototype/xxx quick -o ./clone-data
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
  console.log('[CoDesign 克隆 v2]');
  console.log('  URL:', args.url);
  console.log('  命令:', args.command);
  if (args.section) console.log('  Section:', args.section);
  console.log('  输出:', outputDir);

  await ensureDependencies();
  if (!isPlaywrightAvailable()) { console.error('[错误] Playwright 不可用'); process.exit(1); }
  const playwright = await loadPlaywright();
  if (!playwright) { console.error('[错误] 加载 Playwright 失败'); process.exit(1); }

  fs.mkdirSync(outputDir, { recursive: true });
  const options = {
    headless: args.headless, connectCdp: args.connectCdp,
    viewport: args.viewport, wait: args.wait,
    section: args.section, listOnly: args.listOnly, interact: args.interact,
  };

  try {
    if (args.command === 'section') {
      await runSection(playwright, args.url, outputDir, options);
    } else if (args.command === 'init' || args.command === 'quick' || args.command === 'full') {
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
    if (args.command !== 'section') {
      console.log(`\n${'='.repeat(50)}`);
      console.log('✅ 完成！');
      console.log('  输出:', outputDir);
    }
  } finally {
    await closeBrowser();
  }
}

main().catch((e) => {
  console.error('[致命错误]', e);
  closeBrowser().then(() => process.exit(1));
});
