#!/usr/bin/env node
/**
 * Records a mobile-format screen capture of repfind.ca searches.
 * Uses Puppeteer to drive the page + screenshots every 100ms,
 * then ffmpeg stitches them into an MP4.
 * 
 * Output: /tmp/repfind_mobile_demo.mp4 (portrait 9:16)
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const FRAME_DIR = '/tmp/repfind_frames';
const OUTPUT = '/tmp/repfind_mobile_demo.mp4';
const WIDTH = 390;   // iPhone 14 Pro width
const HEIGHT = 844;  // iPhone 14 Pro height

// Search queries to demonstrate
const SEARCHES = [
  'jordan 4',
];

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function clearFrameDir() {
  if (fs.existsSync(FRAME_DIR)) {
    fs.rmSync(FRAME_DIR, { recursive: true });
  }
  fs.mkdirSync(FRAME_DIR, { recursive: true });
}

async function typeWithDelay(page, selector, text, delay = 120) {
  // Focus already done by caller, just type
  for (const char of text) {
    await page.keyboard.type(char);
    // Humans don't type at perfectly even intervals
    const jitter = Math.random() * 90 - 20; // -20ms to +70ms
    await sleep(delay + jitter);
    // Occasional brief pause (like thinking between words)
    if (char === ' ') {
      await sleep(200 + Math.random() * 200);
    }
  }
}

async function captureLoop(page, label, durationMs) {
  const frames = [];
  const start = Date.now();
  let frameNum = fs.readdirSync(FRAME_DIR).length;
  
  while (Date.now() - start < durationMs) {
    const filename = path.join(FRAME_DIR, `frame_${String(frameNum).padStart(6, '0')}.png`);
    try {
      await page.screenshot({ path: filename, type: 'png' });
      frames.push(filename);
      frameNum++;
    } catch (e) {
      // page might be mid-scroll
    }
    await sleep(80); // ~12fps
  }
  return frames;
}

// ---------------------------------------------------------------------------
// Human-like scrolling helpers
//
// Real humans don't scroll in fixed 200px jumps with exact 400ms waits.
// They flick, swipe, overshoot, pause to read, and vary their speed.
// These helpers break each scroll gesture into many tiny sub-steps with
// eased velocity so the captured frames reproduce smooth, natural motion.
// ---------------------------------------------------------------------------

function randRange(min, max) {
  return min + Math.random() * (max - min);
}

function randInt(min, max) {
  return Math.floor(randRange(min, max + 1));
}

async function captureFrame(page) {
  const frameNum = fs.readdirSync(FRAME_DIR).length;
  await page.screenshot({
    path: path.join(FRAME_DIR, `frame_${String(frameNum).padStart(6, '0')}.png`),
    type: 'png',
  });
}

// Scroll the window by `totalDistance` px (positive = down, negative = up),
// broken into `subSteps` eased micro-movements. A frame is captured after
// every micro-movement so the video shows continuous motion rather than jumps.
async function humanScrollWindow(page, totalDistance, subSteps) {
  const direction = totalDistance >= 0 ? 1 : -1;
  const magnitude = Math.abs(totalDistance);
  const perStep = magnitude / subSteps;

  for (let i = 0; i < subSteps; i++) {
    // Ease: accelerate toward the middle of the gesture, decelerate at the ends,
    // like a finger fling that ramps up and settles down.
    const progress = (i + 1) / subSteps;
    const weight = Math.sin(progress * Math.PI); // 0 -> 1 -> 0
    const eased = perStep * (0.35 + 0.65 * weight) + randRange(-12, 12);

    await page.evaluate((d) => {
      window.scrollBy({ top: d, behavior: 'auto' });
    }, Math.round(direction * eased));

    await captureFrame(page);
    // Tiny variable gap between micro-movements keeps momentum feeling alive.
    await sleep(randRange(22, 65));
  }
}

// Same idea, but scrolls a scrollable element (e.g. the detail panel) instead
// of the whole window. Falls back silently if the element isn't found.
async function humanScrollElement(page, selector, totalDistance, subSteps) {
  const exists = await page.evaluate((sel) => !!document.querySelector(sel), selector);
  if (!exists) return false;

  const direction = totalDistance >= 0 ? 1 : -1;
  const magnitude = Math.abs(totalDistance);
  const perStep = magnitude / subSteps;

  for (let i = 0; i < subSteps; i++) {
    const progress = (i + 1) / subSteps;
    const weight = Math.sin(progress * Math.PI);
    const eased = perStep * (0.35 + 0.65 * weight) + randRange(-8, 8);

    await page.evaluate((sel, d) => {
      const el = document.querySelector(sel);
      if (el) el.scrollTop += d;
    }, selector, Math.round(direction * eased));

    await captureFrame(page);
    await sleep(randRange(22, 65));
  }
  return true;
}

// Drive a full natural scroll session down the page: a variable number of
// gestures, each with its own distance/speed, occasional overshoot-and-correct,
// and variable "reading" pauses between swipes.
async function humanScrollSequence(page, opts = {}) {
  const {
    minGestures = 6,
    maxGestures = 11,
  } = opts;

  const gestures = randInt(minGestures, maxGestures);
  let totalScrolled = 0;

  for (let i = 0; i < gestures; i++) {
    const roll = Math.random();
    let distance, subSteps, postDelay;

    if (roll < 0.5) {
      // Ordinary swipe — the most common gesture.
      distance = randRange(180, 340);
      subSteps = randInt(4, 7);
      postDelay = randRange(250, 600);
    } else if (roll < 0.78) {
      // Small flick / nudge to peek a little further.
      distance = randRange(60, 160);
      subSteps = randInt(3, 5);
      postDelay = randRange(150, 380);
    } else {
      // A long, fast fling covering a lot of ground.
      distance = randRange(380, 560);
      subSteps = randInt(6, 9);
      postDelay = randRange(420, 850);
    }

    totalScrolled += distance;

    // Occasionally overshoot slightly, then correct back up — very human.
    const doOvershoot = Math.random() < 0.25 && i < gestures - 1;
    let overshootPx = 0;
    if (doOvershoot) {
      overshootPx = randRange(25, 65);
    }

    await humanScrollWindow(page, distance + overshootPx, subSteps);

    if (doOvershoot) {
      await sleep(randRange(60, 150));           // brief settle at the overshoot
      await humanScrollWindow(page, -overshootPx, randInt(2, 4)); // correct back
    }

    // Sometimes linger longer as if actually reading the content.
    if (Math.random() < 0.3) {
      postDelay += randRange(450, 1300);
    }
    await sleep(postDelay);
  }

  return totalScrolled;
}

async function main() {
  await clearFrameDir();
  
  console.log('Launching browser in mobile mode...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: [
      `--window-size=${WIDTH},${HEIGHT}`,
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--force-device-scale-factor=2',
    ],
  });

  const page = await browser.newPage();
  await page.setViewport({
    width: WIDTH,
    height: HEIGHT,
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  });

  // Set a mobile user agent
  await page.setUserAgent(
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
  );

  console.log('Navigating to repfind.ca...');
  
  // Start capturing during page load
  const loadPromise = page.goto('https://repfind.ca', { 
    waitUntil: 'networkidle2',
    timeout: 30000,
  });
  
  // Capture the loading briefly
  await sleep(500);
  const loadFrames = await captureLoop(page, 'loading', 1500);
  console.log(`Captured ${loadFrames.length} frames during load`);

  // Wait for the page to fully load
  console.log('Waiting for page to fully load...');
  await page.waitForSelector('#searchInput', { visible: true, timeout: 60000 }).catch(() => {});
  
  await sleep(500);

  // Capture the homepage briefly
  console.log('Capturing homepage...');
  const homeFrames = await captureLoop(page, 'home', 1000);
  console.log(`Homepage frames: ${homeFrames.length}`);

  // Run searches
  for (const query of SEARCHES) {
    console.log(`Searching: "${query}"`);
    
    // Target the specific search input by ID
    const inputSelector = '#searchInput';
    
    // Wait for the input to exist and be visible
    await page.waitForSelector(inputSelector, { visible: true, timeout: 10000 }).catch(() => {});
    
    // Click it using Puppeteer's click (not evaluate)
    await page.click(inputSelector, { clickCount: 3 }).catch(() => {}); // triple-click to select all
    await sleep(200);
    await page.keyboard.press('Backspace').catch(() => {}); // clear
    await sleep(300);
    
    // Type each character with human delay + capture frames
    for (const char of query) {
      await page.keyboard.type(char);
      const jitter = Math.random() * 90 - 20;
      await sleep(120 + jitter);
      if (char === ' ') {
        await sleep(200 + Math.random() * 200);
      }
      // Capture 3 frames per keystroke so each letter stays visible ~0.3s at 10fps
      const frameNum = fs.readdirSync(FRAME_DIR).length;
      const screenshotPath = path.join(FRAME_DIR, `frame_${String(frameNum).padStart(6, '0')}.png`);
      await page.screenshot({ path: screenshotPath, type: 'png' });
      // Duplicate it 2 more times so the letter lingers
      fs.copyFileSync(screenshotPath, path.join(FRAME_DIR, `frame_${String(frameNum+1).padStart(6, '0')}.png`));
      fs.copyFileSync(screenshotPath, path.join(FRAME_DIR, `frame_${String(frameNum+2).padStart(6, '0')}.png`));
    }
    await sleep(300);
    
    // Press enter to search
    await page.keyboard.press('Enter');
    
    // Wait for AI results to actually appear
    console.log(`  Waiting for results...`);
    await page.waitForSelector('.result-card', { visible: true, timeout: 15000 }).catch(() => {});
    await sleep(500);
    console.log(`  Results loaded`);
    
    // Slow continuous scroll for 3 seconds
    console.log(`  Slow scroll...`);
    const scrollStart = Date.now();
    while (Date.now() - scrollStart < 3000) {
      await page.evaluate(() => window.scrollBy({ top: 8, behavior: 'auto' }));
      const frameNum = fs.readdirSync(FRAME_DIR).length;
      await page.screenshot({ 
        path: path.join(FRAME_DIR, `frame_${String(frameNum).padStart(6, '0')}.png`), 
        type: 'png' 
      });
      await sleep(50);
    }
  }

  await browser.close();
  
  const totalFrames = fs.readdirSync(FRAME_DIR).length;
  console.log(`\nTotal frames captured: ${totalFrames}`);
  console.log(`Frame directory: ${FRAME_DIR}`);
  
  // Now stitch with ffmpeg
  console.log('\nStitching frames into video...');
  const { execSync } = require('child_process');
  
  // Calculate FPS based on total duration
  // ~45 seconds of content, want it around 10fps
  const fps = 10;
  
  try {
    execSync(
      `ffmpeg -y -framerate ${fps} -i ${FRAME_DIR}/frame_%06d.png ` +
      `-vf "scale=390:844" -c:v libx264 -pix_fmt yuv420p ` +
      `-preset fast -crf 20 ${OUTPUT}`,
      { stdio: 'inherit' }
    );
    console.log(`\n✅ Video saved to: ${OUTPUT}`);
    
    // Check file size
    const stats = fs.statSync(OUTPUT);
    console.log(`Size: ${(stats.size / 1024 / 1024).toFixed(1)} MB`);
  } catch (e) {
    console.error('ffmpeg error:', e.message);
  }
}

main().catch(console.error);
