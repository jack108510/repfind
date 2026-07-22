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

  await page.evaluate(() => {
    window.doSearch = async function() {
      const query = (document.getElementById('dockedSearchInput')?.value?.trim()) || document.getElementById('searchInput')?.value?.trim();
      if (!query || isSearching) return;
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
      verdict.innerHTML = '<div class="verdict-header"><div class="avatar"><img src="logo.png"></div><span class="bot-name">repfind <span class="badge">AI</span></span></div><div class="verdict-text">Found <strong>' + products.length + ' matches</strong>.</div>';
      inner.appendChild(verdict);
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
        card.innerHTML = renderCardHTML(p, i);
        list.appendChild(card);
      });
      console.log('Rendered ' + list.querySelectorAll('.result-card').length + ' cards');
      scrollToBottom();
      isSearching = false;
      // Clear inputs like the real doSearch does
      document.getElementById('searchInput').value = '';
      document.getElementById('dockedSearchInput').value = '';
    };
    console.log('Override installed');
  });

  await new Promise(r => setTimeout(r, 10000));
  const state = await page.evaluate(() => ({
    cards: document.querySelectorAll('.result-card').length,
    demoState: document.getElementById('demo-state')?.textContent,
    query: document.querySelector('.query-bubble span')?.textContent,
  }));
  console.log('STATE:', JSON.stringify(state));
  await page.screenshot({ path: '/tmp/headless_final.png' });
  console.log('Screenshot saved');
  await browser.close();
})();
