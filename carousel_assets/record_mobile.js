const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const OUT_DIR = '/Users/jackserver/repfind/demo_frames';
const VIDEO_OUT = '/Users/jackserver/repfind/repfind_demo_mobile.mp4';
const URL = 'http://localhost:8765/demo_autoplay.html?demo';
const DURATION_MS = 80_000;
const FPS = 20;

// Mobile viewport (iPhone 14 Pro)
const MOBILE_W = 390;
const MOBILE_H = 844;
// Output video dimensions (1080x1920 vertical story format)
const OUT_W = 1080;
const OUT_H = 1920;

(async () => {
  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--hide-scrollbars'],
  });

  const page = await browser.newPage();
  // Emulate iPhone 14 Pro
  try {
    const devices = puppeteer.KnownDevices || (require('puppeteer-core').KnownDevices) || {};
    const device = devices['iPhone 14 Pro'] || devices['iPhone 13'];
    if (device) {
      await page.emulate(device);
    } else {
      await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
    }
  } catch(e) {
    await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
  }
  page.on('console', msg => console.log(`[browser] ${msg.text()}`));

  console.log('Loading demo page…');
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30_000 });

  // Wait for DB
  await page.waitForFunction(() => {
    return typeof PRODUCT_DB !== 'undefined' && PRODUCT_DB && PRODUCT_DB.length > 0;
  }, { timeout: 15_000 }).catch(() => console.log('DB wait timeout'));

  // Override doSearch to skip webhook, use local DB directly
  await page.evaluate(() => {
    window.doSearch = async function() {
      const query = (document.getElementById('dockedSearchInput')?.value?.trim()) ||
                    document.getElementById('searchInput')?.value?.trim();
      if (!query || (typeof isSearching !== 'undefined' && isSearching)) return;
      if (typeof isSearching !== 'undefined') isSearching = true;

      document.getElementById('welcome')?.classList.add('hide');
      document.getElementById('chatArea')?.classList.add('show');
      document.getElementById('dockedInput')?.classList.add('show');
      const inner = document.getElementById('chatInner');
      if (inner) inner.innerHTML = '';

      // Query bubble
      const bubble = document.createElement('div');
      bubble.className = 'query-bubble';
      bubble.innerHTML = `<span>${query}</span>`;
      inner?.appendChild(bubble);

      // Loading
      const loading = document.createElement('div');
      loading.className = 'ai-response';
      loading.innerHTML = `<div class="loading-steps"><div class="step-item active"><div class="step-check spinner-mini"></div><span>Searching 66K+ direct-link products…</span></div></div>`;
      inner?.appendChild(loading);
      if (typeof scrollToBottom === 'function') scrollToBottom();

      // Signal focus to recorder
      window.__demoFocus = { type: 'searching', query };

      // Clear inputs
      document.getElementById('dockedSearchInput').value = '';
      document.getElementById('searchInput').value = '';

      await new Promise(r => setTimeout(r, 1000));
      const products = typeof searchProducts === 'function' ? searchProducts(query, 15) : [];
      console.log('Found ' + products.length + ' for: ' + query);

      inner?.querySelectorAll('.loading-steps').forEach(e => e.remove());

      const verdict = document.createElement('div');
      verdict.className = 'ai-response';
      verdict.innerHTML = `<div class="verdict-header"><div class="avatar"><img src="logo.png" alt=""></div><span class="bot-name">repfind <span class="badge">AI</span></span></div><div class="verdict-text">Found <strong>${products.length} matches</strong> for "${query}".</div>`;
      inner?.appendChild(verdict);

      if (products.length > 0 && inner) {
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
          card.style.animationDelay = Math.min(i * 0.06, 0.4) + 's';
          if (typeof renderCardHTML === 'function') card.innerHTML = renderCardHTML(p, i);
          list.appendChild(card);
        });
        console.log('Rendered ' + list.querySelectorAll('.result-card').length + ' cards');
      }

      if (typeof scrollToBottom === 'function') scrollToBottom();
      if (typeof isSearching !== 'undefined') isSearching = false;
      window.__demoFocus = { type: 'results', query };
    };
    console.log('doSearch overridden');
  });

  // Inject a focus tracker into the demo driver
  await page.evaluate(() => {
    // Poll the demo state and set focus hints
    const focusPoll = setInterval(() => {
      const stateEl = document.getElementById('demo-state');
      if (!stateEl) return;
      const state = stateEl.textContent || '';
      const focus = { state };

      // Determine what to focus on
      if (state.includes('typing')) {
        const input = document.getElementById('searchInput') || document.getElementById('dockedSearchInput');
        if (input) {
          const rect = input.getBoundingClientRect();
          focus.type = 'typing';
          focus.x = rect.left + rect.width / 2;
          focus.y = rect.top + rect.height / 2;
          focus.scale = 1.8;
        }
      } else if (state.includes('scrolling') || state.includes('browsing') || state.includes('results')) {
        // Follow the results area
        const cards = document.querySelectorAll('.result-card');
        if (cards.length > 0) {
          const mid = Math.min(cards.length - 1, 2);
          const rect = cards[mid].getBoundingClientRect();
          focus.type = 'browsing';
          focus.x = rect.left + rect.width / 2;
          focus.y = rect.top + rect.height / 2;
          focus.scale = 1.3;
        }
      } else if (state.includes('haul') || state.includes('cart')) {
        const cart = document.getElementById('cartPanel');
        if (cart) {
          const rect = cart.getBoundingClientRect();
          focus.type = 'cart';
          focus.x = rect.left + rect.width / 2;
          focus.y = rect.top + rect.height / 2;
          focus.scale = 1.5;
        }
      } else if (state.includes('agent')) {
        const btns = document.querySelectorAll('.agent-toggle-btn');
        if (btns.length) {
          const rect = btns[0].getBoundingClientRect();
          focus.type = 'agent';
          focus.x = rect.left + rect.width / 2;
          focus.y = rect.top + rect.height / 2;
          focus.scale = 1.6;
        }
      } else {
        focus.type = 'overview';
        focus.x = MOBILE_W / 2 || 195;
        focus.y = MOBILE_H / 2 || 422;
        focus.scale = 1.0;
      }

      window.__focus = focus;
    }, 200);
  });

  console.log('Waiting for demo to start…');
  await new Promise(r => setTimeout(r, 4000));

  console.log(`Capturing ${Math.floor(DURATION_MS / (1000 / FPS))} frames at ${FPS}fps (${DURATION_MS/1000}s)…`);

  let frame = 0;
  const interval = 1000 / FPS;
  const startTime = Date.now();
  const captureDir = OUT_DIR;

  while (Date.now() - startTime < DURATION_MS) {
    const padded = String(frame).padStart(5, '0');

    // Get current focus + scroll position
    const focusData = await page.evaluate(() => ({
      focus: window.__focus || { type: 'overview', x: 195, y: 422, scale: 1.0 },
      scrollY: window.scrollY,
      innerHeight: window.innerHeight,
    }));

    // Take screenshot of full page
    const rawFile = path.join(captureDir, `raw_${padded}.png`);
    await page.screenshot({ path: rawFile, type: 'png' });

    // Crop and zoom: center on focus point, scale up
    const fx = focusData.focus.x || 195;
    const fy = focusData.focus.y + focusData.scrollY; // account for scroll
    const scale = focusData.focus.scale || 1.0;

    // Source crop dimensions (what portion of the full screenshot we grab)
    const srcW = MOBILE_W / scale;
    const srcH = MOBILE_H / scale;

    // Clamp crop center to page bounds
    let cropX = fx - srcW / 2;
    let cropY = fy - srcH / 2;
    cropX = Math.max(0, Math.min(cropX, MOBILE_W - srcW));
    cropY = Math.max(0, cropY); // Y can extend for long pages

    const outFile = path.join(captureDir, `frame_${padded}.png`);

    if (scale > 1.05) {
      // Crop then scale to output size
      execSync(
        `ffmpeg -y -i ${rawFile} ` +
        `-filter:v "crop=${Math.round(srcW)}:${Math.round(srcH)}:${Math.round(cropX)}:${Math.round(cropY)},scale=${OUT_W}:${OUT_H}" ` +
        `-frames:v 1 ${outFile} 2>/dev/null`
      );
    } else {
      // Just scale to output size (overview)
      execSync(
        `ffmpeg -y -i ${rawFile} -filter:v "scale=${OUT_W}:${OUT_H}" -frames:v 1 ${outFile} 2>/dev/null`
      );
    }

    fs.unlinkSync(rawFile); // clean raw

    frame++;
    if (frame % 20 === 0) {
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      console.log(`  frame ${frame} (${elapsed}s) focus: ${focusData.focus.type} scale: ${scale}`);
    }

    // Wait for next interval (minus processing time)
    const elapsedThisFrame = Date.now() - startTime - (frame - 1) * interval;
    const waitTime = Math.max(0, interval - elapsedThisFrame);
    await new Promise(r => setTimeout(r, waitTime));
  }

  console.log(`Done: ${frame} frames captured`);
  await browser.close();

  // Stitch
  console.log('Stitching video with ffmpeg…');
  execSync(
    `ffmpeg -y -framerate ${FPS} -i ${OUT_DIR}/frame_%05d.png ` +
    `-c:v libx264 -pix_fmt yuv420p -crf 20 -preset fast ` +
    `-movflags +faststart ${VIDEO_OUT}`,
    { stdio: 'inherit' }
  );

  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  const size = fs.statSync(VIDEO_OUT).size;
  console.log(`✓ Video saved: ${VIDEO_OUT} (${(size/1024/1024).toFixed(1)}MB)`);
})();
