const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const outputDirectory = path.join(__dirname, 'output', 'kakobuy-image-debug');
const destination = 'https://www.kakobuy.com/item/details?url=https%3A%2F%2Fweidian.com%2Fitem.html%3FitemID%3D7778860787&source=WD&affcode=cq43b';
const MOBILE_VIEWPORT = { width: 360, height: 640 };

async function inspectPrimaryImage(page) {
  return page.evaluate(() => {
    const images = [...document.images].map((image, index) => {
      const box = image.getBoundingClientRect();
      const style = getComputedStyle(image);
      return {
        index,
        selectorLike: `${image.parentElement?.className || ''} > ${image.className || image.tagName}`,
        src: image.currentSrc || image.src || '',
        complete: image.complete,
        naturalWidth: image.naturalWidth,
        naturalHeight: image.naturalHeight,
        width: Math.round(box.width),
        height: Math.round(box.height),
        top: Math.round(box.top),
        left: Math.round(box.left),
        opacity: style.opacity,
        visibility: style.visibility,
        display: style.display
      };
    });
    return images.filter((item) => /preview-img|el-image__preview/i.test(item.selectorLike) || item.width > 100);
  });
}

async function main() {
  fs.rmSync(outputDirectory, { recursive: true, force: true });
  fs.mkdirSync(outputDirectory, { recursive: true });

  const browser = await chromium.launch({
    executablePath: '/usr/bin/chromium',
    headless: true,
    args: ['--disable-background-networking', '--disable-component-update', '--disable-default-apps', '--no-first-run', '--password-store=basic']
  });

  try {
    const context = await browser.newContext({
      viewport: MOBILE_VIEWPORT,
      screen: MOBILE_VIEWPORT,
      deviceScaleFactor: 3,
      isMobile: true,
      hasTouch: true,
      colorScheme: 'dark',
      locale: 'en-US'
    });
    const page = await context.newPage();
    await page.goto(destination, { waitUntil: 'commit', timeout: 30000 });

    const checks = [];
    for (const milliseconds of [3000, 8000, 15000]) {
      await page.waitForTimeout(milliseconds - (checks.length ? [3000, 8000, 15000][checks.length - 1] : 0));
      const state = await inspectPrimaryImage(page);
      const name = `${milliseconds}ms`;
      await page.screenshot({ path: path.join(outputDirectory, `${name}.png`), fullPage: false });
      checks.push({ milliseconds, state });
    }

    fs.writeFileSync(path.join(outputDirectory, 'primary-image-state.json'), `${JSON.stringify(checks, null, 2)}\n`);
    console.log(path.join(outputDirectory, 'primary-image-state.json'));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
