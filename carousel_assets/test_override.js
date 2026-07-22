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
  
  // Wait for DB
  await page.waitForFunction(() => typeof PRODUCT_DB !== 'undefined' && PRODUCT_DB && PRODUCT_DB.length > 0, { timeout: 15_000 });
  console.log('DB loaded');
  
  // Inject override
  await page.evaluate(() => {
    window.doSearch = async function() {
      const query = document.getElementById('searchInput')?.value?.trim() || document.getElementById('dockedSearchInput')?.value?.trim();
      if (!query) return;
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
      await new Promise(r => setTimeout(r, 1000));
      const products = searchProducts(query, 20);
      console.log('Found ' + products.length + ' products for: ' + query);
      const verdict = document.createElement('div');
      verdict.className = 'ai-response';
      verdict.innerHTML = '<div class="verdict-text">Found <strong>' + products.length + ' matches</strong> for "' + query + '"</div>';
      inner.appendChild(verdict);
      const results = document.createElement('div');
      results.className = 'results-section';
      results.innerHTML = '<div class="results-header"><span class="results-label">Top results</span></div><div class="results-list"></div>';
      inner.appendChild(results);
      const list = results.querySelector('.results-list');
      if (typeof renderResultCard === 'function') {
        products.forEach((p, i) => {
          const card = renderResultCard(p, i);
          if (card) list.appendChild(card);
        });
        console.log('Rendered ' + list.children.length + ' cards');
      } else {
        console.log('renderResultCard not found! Available: ' + Object.keys(window).filter(k => k.toLowerCase().includes('render')).join(', '));
      }
      scrollToBottom();
      isSearching = false;
    };
    console.log('Override installed');
  });

  // Wait for demo to fire a search
  await new Promise(r => setTimeout(r, 8000));

  const state = await page.evaluate(() => ({
    cards: document.querySelectorAll('.result-card').length,
    demoState: document.getElementById('demo-state')?.textContent,
    queryBubble: document.querySelector('.query-bubble span')?.textContent,
  }));
  console.log('STATE:', JSON.stringify(state));

  await page.screenshot({ path: '/tmp/headless_override.png' });
  await browser.close();
})();
