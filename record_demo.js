const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const OUT_DIR = '/Users/jackserver/repfind/demo_frames';
const VIDEO_OUT = '/Users/jackserver/repfind/repfind_demo.mp4';
const URL = 'http://localhost:8765/demo_autoplay.html?demo';
const DURATION_MS = 90_000;   // 90 seconds
const FPS = 15;
const TOTAL_FRAMES = Math.floor(DURATION_MS / (1000 / FPS));

(async () => {
  // Clean frames dir
  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-gpu',
      '--hide-scrollbars',
      '--window-size=1280,900',
    ],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });

  console.log('Loading demo page…');
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30_000 });

  // Wait for product DB to load
  await page.waitForFunction(() => {
    return typeof PRODUCT_DB !== 'undefined' && PRODUCT_DB && PRODUCT_DB.length > 0;
  }, { timeout: 15_000 }).catch(() => console.log('PRODUCT_DB wait timed out (continuing)'));

  console.log(`Capturing ${TOTAL_FRAMES} frames at ${FPS}fps (${DURATION_MS/1000}s)…`);

  let frame = 0;
  const interval = 1000 / FPS;
  const startTime = Date.now();

  await new Promise((resolve) => {
    const grab = async () => {
      const elapsed = Date.now() - startTime;
      if (elapsed >= DURATION_MS) { resolve(); return; }

      const padded = String(frame).padStart(5, '0');
      const file = path.join(OUT_DIR, `frame_${padded}.png`);
      await page.screenshot({ path: file, type: 'png' });
      frame++;

      if (frame % 15 === 0) {
        console.log(`  frame ${frame}/${TOTAL_FRAMES} (${(elapsed/1000).toFixed(1)}s)`);
      }

      setTimeout(grab, interval);
    };
    grab();
  });

  console.log(`Done: ${frame} frames captured`);
  await browser.close();

  // Stitch with ffmpeg
  console.log('Stitching video with ffmpeg…');
  const { execSync } = require('child_process');
  execSync(
    `ffmpeg -y -framerate ${FPS} -i ${OUT_DIR}/frame_%05d.png ` +
    `-c:v libx264 -pix_fmt yuv420p -crf 18 -preset fast ` +
    `-movflags +faststart ${VIDEO_OUT}`,
    { stdio: 'inherit' }
  );

  // Clean frames
  fs.rmSync(OUT_DIR, { recursive: true, force: true });

  const size = fs.statSync(VIDEO_OUT).size;
  console.log(`✓ Video saved: ${VIDEO_OUT} (${(size/1024/1024).toFixed(1)}MB)`);
})();
