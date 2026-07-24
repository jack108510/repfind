const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');
const { runGuestFlow } = require('./recording-actions');

const root = __dirname;
const rawDirectory = path.join(root, 'recordings', 'raw');
const outputDirectory = path.join(root, 'output');
const MOBILE_VIEWPORT = { width: 360, height: 640 };

async function main() {
  fs.rmSync(rawDirectory, { recursive: true, force: true });
  fs.mkdirSync(rawDirectory, { recursive: true });
  fs.mkdirSync(outputDirectory, { recursive: true });

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
      viewport: MOBILE_VIEWPORT,
      screen: MOBILE_VIEWPORT,
      deviceScaleFactor: 3,
      isMobile: true,
      hasTouch: true,
      colorScheme: 'dark',
      locale: 'en-US',
      recordVideo: {
        dir: rawDirectory,
        // Playwright records the viewport into this canvas. It must match exactly to avoid a top-left inset.
        size: MOBILE_VIEWPORT
      }
    });
    await context.addInitScript(() => {
      try {
        localStorage.setItem('repfind_onboarded', '1');
      } catch (_) {
        // Storage is optional for the isolated recording page.
      }
    });
    const page = await context.newPage();
    const video = page.video();

    await runGuestFlow(page);
    await context.close();

    const rawVideoPath = await video.path();
    const destination = path.join(outputDirectory, 'repfind-mobile-screen-recording.webm');
    fs.copyFileSync(rawVideoPath, destination);
    console.log(destination);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
