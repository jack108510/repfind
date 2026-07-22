#!/usr/bin/env python3
"""CORS-safe repfind chat + embed proxy backed by local Ollama.

Public browser -> Cloudflare Tunnel -> this proxy -> Ollama.
Returns JSON the repfind frontend expects.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("REPFIND_PROXY_HOST", "127.0.0.1")
PORT = int(os.environ.get("REPFIND_PROXY_PORT", "8787"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "repfind:latest")
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
ALLOWED_ORIGINS = [
    "https://jack108510.github.io",
    "http://repfind.ca",
    "https://repfind.ca",
    "http://www.repfind.ca",
    "https://www.repfind.ca",
]
LOG_PATH = os.environ.get("REPFIND_PROXY_LOG", "/tmp/repfind-ollama-proxy.log")

SYSTEM_PROMPT = """You are repfind, the AI plug for finding replica products on Weidian, Taobao, and 1688.
Confident, casual, plugged in. Short responses (1-3 sentences).

═══ WHAT REPFIND CARRIES ═══
We have 66,000+ products across 14 categories:

FASHION & APPAREL:
- Sneakers & shoes: Nike, Jordan, Adidas, Yeezy, New Balance, Kobe, ASICS, Balenciaga, Bape, Travis Scott, Off-White, Sacai, Vans, Dior, SB Dunk, Air Force 1, Air Max
- Streetwear: hoodies, tees, jackets, pants, shorts, sweatpants — Bape, Supreme, Stussy, Human Made, Fear of God/Essentials, Chrome Hearts, Travis Scott, Off-White, Gallery Dept, Vlone
- Designer clothing: LV, Gucci, Prada, Dior, Dolce & Gabbana, Balmain, Moncler, Givenchy shirts, tees, jackets, vests, puffers
- Dresses & skirts: 500+ dresses and skirts
- Jerseys: 4,958 jerseys — NBA, NFL, soccer, and more
- Swimwear: 345 bikinis, one-pieces, and swim trunks

ACCESSORIES:
- Bags & wallets: 2,700+ totes, backpacks, crossbody bags, wallets, chain bags (LV, Gucci, Prada, Dior, Chanel)
- Watches: 197 luxury watches — Rolex, AP, Patek Philippe, Omega, Cartier, Hublot, Richard Mille, Breitling
- Jewelry: 672 necklaces, 643 bracelets, 433 rings, 272 earrings — cuban links, chains, pendants
- Sunglasses & eyewear: 701 sunglasses and 111 optical frames (LV, Dior, Gucci, Oakley)
- Hats & caps: 1,136 baseball caps, 159 bucket hats, 85 beanies
- Socks: 1,157 pairs
- Belts: 361 belts — Gucci, LV, canvas, leather
- Scarves & wraps: 108 scarves — silk, cashmere, Burberry, LV
- Fragrances: 176 perfumes and colognes — Dior, Chanel, Givenchy, Sauvage

ELECTRONICS & TECH:
- Smartwatches & sports watches: 117 — Apple Watch Series, Watch Ultra, sports watches
- TWS earbuds: 71 — AirPods, wireless earbuds
- Bluetooth speakers: 41 portable speakers
- Phone cases, chargers, and accessories

HOME:
- Home decor: 200+ rugs, lamps, pillows, decorative pieces

═══ WHAT WE DON'T CARRY — REJECT THESE ═══
- Laptops, computers, tablets, gaming consoles, monitors
- Tools, appliances, kitchen items
- Toys: Lego, action figures, board games
- Pet supplies: cat trees, pet food, dog beds
- Furniture: chairs, tables, desks, couches
- Food, drinks, supplements
- Skincare, makeup, cosmetics
- Books, textbooks, media
- Sports equipment: tennis rackets, bicycles, skateboards
- Garden, outdoor, camping gear
- Instruments: guitars, pianos, drums

REJECTION FORMAT:
- reply: short, redirect to what we DO carry
- action: "clarify"
- search_query: null
- chips: 3-4 things we actually have

═══ IN-SCOPE BEHAVIOR ═══

Your job is to interpret a user's request and return STRICT JSON only.
No markdown. No prose outside JSON. No <think> blocks in output.

Schema:
{"action": "search" | "clarify", "search_query": "short product search query or null", "reply": "short helpful assistant sentence", "chips": ["optional follow-up option"]}

DECISION RULES:
- If the user asks for ANY product type we carry, SEARCH immediately.
- Only CLARIFY for extremely vague queries like "shoes" or "clothes" — never for specific product types.
- SINGLE-WORD PRODUCT TYPES ALWAYS SEARCH: earbuds, smartwatch, speakers, sunglasses, hoodies, jerseys, dresses, perfume, wallets, backpacks → action:search, NOT clarify.
- Electronics are IN SCOPE: earbuds, smartwatch, AirPods, bluetooth speaker, phone case → action:search
- SEARCH examples: earbuds, airpods, jordan 1 chicago, air force 1, rolex submariner, AP royal oak, gucci tote bag, cuban link chain, bape hoodie, airpods pro, samsung earbuds, nba jersey, bikini, cashmere scarf, smartwatch, bluetooth speaker
- CLARIFY examples: shoes (what brand?), bag (what style?), watch (what brand?)
- Keep reply under 200 characters.
"""


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def cors_origin(origin: str | None) -> str:
    if origin and origin in ALLOWED_ORIGINS:
        return origin
    if origin and (origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")):
        return origin
    return ALLOWED_ORIGINS[0]


def fallback(message: str, why: str = "") -> dict:
    query = re.sub(r"[^\w\s\-.'&]", " ", message or "").strip().lower()
    query = re.sub(r"\s+", " ", query)[:120] or "reps"
    if why:
        log(f"fallback why={why!r} query={query!r}")
    return {
        "action": "search",
        "search_query": query,
        "reply": f"I searched repfind for \"{query}\".",
        "chips": []
    }


def extract_json(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
    # Strip <think>...</think> blocks (qwen3 extended thinking)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def ask_ollama(message: str, history: list | None) -> dict:
    history = history or []
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-10:]:
        msgs.append({"role": h.get("role", "user"), "content": str(h.get("content", ""))})
    msgs.append({"role": "user", "content": "/no_think\n" + message})

    payload = {
        "model": CHAT_MODEL,
        "messages": msgs,
        "stream": False,
        "options": {"num_predict": 512},
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    content = data.get("message", {}).get("content", "")
    parsed = extract_json(content)
    if not parsed:
        return fallback(message, f"ollama returned non-json: {content[:200]!r}")

    action = parsed.get("action") if parsed.get("action") in {"search", "clarify"} else "search"
    search_query = str(parsed.get("search_query") or "").strip()[:140] or None
    reply = str(parsed.get("reply") or "What are you looking for?").strip()[:500]
    chips = parsed.get("chips") if isinstance(parsed.get("chips"), list) else []
    chips = [str(c).strip()[:60] for c in chips[:6] if str(c).strip()]
    return {"action": action, "search_query": search_query, "reply": reply, "chips": chips}


def do_embed(text: str) -> dict:
    payload = {"model": EMBED_MODEL, "prompt": text}
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embeddings",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    embedding = data.get("embedding")
    if not isinstance(embedding, list):
        raise ValueError("Ollama returned no embedding")
    return {"embedding": embedding}


class Handler(BaseHTTPRequestHandler):
    server_version = "repfind-ollama-proxy/3.0"

    def _headers(self, status: int = 200, content_type: str = "application/json") -> None:
        origin = self.headers.get("Origin")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", cors_origin(origin))
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Vary", "Origin")
        self.send_header("Content-Type", content_type)
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._headers(204, "text/plain")

    def do_GET(self) -> None:
        if self.path.startswith("/health") or self.path.startswith("/webhook/repfind-chat"):
            self._headers(200)
            self.wfile.write(json.dumps({
                "ok": True,
                "chat_model": CHAT_MODEL,
                "embed_model": EMBED_MODEL,
                "service": "repfind-ollama-proxy"
            }).encode())
        else:
            self._headers(404)
            self.wfile.write(b'{"error":"not found"}')

    def do_POST(self) -> None:
        path = self.path.split("?")[0]

        if path in ("/webhook/repfind-embed", "/repfind-embed"):
            self._handle_embed()
            return

        if not (path.startswith("/webhook/repfind-chat") or path.startswith("/repfind-chat")):
            self._headers(404)
            self.wfile.write(b'{"error":"not found"}')
            return

        self._handle_chat()

    def _handle_chat(self) -> None:
        message = ""
        try:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(min(length, 1024 * 1024)).decode("utf-8", errors="replace")
            payload = json.loads(body) if body else {}
            message = str(payload.get("message") or payload.get("query") or "").strip()
            if not message:
                out = {"action": "clarify", "search_query": None, "reply": "What are you looking for? Sneakers, hoodies, jackets?", "chips": ["Sneakers", "Hoodies", "Jackets"]}
            else:
                out = ask_ollama(message, payload.get("history"))
            log(f"chat path={self.path!r} msg={message[:80]!r} out={out}")
            self._headers(200)
            self.wfile.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            log(f"chat error {type(exc).__name__}: {exc}")
            self._headers(200)
            try:
                out = fallback(message, str(exc))
            except Exception:
                out = {"action": "search", "search_query": "reps", "reply": "I searched repfind.", "chips": []}
            self.wfile.write(json.dumps(out).encode("utf-8"))

    def _handle_embed(self) -> None:
        try:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(min(length, 64 * 1024)).decode("utf-8", errors="replace")
            payload = json.loads(body) if body else {}
            text = str(payload.get("text") or payload.get("prompt") or "").strip()
            if not text:
                self._headers(400)
                self.wfile.write(b'{"error":"text is required"}')
                return
            out = do_embed(text)
            log(f"embed len={len(out.get('embedding', []))} text={text[:60]!r}")
            self._headers(200)
            self.wfile.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            log(f"embed error {type(exc).__name__}: {exc}")
            self._headers(503)
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        log(format % args)


if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    log(f"starting host={HOST} port={PORT} chat={CHAT_MODEL} embed={EMBED_MODEL}")
    print(f"repfind ollama proxy listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()
