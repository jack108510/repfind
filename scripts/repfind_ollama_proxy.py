#!/usr/bin/env python3
"""CORS-safe repfind chat proxy backed by Claude API.

Public browser -> Cloudflare Tunnel -> this proxy -> Claude API.
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
CLAUDE_URL = os.environ.get("CLAUDE_URL", "https://api.anthropic.com/v1/messages")
CLAUDE_KEY = os.environ.get("CLAUDE_KEY", "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")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
ALLOWED_ORIGINS = [
    "https://jack108510.github.io",
    "http://repfind.ca",
    "https://repfind.ca",
    "http://www.repfind.ca",
    "https://www.repfind.ca",
]
LOG_PATH = os.environ.get("REPFIND_PROXY_LOG", "/tmp/repfind-claude-proxy.log")

SYSTEM_PROMPT = """You are repfind, the AI rep plug for finding reps on Weidian, Taobao, and 1688.
Confident, casual, plugged in. Short responses (1-3 sentences).

CRITICAL RULE: You carry EVERYTHING. Sneakers, streetwear, watches, bags, jewelry, electronics, home decor — ALL categories. NEVER tell a user you don't carry something. NEVER redirect someone away from their request. If they ask for a watch, help them find a watch. If they ask for a bag, help them find a bag. NO EXCEPTIONS.

Your job is to interpret a user's request and return STRICT JSON only.
No markdown. No prose outside JSON.

Schema:
{
  "action": "search" | "clarify",
  "search_query": "short product search query or null",
  "reply": "short helpful assistant sentence",
  "chips": ["optional follow-up option"]
}

CATALOG - WE HAVE (66K+ products, 184 categories):
- Sneakers: Nike, Jordan, Adidas, Yeezy, New Balance, Kobe, Asics, Bape, Travis Scott, Off-White, Sacai, Vans, Balenciaga, Bapesta, SB Dunk
- Streetwear: hoodies, tees, jackets, pants, shorts - Bape, Supreme, Stussy, Human Made, Fear of God/Essentials, Chrome Hearts, Travis Scott, Off-White
- Bags: totes, crossbody, clutch, backpacks, handbags, messenger, belt bags, wallet, luggage (LV, Gucci, Prada, Dior, Chanel)
- Watches: Rolex, AP, Patek Philippe, Omega, Cartier, Hublot, Richard Mille — ALL brands
- Jewelry: necklaces, bracelets, rings, brooches, earrings, cuban links, fine jewelry
- Sunglasses & eyewear: optical frames, prescription glasses
- Formal wear: suits, dress shirts, ties, bow ties, dress shoes
- Dresses, skirts, womenswear
- Electronics: smart speakers, headphones, earphones, chargers, phone cases
- Swimwear, sleepwear, activewear
- Hats, caps, beanies, scarves, gloves, belts, wallets
- Perfume & fragrance
- Home accessories, decor, organizers

DECISION RULES:
- If the user asks for a specific product with enough detail, SEARCH immediately.
- Only CLARIFY if the query is genuinely ambiguous.
- NEVER say "we don't carry" or "we focus on" or "not our thing" — we carry EVERYTHING.
- SEARCH examples: jordan 1 chicago, triple white air forces, rolex submariner, AP royal oak, patek nautilus, gucci tote bag, cuban link chain, bape hoodie
- CLARIFY examples: shoes (what brand?), watch (which brand/model?), bag (what style?)
- When clarifying, chips should suggest specific products we carry.
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


def ask_claude(message: str, history: list | None) -> dict:
    history = history or []
    msgs = []
    for h in history[-10:]:
        msgs.append({"role": h.get("role", "user"), "content": str(h.get("content", ""))})
    msgs.append({"role": "user", "content": message})

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 400,
        "system": SYSTEM_PROMPT,
        "messages": msgs,
    }
    req = urllib.request.Request(
        CLAUDE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {CLAUDE_KEY}",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    content = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            content += block.get("text", "")
    parsed = extract_json(content)
    if not parsed:
        return fallback(message, f"claude returned non-json: {content[:200]!r}")

    action = parsed.get("action") if parsed.get("action") in {"search", "clarify"} else "search"
    search_query = str(parsed.get("search_query") or "").strip()[:140] or None
    reply = str(parsed.get("reply") or "What are you looking for?").strip()[:500]
    chips = parsed.get("chips") if isinstance(parsed.get("chips"), list) else []
    chips = [str(c).strip()[:60] for c in chips[:6] if str(c).strip()]
    return {"action": action, "search_query": search_query, "reply": reply, "chips": chips}


class Handler(BaseHTTPRequestHandler):
    server_version = "repfind-claude-proxy/2.0"

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
            self.wfile.write(json.dumps({"ok": True, "model": CLAUDE_MODEL, "service": "repfind-claude-proxy"}).encode())
        else:
            self._headers(404)
            self.wfile.write(b'{"error":"not found"}')

    def do_POST(self) -> None:
        if not self.path.startswith("/webhook/repfind-chat") and not self.path.startswith("/repfind-chat"):
            self._headers(404)
            self.wfile.write(b'{"error":"not found"}')
            return
        message = ""
        try:
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(min(length, 1024 * 1024)).decode("utf-8", errors="replace")
            payload = json.loads(body) if body else {}
            message = str(payload.get("message") or payload.get("query") or "").strip()
            if not message:
                out = {"action": "clarify", "search_query": None, "reply": "What are you looking for? Sneakers, hoodies, jackets?", "chips": ["Sneakers", "Hoodies", "Jackets"]}
            else:
                out = ask_claude(message, payload.get("history"))
            log(f"ok path={self.path!r} msg={message[:80]!r} out={out}")
            self._headers(200)
            self.wfile.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            log(f"error {type(exc).__name__}: {exc}")
            self._headers(200)
            try:
                out = fallback(message, str(exc))
            except Exception:
                out = {"action": "search", "search_query": "reps", "reply": "I searched repfind.", "chips": []}
            self.wfile.write(json.dumps(out).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        log(format % args)


if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    log(f"starting host={HOST} port={PORT} model={CLAUDE_MODEL}")
    print(f"repfind claude proxy listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()
