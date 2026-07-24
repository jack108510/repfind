const fs = require('fs');

/*
 * Resolves the Chromium binary used by the preview and recording drivers.
 * Override with REPFIND_CHROMIUM when the browser lives somewhere else.
 */
const candidates = [
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium'
];

function resolveChromiumPath() {
  const override = process.env.REPFIND_CHROMIUM;
  if (override) {
    if (!fs.existsSync(override)) throw new Error(`REPFIND_CHROMIUM is set to a missing binary: ${override}`);
    return override;
  }
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  if (!found) throw new Error(`No Chromium binary found. Checked: ${candidates.join(', ')}`);
  return found;
}

module.exports = { resolveChromiumPath };
