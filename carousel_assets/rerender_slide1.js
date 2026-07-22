const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--font-render-hinting=none']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });

  const htmlPath = 'file://' + path.resolve(__dirname, 'carousel.html');
  await page.goto(htmlPath, { waitUntil: 'networkidle0' });
  await page.evaluate(() => document.fonts.ready);
  await new Promise(r => setTimeout(r, 2000));

  // Force each slide to exactly 1080x1920 and screenshot only that element
  const el = await page.$('#slide1');
  if (el) {
    // Override the element's height via JS
    await page.evaluate(() => {
      const s = document.getElementById('slide1');
      s.style.height = '1920px';
      s.style.maxHeight = '1920px';
      // Shrink phone image to fit
      const phoneWrap = s.querySelector('.phone-wrap');
      if (phoneWrap) phoneWrap.style.maxHeight = '1200px';
    });
    await new Promise(r => setTimeout(r, 500));
    await el.screenshot({ path: path.resolve(__dirname, 'slide1.png') });
    console.log('slide1.png saved (1080x1920)');
  }

  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
