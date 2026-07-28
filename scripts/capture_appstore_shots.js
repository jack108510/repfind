// Capture App Store screenshots for repfind
// iPhone 6.7" display: 1290 x 2796 pixels
const puppeteer = require('puppeteer');
const path = require('path');

const WIDTH = 390;   // CSS pixels (device)
const HEIGHT = 844;
const SCALE = 3.306; // 390 * 3.306 ≈ 1290, 844 * 3.306 ≈ 2790 (close enough, Apple rounds)

const OUT_DIR = path.join(__dirname, '..', 'appstore-screenshots');
const fs = require('fs');
if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({
    width: WIDTH,
    height: HEIGHT,
    deviceScaleFactor: SCALE,
    isMobile: true,
    hasTouch: true,
  });

  // Set user agent to mobile
  await page.setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1');

  console.log('Loading repfind.ca...');
  await page.goto('https://repfind.ca', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  // Shot 1: Welcome/home screen
  console.log('Shot 1: Home screen');
  await page.screenshot({ path: path.join(OUT_DIR, 'shot1_home.png') });

  // Shot 2: Search with suggestions visible
  console.log('Shot 2: Search focus');
  await page.tap('#dockedSearchInput, #searchInput, input[type="text"]').catch(() => {});
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: path.join(OUT_DIR, 'shot2_search.png') });

  // Shot 3: Search results - sneakers
  console.log('Shot 3: Jordan 4 results');
  await page.type('#dockedSearchInput, #searchInput, input[type="text"]', 'jordan 4', { delay: 50 }).catch(async () => {
    // Fallback: set value directly
    await page.evaluate(() => {
      const input = document.querySelector('#dockedSearchInput, #searchInput, input[type="text"]');
      if (input) {
        input.value = 'jordan 4';
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
  });
  await new Promise(r => setTimeout(r, 500));
  await page.keyboard.press('Enter');
  await new Promise(r => setTimeout(r, 4000)); // Wait for AI response + results
  await page.screenshot({ path: path.join(OUT_DIR, 'shot3_jordan_results.png') });

  // Shot 4: Scroll down to show more results
  console.log('Shot 4: Scrolled results');
  await page.evaluate(() => window.scrollBy(0, 400));
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: path.join(OUT_DIR, 'shot4_results_scrolled.png') });

  // Shot 5: Different search - hoodies
  console.log('Shot 5: Essentials hoodie');
  // Click new search
  await page.evaluate(() => {
    const input = document.querySelector('#dockedSearchInput, #searchInput, input[type="text"]');
    if (input) { input.value = ''; input.dispatchEvent(new Event('input', { bubbles: true })); }
  });
  await page.evaluate(() => {
    const input = document.querySelector('#dockedSearchInput, #searchInput, input[type="text"]');
    if (input) {
      input.value = 'essentials hoodie';
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
  });
  await page.keyboard.press('Enter');
  await new Promise(r => setTimeout(r, 4000));
  await page.screenshot({ path: path.join(OUT_DIR, 'shot5_hoodie_results.png') });

  // Shot 6: Open cart/haul
  console.log('Shot 6: My Haul');
  await page.evaluate(() => {
    const cartBtn = document.querySelector('[onclick*="toggleCart"], .cart-btn, #cartBtn, button[aria-label*="cart" i], button[aria-label*="haul" i]');
    if (cartBtn) cartBtn.click();
    // Try to find and click the haul button
    const btns = Array.from(document.querySelectorAll('button'));
    const haulBtn = btns.find(b => b.textContent.toLowerCase().includes('haul'));
    if (haulBtn) haulBtn.click();
  });
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(OUT_DIR, 'shot6_haul.png') });

  await browser.close();
  console.log('Done! Screenshots saved to:', OUT_DIR);
})();
