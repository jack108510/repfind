# Preview Quality Findings

The scripted guest-flow preview renders at 1920×1080 and shows four coherent checkpoints: the welcome/search screen, Jordan 4 result list, product detail panel, and a haul panel containing the selected item. Typography, dark-theme contrast, product imagery, and the simulated cursor are legible at the target resolution.

The current haul checkpoint correctly shows the selected Jordan 4 item and estimated total. However, the original page's cart renderer restores an enabled “Open direct product link” button after the local item is added. That button must be disabled and relabeled in the isolated recording copy so the screen video cannot imply or invoke an external purchase action.

The recording remains non-transactional: no sign-in form is completed, no checkout is clicked, and no external purchase link is opened.

## Mobile Preview Findings

The portrait capture is correctly rendered at 1080×1920 using a phone-sized 360×640 CSS viewport and shows the responsive mobile header, detail panel, and haul drawer. The title and primary product detail are legible in portrait orientation.

Two adjustments are required before rendering: the result checkpoint should scroll to show at least one product card rather than only the results heading, and the haul drawer must be relabeled and disabled after it opens because the normal renderer restores the original external-link label when the drawer is toggled. These are local recording-copy changes only.

## First Render Findings

The first MP4 pass encoded successfully as H.264 at 1080×1920, 25 fps, with a 13.16-second duration. Representative frames confirm the responsive UI, cursor movement, and scripted search/haul progression are captured.

The initial frame still contains the source page’s first-visit onboarding modal before the existing flow dismisses it. This differs from the approved preview and should be removed at browser initialization. The recording runner will set the onboarding flag before page scripts execute, then the video will be re-rendered and rechecked.

## Final Haul Safeguard Verification

The refreshed portrait preview confirms that the My Haul drawer retains the selected product, communicates the guest-demo limitation, and visibly disables the checkout control with the label “Demo recording — checkout disabled.” The scripted flow continues to complete without opening an external link, authenticating, or transacting.

## Delivery Verification

The final H.264 MP4 is 1080×1920 at 25 fps with a duration of 13.20 seconds. Final frame review confirms a clean mobile welcome state, search results, product detail, and the final My Haul view. The final My Haul frame visibly carries the guest-demo notice and the disabled “Demo recording — checkout disabled” button. No authentication, external link, or checkout action is performed in the delivered flow.

## Revised Natural-Browse Preview

The revised portrait preview waits for visible result thumbnails, then slowly traverses the loaded product list before selecting a deterministic non-first item. The captured result state shows multiple product images and the cursor positioned over a later card. The selected item is Jordan 4 Bred, which carries through consistently into the product detail and guest-haul views. The slower scripted browse is suitable for the revised mobile render.

## First Slower Render Timing Check

The first slower render completed successfully but ran to 32.60 seconds, longer than intended for a modestly paced browse. The thumbnail-readiness helper was waiting for every image in the visible cards, which can include slow remote images. The helper will be narrowed to require a small minimum count of loaded product thumbnails with a short bounded timeout, followed by the existing deliberate viewing pause. This preserves the user-requested image-load wait while avoiding an excessive hold.

## Final Slower-Render Verification

The updated MP4 is 1080×1920 H.264 at 25 fps and runs for 26.28 seconds. Timing probes confirm the sequence holds while results and thumbnails populate, then presents several loaded result cards during a smooth scroll before opening the varied Jordan 4 Bred item. The product detail and final guest-haul state follow in sequence, with checkout still visibly disabled. The 26-second duration provides a slower browsing rhythm without the excessive all-image wait from the first render.

## Final 1.5-Second Pacing Verification

The final concise MP4 is 1080×1920 H.264 at 25 fps with an 18.68-second duration. The thumbnail readiness pause is fixed at approximately 1.5 seconds, after which the recording displays loaded product cards through a short, readable two-part scroll. The varied Jordan 4 Bred selection, product detail, and disabled guest-haul ending remain intact. This version provides the requested middle ground between the original fast sequence and the longer 26-second version.

## Human-Motion Preview Verification

The revised preview disables the page's built-in auto-scroll and uses two unequal, decelerating cursor-led scroll bursts. A continuous temporary capture was checked for timing and motion: the result listing appears after a short transition, the browse movement reads as a quick irregular swipe rather than a uniform automated scroll, and the Jordan 4 Bred card is visible before opening. The temporary capture duration is 15.12 seconds; this is a preview only, pending user approval for final rendering.

## Final Natural-Motion Render Verification

The approved final MP4 is 1080×1920 H.264 at 25 fps and runs for 15.24 seconds. Continuous playback verification confirms that thumbnails appear promptly, the result browse is an irregular cursor-led gesture with slight pauses rather than an automated uniform sweep, the Jordan 4 Bred card is visible before the detail panel opens, and the guest-haul endpoint keeps checkout visibly disabled.

## Configurable Search Validation

The reusable `recording-config.js` file controls both the typed browser query and the deterministic browser response. An end-to-end mobile preview was run after setting `searchTerm` to `Chrome Hearts`; it produced matching Chrome Hearts product cards and completed the scripted result flow. The delivered configuration was then restored to the default `Jordan 4`, and a second preview plus syntax checks for the configuration, action, and browser-hook scripts completed successfully.

## Pointer-Led Interaction Preview Verification

The refined continuous preview runs for 19.72 seconds. The result browse uses pointer-positioned, unequal wheel gestures with varied speed and short pauses. Continuous playback review confirmed that the visible cursor arrives before the search icon, selected product card, Add to Haul button, mobile menu icon, and My Haul control, with the click pulse shown before each interaction.

## Full-Frame Capture Fix Verification

The prior raw capture used a 360×640 browser viewport with a 1080×1920 Playwright recording canvas, causing the viewport to occupy only the top-left of the raw file. The corrected runner records to a matching 360×640 raw canvas and the new `record:mobile` command scales that raw capture to a 1080×1920 H.264 MP4. A representative delivery frame was checked and the mobile page fills the complete portrait frame.

## Immediate-Browse Live-Link Diagnosis

The first continuous live-link preview successfully resolved the real KakoBuy product page and showed the cursor before the product and agent-link actions, but automated motion review found that the results appeared to jump to the selected card. The likely cause was the source page’s internal `scrollToBottom()` binding continuing to move the chat pane after results rendered. The isolated recording hook now suppresses both the global property and lexical function binding before the next validation pass, so the scripted browse can begin from the visible result list.

## Scroll-Root Correction Verification

The chat pane was not the active scrolling element in the mobile capture: its scroll height equaled its client height, while the document scroll root carried the full result list. The recording action now detects the active scroll root and applies its incremental motion there. The refreshed result checkpoint visibly shows multiple product cards in sequence, including the verified CDG item later in the list, confirming that the browse now traverses actual visible results before selection.

## Full Live-Product Load Verification

The live-link recording no longer relies on a fixed timing pause. It waits for the KakoBuy product page to expose a populated item title, a CNY price, Weidian source attribution, and a loaded product image before the final visible dwell. Continuous playback verification confirmed that all four signals are visible and the resolved listing remains on screen for several seconds, while no sign-in, cart, payment, checkout, or purchase action occurs.

## Primary-Image Paint Diagnosis

The direct-page diagnostic used the same mobile recording browser context and showed that the primary product image is present in the DOM with a successful image response by eight seconds after navigation, but the captured final frame can still show its blank placeholder when the recording proceeds sooner. A 15-second diagnostic frame visibly rendered the main product image and thumbnails. The timing safeguard therefore needs a longer post-readiness paint-and-stability interval rather than only DOM completion checks.

## Refreshed Checkpoint Validation

The earlier blank `preview-mobile/04-kakobuy-live-link.png` was stale because the raw-video runner deliberately does not create preview screenshots. After running the dedicated `preview:mobile` workflow with the new nine-second post-readiness paint hold, the regenerated checkpoint visibly shows the live product’s primary photo and populated thumbnail strip. This validates the timing safeguard in the same 360×640 mobile browser configuration.

## Final Live-Link Delivery Verification

The QA-approved raw capture runs for 33.84 seconds. Its extracted endpoint frame visibly contains the loaded primary product photo, complete thumbnail strip, CNY ¥73 price, and Weidian attribution on the real KakoBuy listing. Automated visual review also confirmed the configured search term, immediate irregular result browsing, cursor-led activations, non-transactional behavior, and the photo-complete live endpoint with no visual defects. The delivery MP4 was encoded from that exact raw capture as H.264, 1080×1920, yuv420p, at 25 fps. The accompanying four-stage contact sheet shows welcome/search, natural browsing, product selection, and the fully rendered live-link page.
