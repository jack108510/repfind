const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');
const { runGuestFlow } = require('./recording-actions');

const root = __dirname;
const captureDirectory = path.join(root, 'preview-mobile');

async function main() {
  fs.rmSync(captureDirectory, { recursive: true, force: true });
  fs.mkdirSync(captureDirectory, { recursive: true });

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: [
      '--disable-background-networking',
      '--disable-component-update',
      '--disable-default-apps',
      '--disable-sync',
      '--no-first-run',
      '--password-store=basic'
    ]
  });

  try {
    const context = await browser.newContext({
      viewport: { width: 360, height: 640 },
      screen: { width: 360, height: 640 },
      deviceScaleFactor: 3,
      isMobile: true,
      hasTouch: true,
      colorScheme: 'dark',
      locale: 'en-US'
    });
    const page = await context.newPage();
    await runGuestFlow(page, captureDirectory);
    await context.close();
  } finally {
    await browser.close();
  }

  const captures = fs.readdirSync(captureDirectory).filter((entry) => entry.endsWith('.png')).sort();
  console.log(`Mobile preview captures complete: ${captures.join(', ')}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
