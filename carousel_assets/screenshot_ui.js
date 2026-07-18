const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-features=site-per-process']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 540, height: 1170, deviceScaleFactor: 2 });
  await page.setBypassCSP(true);
  await page.goto('https://repfind.ca?q=jordan+4+bred', { waitUntil: 'networkidle0', timeout: 30000 });
  
  // Wait for and dismiss the onboarding modal
  await new Promise(r => setTimeout(r, 2000));
  await page.evaluate(() => {
    // Click the "Start searching" button to properly dismiss onboarding
    const onboardBtn = document.querySelector('#onboardOverlay button[onclick="closeOnboarding()"]');
    if (onboardBtn) onboardBtn.click();
    // Fallback: hide all overlays
    document.querySelectorAll('#onboardOverlay, #checkoutOverlay2, .detail-overlay').forEach(el => el.style.display = 'none');
  });
  
  await new Promise(r => setTimeout(r, 6000));
  
  // Scroll to show results nicely
  await page.evaluate(() => {
    window.scrollTo(0, 200);
  });
  
  await new Promise(r => setTimeout(r, 1000));
  
  await page.screenshot({
    path: 'slide1.png',
    clip: { x: 0, y: 0, width: 540, height: 1170 }
  });
  
  console.log('Saved slide1.png');
  await browser.close();
})();
