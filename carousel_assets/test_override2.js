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
  await page.waitForFunction(() => typeof PRODUCT_DB !== 'undefined' && PRODUCT_DB.length > 0, { timeout: 15000 });
  console.log('DB loaded');

  // Check what renderResults expects
  const info = await page.evaluate(() => {
    console.log('renderResults signature: ' + renderResults.toString().slice(0, 200));
    console.log('renderCardHTML signature: ' + renderCardHTML.toString().slice(0, 200));
    return 'ok';
  });

  // Override
  await page.evaluate(() => {
    window.doSearch = async function() {
      const query = document.getElementById('searchInput')?.value?.trim() || document.getElementById('dockedSearchInput')?.value?.trim();
      if (!query) return;
      if (isSearching) return;
      isSearching = true;
      document.getElementById('welcome').classList.add('hide');
      document.getElementById('chatArea').classList.add('show');
      document.getElementById('dockedInput').classList.add('show');
      const inner = document.getElementById('chatInner');
      inner.innerHTML = '';
      const bubble = document.createElement('div');
      bubble.className = 'query-bubble';
      bubble.innerHTML = '<span>' + query + '</span>';
      inner.appendChild(bubble);
      await new Promise(r => setTimeout(r, 1200));
      const products = searchProducts(query, 20);
      console.log('Found ' + products.length + ' for: ' + query);
      const verdict = document.createElement('div');
      verdict.className = 'ai-response';
      verdict.innerHTML = '<div class="verdict-header"><div class="avatar"><img src="logo.png"></div><span class="bot-name">repfind <span class="badge">AI</span></span></div><div class="verdict-text">Found <strong>' + products.length + ' matches</strong> for "' + query + '". Here are the best direct-link listings:</div>';
      inner.appendChild(verdict);
      renderResults(inner, products, query);
      console.log('After renderResults, cards: ' + inner.querySelectorAll('.result-card').length);
      scrollToBottom();
      isSearching = false;
    };
    console.log('Override installed');
  });

  await new Promise(r => setTimeout(r, 9000));
  const state = await page.evaluate(() => ({
    cards: document.querySelectorAll('.result-card').length,
    demoState: document.getElementById('demo-state')?.textContent,
    queryBubble: document.querySelector('.query-bubble span')?.textContent,
  }));
  console.log('STATE:', JSON.stringify(state));
  await page.screenshot({ path: '/tmp/headless_v2.png' });
  await browser.close();
})();
