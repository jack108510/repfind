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

  // Collect console logs for debugging
  page.on('console', msg => console.log(`[browser] ${msg.text()}`));

  console.log('Loading demo page…');
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30_000 });

  // Wait for product DB to load
  await page.waitForFunction(() => {
    return typeof PRODUCT_DB !== 'undefined' && PRODUCT_DB && PRODUCT_DB.length > 0;
  }, { timeout: 15_000 }).catch(() => console.log('PRODUCT_DB wait timed out (continuing)'));

  // Override doSearch to skip the webhook entirely — use local DB directly.
  // The webhook returns 400 in headless mode (bot detection).
  await page.evaluate(() => {
    window.doSearch = async function(fromDocked) {
      if (typeof isSearching !== 'undefined' && isSearching) return;
      const query = (typeof getQuery === 'function') ? getQuery() :
        (document.getElementById('dockedSearchInput')?.value?.trim() ||
         document.getElementById('searchInput')?.value?.trim());
      if (!query) return;

      // Reset state
      if (typeof isSearching !== 'undefined') isSearching = true;
      document.getElementById('welcome')?.classList.add('hide');
      document.getElementById('chatArea')?.classList.add('show');
      document.getElementById('dockedInput')?.classList.add('show');

      const inner = document.getElementById('chatInner');
      if (inner) inner.innerHTML = '';

      // Query bubble
      if (inner) {
        const bubble = document.createElement('div');
        bubble.className = 'query-bubble';
        bubble.innerHTML = `<span>${query}</span>`;
        inner.appendChild(bubble);
      }

      // Loading message
      if (inner) {
        const loading = document.createElement('div');
        loading.className = 'ai-response';
        loading.innerHTML = `
          <div class="verdict-header">
            <div class="avatar"><img src="logo.png" alt=""></div>
            <span class="bot-name">repfind <span class="badge">AI</span></span>
          </div>
          <div class="loading-steps">
            <div class="step-item active">
              <div class="step-check spinner-mini"></div>
              <span>Searching 66K+ direct-link products…</span>
            </div>
          </div>`;
        inner.appendChild(loading);
        if (typeof scrollToBottom === 'function') scrollToBottom();
      }

      // Clear inputs
      const di = document.getElementById('dockedSearchInput');
      const mi = document.getElementById('searchInput');
      if (di) di.value = '';
      if (mi) mi.value = '';

      // Brief delay to show loading
      await new Promise(r => setTimeout(r, 1200));

      // Search local DB directly
      let products = [];
      if (typeof searchProducts === 'function') {
        products = searchProducts(query, 20);
      }
      console.log('Found ' + products.length + ' for: ' + query);

      // Remove loading
      if (inner) inner.querySelectorAll('.loading-steps, #loadingSection').forEach(e => e.remove());

      // Render verdict
      if (inner) {
        const verdict = document.createElement('div');
        verdict.className = 'ai-response';
        verdict.innerHTML = `
          <div class="verdict-header">
            <div class="avatar"><img src="logo.png" alt=""></div>
            <span class="bot-name">repfind <span class="badge">AI</span></span>
          </div>
          <div class="verdict-text">Found <strong>${products.length} matches</strong> for "${query}". Here are the best direct-link listings:</div>
        `;
        inner.appendChild(verdict);

        // Render results section + cards manually
        if (products.length > 0) {
          const section = document.createElement('div');
          section.className = 'results-section';
          section.innerHTML = '<div class="results-header"><span class="results-label">Top results</span></div>';
          const list = document.createElement('div');
          list.className = 'results-list';
          section.appendChild(list);
          inner.appendChild(section);

          products.forEach((p, i) => {
            const card = document.createElement('div');
            card.className = 'result-card';
            card.dataset.platform = p.platform || 'weidian';
            card.style.animationDelay = Math.min(i * 0.06, 0.4) + 's';
            if (typeof renderCardHTML === 'function') {
              card.innerHTML = renderCardHTML(p, i);
            }
            list.appendChild(card);
          });
          console.log('Rendered ' + list.querySelectorAll('.result-card').length + ' cards');
        }

        if (typeof scrollToBottom === 'function') scrollToBottom();
      }

      if (typeof isSearching !== 'undefined') isSearching = false;
    };
    console.log('doSearch overridden for headless recording (skips webhook)');
  });

  // Wait for the demo to start
  console.log('Waiting for demo to start searching…');
  await new Promise(r => setTimeout(r, 5000));

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
