const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
  await page.goto('file:///Users/jackserver/repfind/carousel_assets/carousel.html', { waitUntil: 'networkidle0' });
  
  // Wait for fonts and images to load
  await page.evaluate(() => document.fonts.ready);
  await new Promise(r => setTimeout(r, 3000));
  
  const carouselDir = '/Users/jackserver/repfind/carousel_assets';
  const slides = ['slide1', 'slide2', 'slide3', 'slide4', 'slide5'];
  for (const id of slides) {
    const el = await page.$('#' + id);
    if (el) {
      await el.screenshot({ path: carouselDir + '/' + id + '.png' });
      console.log('Saved ' + id + '.png');
    } else {
      console.log('Missing #' + id);
    }
  }
  
  await browser.close();
})();
