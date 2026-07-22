const puppeteer = require('puppeteer-core');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--window-size=1280,900'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  page.on('console', msg => console.log(`[browser] ${msg.text()}`));

  await page.goto('http://localhost:8765/demo_autoplay.html?demo', { waitUntil: 'networkidle2' });

  // Wait for DB load + demo to progress
  await new Promise(r => setTimeout(r, 8000));

  const state = await page.evaluate(() => ({
    demoState: document.getElementById('demo-state')?.textContent,
    cards: document.querySelectorAll('.result-card').length,
    welcomeHidden: document.getElementById('welcome')?.classList.contains('hide'),
    queryBubble: document.querySelector('.query-bubble span')?.textContent,
    chatSnippet: document.getElementById('chatInner')?.innerHTML?.slice(0, 300),
  }));
  console.log('STATE:', JSON.stringify(state, null, 2));

  await page.screenshot({ path: '/tmp/headless_test.png' });
  console.log('Screenshot saved');
  await browser.close();
})();
