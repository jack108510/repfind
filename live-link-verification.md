# Live KakoBuy Link Verification

## Selected catalog record

- Product: `Jordan 4 Bred`
- Source platform: `weidian`
- Source item ID: `6564607798`
- Generated KakoBuy destination:
  `https://www.kakobuy.com/item/details?url=https%3A%2F%2Fweidian.com%2Fitem.html%3FitemID%3D6564607798&source=WD&affcode=cq43b`

## Non-transactional browser check

The exact generated URL resolved to the `www.kakobuy.com/item/details` route and loaded the KakoBuy site shell without a login, cart, payment, or checkout interaction. On the initial rendered state, the site showed a loading skeleton in the product area rather than a populated product listing. A further wait is required before treating the product content itself as successfully resolved.

## Additional live checks

- `Jordan 4 Bred` (`weidian` ID `6564607798`) opened the real KakoBuy item route and resolved to a populated product-detail page, but its media region displayed `FAILED` and the fetched listing title/price were incomplete (`X A*r J*rdan 4, Black Fire RED 308497 060`, CNY ¥0).
- `Jordan 4 Oklahoma Sooners PE` (`weidian` ID `6564076764`) opened the real KakoBuy item route but resolved to the explicit unavailable state: `This product may not exist.`

These checks establish that the page constructs and opens actual KakoBuy routes. They do not support claiming that every historical catalog record is currently purchasable. The recording should either use a currently populated result after validation or accurately display the live link opening without suggesting availability or purchase completion.

## Request-path inspection

The live KakoBuy item page loaded its product data through `https://hbapi.kakobuy.com/api/sapi/item`. The page’s non-transactional reload control was instrumented so the request shape can be inspected without using any sign-in, shopping-cart, payment, or checkout functionality.

- A newer Weidian catalog item, `Comme des Garçons Play Heart Print Pink T-Shirt` (ID `7778860787`), was opened through the same generated KakoBuy route. Its initial state showed the normal KakoBuy product loading skeleton; a follow-up wait is required before classifying the item as resolved or unavailable.

## Verified usable listing for the recording

A current catalog record resolved successfully through its generated KakoBuy route: `Comme des Garçons Play Heart Print Pink T-Shirt` (Weidian ID `7778860787`). The destination displayed a product image gallery, seller information, a sourced Weidian link, color and size variants, and a live fetched price of CNY ¥73 (approximately US$11.68 at the page’s displayed conversion). No login, shopping-cart, payment, or checkout control was used. This is the appropriate record to demonstrate that the direct-link path resolves to an actual product listing.

## Continuous recording verification

The revised non-transactional sequence opened the exact generated KakoBuy destination for the configured catalog item (`https://www.kakobuy.com/item/details?url=https%3A%2F%2Fweidian.com%2Fitem.html%3FitemID%3D7778860787&source=WD&affcode=cq43b`) after the user-visible cursor click. Continuous playback review confirmed that the result list begins moving shortly after results appear, scrolls visibly slowly and continuously, shows the cursor before product and link actions, and ends on a resolved KakoBuy product listing with product images, pricing, and specifications. No sign-in, cart, checkout, payment, or order-submission action was performed.

## Product-load readiness markers

The live AkoBuy product page exposes stable non-transactional readiness signals after its item data resolves: a visible product-title element (`span.item-title`), a visible source label (`Source of the product :` inside `.item_youks`), a populated product price in the detail region, and a loaded primary product image with a non-zero natural size. The recording can wait for these signals together rather than relying on a fixed delay or only the document-ready state.
