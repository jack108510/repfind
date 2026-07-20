# repfind — Product Search for Replicas

## What This Is
repfind.ca is a search engine for replica (rep) products. Users search for sneakers, clothing, electronics, accessories across 66,332 products sourced from Weidian, Taobao, and 1688 (Chinese marketplaces). Results link directly to shipping agents (KakoBuy, CNFans, OopBuy) that buy and ship on the user's behalf.

## Tech Stack
- **Single-page app**: Pure HTML/CSS/JS — no framework, no build step
- **Hosting**: GitHub Pages (static), domain repfind.ca
- **Database**: Supabase (project: xacehhtgvubcqdoltazg)
- **Product data**: `data/products.json` — 66,332 products as arrays: `[name, priceUSD, category, imageURL, platform, itemID]`
- **AI webhook**: n8n at n8n.wildeautomations.com/webhook/repfind-chat (refines queries, may be down — code has fallback)
- **Analytics**: Supabase tables (repfind_searches, repfind_page_views, repfind_events)

## Architecture Constraints
- MUST stay pure HTML — no build tools, no npm, no framework
- `node --check` on extracted JS before EVERY push — one syntax error bricks the site
- Monochrome dark UI (ChatGPT-inspired palette), --accent: #C84B2F (terracotta)
- Search relevance is #1 priority
- Never mock data — always use real products from data/products.json
- Jack's priorities: search relevance > clean UI > everything else

## Current Problems (as of Jul 20, 2026)

### 1. Category/Intent System is Fragile and Hardcoded
- `detectSpecialIntent()` only knows "decor" and "apple_electronics" — misses everything else
- When a category isn't recognized, the "no results" message lies:
  - Says "No Apple electronics yet" when we have 117 smartwatches, 70 earbuds, 40 speakers
  - Says "No decor results" when we have 1680 products with "light" in the name
- There's no proper category taxonomy — categories are raw Chinese strings from the source data

### 2. Product Categories Need Taxonomy
The raw categories from the data are Chinese marketplace categories:
- T恤 (t-shirts), 卫衣 (hoodies), 球衣 (jerseys), 运动裤 (pants), etc.
- 电子产品 (electronics), 智能手表 (smartwatches), 真无线耳机 (TWS earbuds), etc.
These need to be mapped to English categories for filtering and intent detection.

### 3. Search Could Be Smarter
- Two-phase search (recall → rank) works well for sneakers/apparel
- Falls apart for electronics, home goods, accessories — categories it doesn't understand
- Synonyms dictionary is sneaker-focused (AF1, AJ1, TS, etc.) — missing electronics brands

### 4. Analytics Were Just Fixed (Jul 20)
- Column mismatch (session_id vs conversation_id, result_count vs results_count) — FIXED
- RLS blocks page_views and events tables (needs Supabase dashboard fix)
- Searches table now works with publishable key

## Product Data Structure
```json
["Product Name", 10.07, "T恤", "https://image-url...", "weidian", "7778860787"]
```
- Index 0: name (string, often English product names)
- Index 1: price in USD (float)
- Index 2: category (Chinese string from marketplace)
- Index 3: image URL
- Index 4: platform ("weidian", "taobao", "1688")
- Index 5: itemID (string, used for agent links)

## Key Files
- `index.html` — the entire app (4062 lines)
- `data/products.json` — product database (12.8MB, 66,332 products)
- `demo_autoplay.html` — demo recorder version
- `scripts/` — data pipeline scripts

## Supabase
- URL: https://xacehhtgvubcqdoltazg.supabase.co
- Publishable key: sb_publishable_1TNu5hqotJ7GGQXfjliivQ_ttK51EAA
- Tables: repfind_searches (works), repfind_page_views (RLS blocked), repfind_events (RLS blocked), repfind_conversations, ss_calls (unrelated app)
- repfind_searches schema: id, user_id, conversation_id (uuid nullable), query, refined_query, results_count, action, created_at
