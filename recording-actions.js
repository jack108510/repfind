const fs = require('fs');
const path = require('path');
const recordingConfig = require('./recording-config.js');

const searchTerm = String(recordingConfig.searchTerm || 'Jordan 4').trim() || 'Jordan 4';
const selectedProductId = String(recordingConfig.selectedProductId || '').trim();
const verifyLiveKakobuy = recordingConfig.verifyLiveKakobuy !== false;
const wait = (page, milliseconds) => page.waitForTimeout(milliseconds);

async function resolveLocatorPoint(locator) {
  const box = await locator.boundingBox();
  if (!box) throw new Error('Could not locate a visible target for the scripted recording.');
  return {
    x: box.x + Math.min(Math.max(box.width / 2, 12), Math.max(box.width - 12, 12)),
    y: box.y + Math.min(Math.max(box.height / 2, 12), Math.max(box.height - 12, 12))
  };
}

async function moveCursorTo(page, locator) {
  await locator.scrollIntoViewIfNeeded();
  const point = await resolveLocatorPoint(locator);
  await page.mouse.move(point.x, point.y, { steps: 14 });
  await page.evaluate(({ x, y }) => window.__recordingDemo?.moveCursor(x, y), point);
  await wait(page, 330);
  return point;
}

async function clickWithCursor(page, locator) {
  await moveCursorTo(page, locator);
  await wait(page, 115);
  await page.evaluate(() => window.__recordingDemo?.pulseCursor());
  await wait(page, 150);
  await locator.click();
  await wait(page, 420);
}

async function typeWithCursor(page, locator, text) {
  await clickWithCursor(page, locator);
  await locator.type(text, { delay: 105 });
  await wait(page, 520);
}

async function capture(page, directory, fileName) {
  if (!directory) return;
  fs.mkdirSync(directory, { recursive: true });
  await page.screenshot({
    path: path.join(directory, fileName),
    type: 'png',
    fullPage: false,
    animations: 'disabled'
  });
}

async function waitForVisibleProductImages(page, minimumImages = 2) {
  try {
    await page.waitForFunction((minimum) => {
      const images = [...document.querySelectorAll('#resultsList .result-card img')];
      return images.filter((image) => image.complete && image.naturalWidth > 0).length >= minimum;
    }, minimumImages, { timeout: 220 });
  } catch (_) {
    // Do not pause the recording for remote thumbnails; visible fallbacks preserve the flow.
  }
}

async function moveCursorIntoResults(page, xFraction = 0.72, yFraction = 0.50) {
  const area = page.locator('#chatArea');
  const box = await area.boundingBox();
  if (!box) throw new Error('Could not locate the visible result area.');
  const point = {
    x: Math.round(box.x + box.width * xFraction),
    y: Math.round(box.y + box.height * yFraction)
  };
  await page.mouse.move(point.x, point.y, { steps: 12 });
  await page.evaluate(({ x, y }) => window.__recordingDemo?.moveCursor(x, y), point);
  await wait(page, 160);
}

async function smoothScrollResultViewBy(page, delta, duration = 260) {
  await page.evaluate(async ({ amount, milliseconds }) => {
    const area = document.getElementById('chatArea');
    const root = area && area.scrollHeight > area.clientHeight + 2
      ? area
      : (document.scrollingElement || document.documentElement);
    if (!root || Math.abs(amount) < 2) return;
    const start = root.scrollTop;
    const startedAt = performance.now();
    await new Promise((resolve) => {
      const frame = (now) => {
        const progress = Math.min(1, (now - startedAt) / milliseconds);
        const eased = 1 - Math.pow(1 - progress, 2.35);
        root.scrollTop = start + amount * eased;
        if (progress < 1) requestAnimationFrame(frame);
        else resolve();
      };
      requestAnimationFrame(frame);
    });
  }, { amount: delta, milliseconds: duration });
}

async function browseResultsImmediately(page, selectedIndex) {
  const destination = await page.evaluate((index) => {
    const area = document.getElementById('chatArea');
    const root = area && area.scrollHeight > area.clientHeight + 2
      ? area
      : (document.scrollingElement || document.documentElement);
    const cards = [...document.querySelectorAll('#resultsList .result-card')];
    const card = cards[index];
    if (!root || !card) return 0;
    const cardBox = card.getBoundingClientRect();
    const rootIsArea = root === area;
    const rootBox = rootIsArea ? area.getBoundingClientRect() : null;
    const viewportHeight = rootIsArea ? root.clientHeight : window.innerHeight;
    const cardTopInRoot = rootIsArea
      ? cardBox.top - rootBox.top + root.scrollTop
      : cardBox.top + root.scrollTop;
    return Math.max(0, Math.round(cardTopInRoot - viewportHeight * 0.42));
  }, selectedIndex);

  const start = await page.evaluate(() => {
    const area = document.getElementById('chatArea');
    const root = area && area.scrollHeight > area.clientHeight + 2
      ? area
      : (document.scrollingElement || document.documentElement);
    return root?.scrollTop || 0;
  });
  const travel = Math.max(0, destination - start);
  if (travel < 2) return;

  // Begin immediately with a set of small, real wheel gestures. Each pause is long enough to be
  // captured as movement, rather than compressing the browse into a single scroll-top jump.
  await moveCursorIntoResults(page, 0.71, 0.52);
  const stepCount = Math.max(10, Math.min(16, Math.ceil(travel / 34)));
  const weights = Array.from({ length: stepCount }, (_, index) => 1 + Math.sin((index + 1) * 0.85) * 0.16);
  const weightTotal = weights.reduce((sum, weight) => sum + weight, 0);
  let sent = 0;

  for (let index = 0; index < stepCount; index += 1) {
    const isFinalStep = index === stepCount - 1;
    const delta = isFinalStep ? travel - sent : Math.max(8, Math.round(travel * (weights[index] / weightTotal)));
    sent += delta;
    const before = await page.evaluate(() => {
      const area = document.getElementById('chatArea');
      const root = area && area.scrollHeight > area.clientHeight + 2
        ? area
        : (document.scrollingElement || document.documentElement);
      return root?.scrollTop || 0;
    });
    await page.mouse.wheel(0, delta);
    await wait(page, 105 + (index % 3) * 12);
    const after = await page.evaluate(() => {
      const area = document.getElementById('chatArea');
      const root = area && area.scrollHeight > area.clientHeight + 2
        ? area
        : (document.scrollingElement || document.documentElement);
      return root?.scrollTop || 0;
    });
    // On a touch-emulated browser, route the same small movement through the active scroll root
    // if the wheel event is ignored. The incremental fallback remains visibly smooth.
    if (Math.abs(after - before) < 2) await smoothScrollResultViewBy(page, delta, 92);
  }

  const correction = await page.evaluate((index) => {
    const area = document.getElementById('chatArea');
    const root = area && area.scrollHeight > area.clientHeight + 2
      ? area
      : (document.scrollingElement || document.documentElement);
    const cards = [...document.querySelectorAll('#resultsList .result-card')];
    const card = cards[index];
    if (!root || !card) return 0;
    const cardBox = card.getBoundingClientRect();
    const rootIsArea = root === area;
    const rootBox = rootIsArea ? area.getBoundingClientRect() : null;
    const viewportHeight = rootIsArea ? root.clientHeight : window.innerHeight;
    const visibleTop = rootIsArea ? cardBox.top - rootBox.top : cardBox.top;
    return Math.round(visibleTop - viewportHeight * 0.42);
  }, selectedIndex);
  if (Math.abs(correction) > 2) await smoothScrollResultViewBy(page, correction, 180);
  await wait(page, 150);
}

async function positionConfiguredResultForBrowse(page, cardCount) {
  if (!selectedProductId) return;
  await page.evaluate(({ id, desiredIndex }) => {
    const results = (typeof currentResults !== 'undefined' && Array.isArray(currentResults)) ? currentResults : [];
    const list = document.querySelector('#resultsList');
    const cards = list ? [...list.querySelectorAll('.result-card')] : [];
    const sourceIndex = results.findIndex((product) => String(product.id) === id);
    const targetIndex = Math.min(desiredIndex, results.length - 1, cards.length - 1);
    if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex || !cards[sourceIndex]) return;

    // Keep the real product and its real direct link intact, while featuring it after several
    // result cards so the demo visibly demonstrates browsing before selection.
    const [selectedResult] = results.splice(sourceIndex, 1);
    results.splice(targetIndex, 0, selectedResult);
    const selectedCard = cards[sourceIndex];
    const referenceCard = cards[targetIndex];
    if (sourceIndex < targetIndex) referenceCard.after(selectedCard);
    else referenceCard.before(selectedCard);
  }, { id: selectedProductId, desiredIndex: Math.min(4, cardCount - 1) });
}

async function chooseResultIndex(page, cardCount) {
  if (selectedProductId) {
    const configuredIndex = await page.evaluate((id) => {
      const results = (typeof currentResults !== 'undefined' && Array.isArray(currentResults)) ? currentResults : [];
      return results.findIndex((product) => String(product.id) === id);
    }, selectedProductId);
    if (configuredIndex >= 0) return configuredIndex;
    throw new Error(`The configured selectedProductId (${selectedProductId}) was not found in the search results.`);
  }

  // Fixed arithmetic keeps the capture reproducible while avoiding a first-card selection.
  return Math.min(cardCount - 1, 3 + ((cardCount * 5 + 1) % 4));
}

async function waitForLiveProductDetails(page) {
  await page.waitForFunction(() => {
    const bodyText = document.body?.innerText || '';
    const title = document.querySelector('.item-title')?.textContent?.trim() || '';
    const sourceLabel = [...document.querySelectorAll('.item_youks, .item_youks *')]
      .some((element) => (element.textContent || '').includes('Source of the product'));
    const hasPrice = /CNY\s*[￥¥]?\s*\d+(?:\.\d+)?/i.test(bodyText);
    return title.length >= 12 && sourceLabel && hasPrice;
  }, null, { timeout: 30000 });
}

async function waitForVisiblePrimaryProductImage(page) {
  const selector = '.preview-img img.el-image__inner.el-image__preview, .preview-img img';
  const primaryImage = page.locator(selector).first();
  await primaryImage.waitFor({ state: 'visible', timeout: 30000 });
  await page.evaluate(() => {
    const root = document.scrollingElement || document.documentElement;
    root.scrollTop = 0;
  });

  const isRenderedProductImage = () => {
    const image = document.querySelector('.preview-img img.el-image__inner.el-image__preview, .preview-img img');
    if (!image || !image.complete || image.naturalWidth < 300 || image.naturalHeight < 300) return false;
    const source = image.currentSrc || image.src || '';
    const box = image.getBoundingClientRect();
    const style = getComputedStyle(image);
    return /si\.geilicdn\.com\/.+\.(?:jpe?g|png)/i.test(source)
      && style.visibility !== 'hidden'
      && Number(style.opacity || 1) > 0.95
      && box.width >= 120
      && box.height >= 120
      && box.top >= 0
      && box.bottom <= window.innerHeight;
  };

  await page.waitForFunction(isRenderedProductImage, null, { timeout: 45000 });
  await page.evaluate(async () => {
    const image = document.querySelector('.preview-img img.el-image__inner.el-image__preview, .preview-img img');
    if (!image) return;
    try { await image.decode(); } catch (_) {}
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  // The live CDN image is sometimes decoded in the DOM before Chromium paints it into the recorded
  // canvas. A measured post-readiness hold allows the primary image and thumbnail strip to render
  // before the final visible proof frame is captured.
  await wait(page, 9000);
  await page.waitForFunction(isRenderedProductImage, null, { timeout: 5000 });
}

async function openVerifiedKakobuyListing(page, capturesDirectory) {
  const kakobuyButton = page.locator('.detail-buy-btn').filter({ hasText: /kakobuy/i }).first();
  await kakobuyButton.waitFor({ state: 'visible', timeout: 7000 });
  const destination = await kakobuyButton.getAttribute('href');
  if (!destination || !/kakobuy\.com\/item\/details/i.test(destination)) {
    throw new Error('The selected product does not expose a KakoBuy item-details destination.');
  }
  if (selectedProductId && !destination.includes(`itemID%3D${encodeURIComponent(selectedProductId)}`) && !destination.includes(`itemID=${selectedProductId}`)) {
    throw new Error('The clicked KakoBuy URL does not match the verified configured product.');
  }

  // The production page normally opens the third-party destination in a new tab. For a continuous
  // recording, the cursor visibly activates the same control and then opens its exact href in the
  // current tab. This avoids waiting on third-party page-load events that may never settle.
  await moveCursorTo(page, kakobuyButton);
  await wait(page, 115);
  await page.evaluate(() => window.__recordingDemo?.pulseCursor());
  await wait(page, 150);
  await page.goto(destination, { waitUntil: 'commit', timeout: 30000 });
  if (!/https:\/\/www\.kakobuy\.com\/item\/details/i.test(page.url())) {
    throw new Error('The exact generated KakoBuy destination did not open.');
  }

  // Do not end on a skeleton or a URL change. First wait for populated details, then wait for
  // the actual primary image element to decode and remain within the visible mobile viewport.
  await waitForLiveProductDetails(page);
  await waitForVisiblePrimaryProductImage(page);
  // Keep the image-complete product page on screen long enough to make the successful link
  // resolution visually clear in the finished recording.
  await wait(page, 1800);
  await capture(page, capturesDirectory, '04-kakobuy-live-link.png');
}

async function runGuestFlow(page, capturesDirectory) {
  await page.goto('http://127.0.0.1:4173/', { waitUntil: 'domcontentloaded' });
  await page.locator('#searchInput').waitFor({ state: 'visible', timeout: 15000 });
  await page.waitForFunction(() => Boolean(window.__recordingDemo), null, { timeout: 15000 });
  await page.evaluate(() => window.__recordingDemo?.hideCursor());
  await wait(page, 1150);
  await page.evaluate(() => {
    document.getElementById('onboardOverlay')?.classList.remove('show');
    localStorage.setItem('repfind_onboarded', '1');
  });
  await wait(page, 420);
  await capture(page, capturesDirectory, '01-welcome.png');

  const searchInput = page.locator('#searchInput');
  await typeWithCursor(page, searchInput, searchTerm);
  await wait(page, 450);

  const searchButton = page.locator('#sendBtn');
  await clickWithCursor(page, searchButton);
  await page.locator('#chatArea').waitFor({ state: 'visible', timeout: 7000 });

  const cards = page.locator('#resultsList .result-card');
  await cards.first().waitFor({ state: 'visible', timeout: 20000 });
  const cardCount = await cards.count();
  if (!cardCount) throw new Error('The recording search returned no product cards.');

  await positionConfiguredResultForBrowse(page, cardCount);
  const selectedIndex = await chooseResultIndex(page, cardCount);
  const selectedCard = cards.nth(selectedIndex);

  await waitForVisibleProductImages(page, Math.min(2, cardCount));
  await browseResultsImmediately(page, selectedIndex);
  await capture(page, capturesDirectory, '02-results.png');

  await wait(page, 130);
  await clickWithCursor(page, selectedCard);
  await page.locator('#detailPanel.show').waitFor({ state: 'visible', timeout: 7000 });
  await wait(page, 620);
  await capture(page, capturesDirectory, '03-detail.png');

  if (verifyLiveKakobuy) {
    await openVerifiedKakobuyListing(page, capturesDirectory);
    await page.evaluate(() => window.__recordingDemo?.hideCursor());
    await wait(page, 700);
  }
}

module.exports = { runGuestFlow };
