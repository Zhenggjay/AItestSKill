import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require(
  'C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright',
);

const url = process.argv[2];
const outDir = process.argv[3] || 'codesign-output/sequence';
const total = Number(process.argv[4] || 4);

if (!url) {
  console.error('Usage: node tools/capture-codesign-sequence.mjs <url> [outDir] [total]');
  process.exit(1);
}

await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
});

const page = await browser.newPage({
  viewport: { width: 1920, height: 1400 },
  deviceScaleFactor: 1,
});

async function collectText(page) {
  const texts = [];
  for (const frame of page.frames()) {
    try {
      const text = await frame.evaluate(() => document.body?.innerText || document.body?.textContent || '');
      if (text.trim()) texts.push({ url: frame.url(), text });
    } catch {
      // Cross-origin frames can be skipped.
    }
  }
  return texts;
}

try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForLoadState('load', { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(8000);

  const pages = [];
  for (let index = 1; index <= total; index += 1) {
    const screenshot = path.join(outDir, `page-${String(index).padStart(2, '0')}.png`);

    // Auto-expand iframe and parent containers to capture full page contents
    const dimensions = await page.evaluate(async () => {
      const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const iframe = document.querySelector('iframe');
      if (!iframe) return null;

      try {
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        if (!iframeDoc) return null;

        // Wait for page elements inside the iframe to settle
        await sleep(1500);

        iframe.style.position = 'relative';

        const contentHeight = Math.max(
          iframeDoc.body.scrollHeight,
          iframeDoc.documentElement.scrollHeight,
          iframeDoc.body.offsetHeight,
          iframeDoc.documentElement.offsetHeight
        );

        const contentWidth = Math.max(
          iframeDoc.body.scrollWidth,
          iframeDoc.documentElement.scrollWidth,
          iframeDoc.body.offsetWidth,
          iframeDoc.documentElement.offsetWidth
        );

        if (contentHeight > 0 && contentWidth > 0) {
          // Set iframe styles to expand completely
          iframe.style.height = contentHeight + 'px';
          iframe.style.maxHeight = 'none';
          iframe.style.minHeight = contentHeight + 'px';

          iframe.style.width = contentWidth + 'px';
          iframe.style.maxWidth = 'none';
          iframe.style.minWidth = contentWidth + 'px';

          // Style all parent elements in the parent document to display full size without scrolls
          let parent = iframe.parentElement;
          while (parent && parent !== document.body) {
            parent.style.height = 'auto';
            parent.style.maxHeight = 'none';
            parent.style.minHeight = 'auto';
            parent.style.overflow = 'visible';
            parent.style.overflowY = 'visible';

            parent.style.width = 'auto';
            parent.style.maxWidth = 'none';
            parent.style.minWidth = 'auto';
            parent.style.overflowX = 'visible';
            parent = parent.parentElement;
          }

          // Remove custom viewport scrollbars on top document
          document.body.style.overflow = 'visible';
          document.body.style.overflowY = 'visible';
          document.body.style.overflowX = 'visible';
          document.documentElement.style.overflow = 'visible';
          document.documentElement.style.overflowY = 'visible';
          document.documentElement.style.overflowX = 'visible';

          return { width: contentWidth, height: contentHeight };
        }
      } catch (e) {
        console.error('Error expanding iframe:', e);
      }
      return null;
    });

    if (dimensions) {
      console.log(`Dynamic Viewport Resize: ${dimensions.width}x${dimensions.height}`);
      const targetWidth = Math.min(5000, Math.max(1920, dimensions.width));
      const targetHeight = Math.min(10000, Math.max(1400, dimensions.height));
      await page.setViewportSize({ width: targetWidth, height: targetHeight });
    }

    // Add extra wait time for layout recalculations and rendering
    await page.waitForTimeout(2000);

    await page.screenshot({ path: screenshot, fullPage: true });
    const texts = await collectText(page);
    pages.push({
      index,
      screenshot,
      url: page.url(),
      title: await page.title(),
      texts,
    });
    await fs.writeFile(path.join(outDir, `page-${String(index).padStart(2, '0')}.txt`), texts.map((item) => item.text).join('\n\n---FRAME---\n\n'), 'utf8');

    if (index < total) {
      await page.keyboard.press('ArrowRight');
      await page.waitForTimeout(2000);
      const afterText = (await collectText(page)).map((item) => item.text).join('\n');
      if (!afterText.includes(`${index + 1}/${total}`)) {
        await page.mouse.click(1300, 970);
        await page.waitForTimeout(1800);
      }
    }
  }

  await fs.writeFile(path.join(outDir, 'sequence-meta.json'), JSON.stringify(pages, null, 2), 'utf8');
  console.log(JSON.stringify({ ok: true, pages: pages.length, outDir: path.resolve(outDir) }, null, 2));
} catch (error) {
  await fs.writeFile(path.join(outDir, 'sequence-error.txt'), error.stack || String(error), 'utf8');
  console.error(error);
  process.exitCode = 1;
} finally {
  await browser.close();
}
