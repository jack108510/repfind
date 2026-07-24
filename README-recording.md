# repfind Portrait Mobile Screen Recording

This package contains the isolated, editable recording workflow for the delivered mobile demo.

## Delivered flow

The recording uses a 1080×1920, 9:16 portrait layout and demonstrates the following guest sequence:

1. Open the mobile welcome screen.
2. Search for the term defined in `recording-config.js` (default: `Jordan 4`).
3. Let the visible thumbnails load promptly, then browse the local results with two unequal cursor-led scroll bursts and a short hover before selection.
4. Open a deterministic non-first matching product detail panel.
5. Add the selected item to a display-only guest haul.
6. Open the haul panel.

No sign-in, checkout, external purchasing link, or transaction is performed. The final haul view explicitly disables checkout.

## Included files

| File | Purpose |
|---|---|
| `index.html`, `logo.png`, `data/products.json` | Local website and product-catalog source used for the demo. |
| `recording-config.js` | **Change this file** to set the scripted search term. |
| `recording-demo.js` | Deterministic local behavior, cursor overlay, and guest-haul safety guard. |
| `recording-actions.js` | Reusable scripted interaction sequence. |
| `recording-server.js` | Local static server. |
| `preview-recording-mobile.js` | Generates mobile checkpoint screenshots. |
| `record-screen-demo-mobile.js` | Captures the mobile raw browser video. |
| `qa-findings.md` | Preview and delivery validation notes. |

## Change the search term

Open `recording-config.js` and change the one value at the top:

```js
const recordingConfig = {
  searchTerm: 'Jordan 4'
};
```

For example, change it to `searchTerm: 'Chrome Hearts'`, save the file, then run a preview or recording command. Use a term represented in `data/products.json`; otherwise, the result list may not contain enough cards for the scripted browse-and-select step.

## Reproduce

Install dependencies with `pnpm install --ignore-scripts`. Start the local server with `pnpm serve`. In another terminal, run `pnpm preview:mobile` to generate screenshots or `pnpm record:mobile` to capture a raw `.webm` file. Convert the raw capture to the MP4 delivery format with:

```bash
ffmpeg -y -i output/repfind-mobile-screen-recording.webm \
  -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
  -movflags +faststart output/repfind-mobile-screen-recording.mp4
```

The recording driver expects Chromium at `/usr/bin/chromium` and a local server on `http://127.0.0.1:4173/`.
