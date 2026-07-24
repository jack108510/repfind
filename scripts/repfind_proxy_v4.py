#!/usr/bin/env python3
"""repfind chat proxy v4 — Search-first, AI-filter.

Flow: User types → Search Supabase DB → AI reviews matches → Returns best ones.

Public browser -> Cloudflare Tunnel -> this proxy -> Supabase + Ollama.
Returns JSON the repfind frontend expects.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("REPFIND_PROXY_HOST", "127.0.0.1")
PORT = int(os.environ.get("REPFIND_PROXY_PORT", "8787"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")
EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Supabase config
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://xacehhtgvubcqdoltazg.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_1TNu5hqotJ7GGQXfjliivQ_ttK51EAA")

ALLOWED_ORIGINS = [
    "https://jack108510.github.io",
    "http://repfind.ca",
    "https://repfind.ca",
    "http://www.repfind.ca",
    "https://www.repfind.ca",
]
LOG_PATH = os.environ.get("REPFIND_PROXY_LOG", "/tmp/repfind-ollama-proxy.log")

# Global product cache
_PRODUCTS = None

# Compact system prompt — AI just needs to pick best matches and write a reply
SYSTEM_PROMPT = """Review product search results. Write one casual sentence about what was found.
Output JSON only: {"reply":"casual one sentence","action":"search","chips":["2-3 related terms"],"search_query":"the query"}"""


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
        "reply": f'Searching repfind for "{query}".',
        "chips": []
    }


def extract_json(text: str) -> dict | None:
    text = (text or "").strip()
    if not text:
        return None
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


def search_products(query: str) -> list:
    """Search local products.json — returns all close matches, sorted by relevance."""
    global _PRODUCTS
    if _PRODUCTS is None:
        try:
            import json as _json
            with open(os.path.join(os.path.dirname(__file__), "..", "data", "products.json"), "r", encoding="utf-8") as f:
                _PRODUCTS = _json.load(f)
            log(f"loaded {len(_PRODUCTS)} products from products.json")
        except Exception as e:
            log(f"failed to load products.json: {e}")
            _PRODUCTS = []

    if not _PRODUCTS:
        return []

    query_lower = query.lower()
    words = [w for w in query_lower.split() if len(w) > 1]
    scored = []

    for p in _PRODUCTS:
        name = (p[0] if isinstance(p, list) else p.get("name", "")).lower()
        score = 0
        for w in words:
            if f" {w} " in f" {name} ":
                score += 10  # exact word match
            elif w in name:
                score += 5   # partial match
        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: -x[0])

    # Only keep products with a meaningful relevance score
    # (at least one partial match — score >= 5)
    min_score = 5
    relevant = [(s, p) for s, p in scored if s >= min_score]

    return [p for _, p in relevant]


def resolve_query(message: str, history: list) -> str:
    """Use AI to resolve follow-up messages into a full search query using context.
    Falls back to the original message if AI fails or history is empty."""
    if not history or len(history) < 2:
        return message

    # Quick AI call — "chicago ones" + history of "jordan 1 high tops" → "jordan 1 chicago"
    prompt = f"""Based on this conversation, what product is the user looking for?

Conversation:"""
    for h in history[-6:]:
        role = h.get("role", "user")
        content = str(h.get("content", ""))[:200]
        prompt += f"\n{role}: {content}"
    prompt += f'\nuser: {message}'
    prompt += '\n\nRespond with ONLY the product search query (no explanation, no JSON). Max 6 words.'

    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_predict": 30},
    }

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        content = data.get("message", {}).get("content", "").strip()
        # Clean up — remove quotes, periods, extra text
        content = content.split("\n")[0].strip().strip('"').strip("'").rstrip(".")
        if content and len(content) < 80:
            log(f"resolved query: {message!r} → {content!r}")
            return content
    except Exception as e:
        log(f"resolve_query error: {e}")

    return message


def review_with_ai(query: str, matches: list) -> dict:
    """Send search results to Ollama for review. AI picks best ones + writes reply."""
    if not matches:
        # No results — let AI suggest alternatives
        return {
            "action": "clarify",
            "search_query": None,
            "reply": f'Nothing found for "{query}". Try sneakers, hoodies, bags, or watches.',
            "chips": ["Air Force 1", "Bape hoodie", "LV bag", "Rolex"]
        }

    # Build a compact list of matches for the AI
    product_list = []
    # Send top matches to AI for review (cap at 20 to stay fast)
    review_list = matches[:20] if len(matches) > 20 else matches
    for i, m in enumerate(review_list):
        if isinstance(m, list):
            name = m[0] if len(m) > 0 else ""
            price = m[1] if len(m) > 1 else ""
        elif isinstance(m, dict):
            name = m.get("name", "")
            price = m.get("price", "")
        else:
            name = str(m)
            price = ""
        product_list.append(f"{i}: {name} (${price})")

    ai_input = f"""Query: {query}

Results found ({len(matches)}):
{chr(10).join(product_list)}

Pick the best matches and respond."""

    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": ai_input},
    ]

    payload = {
        "model": CHAT_MODEL,
        "messages": msgs,
        "stream": False,
                "options": {"num_predict": 500},
    }

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        msg = data.get("message", {})
        content = msg.get("content", "")
        # qwen3 sometimes puts the response in "thinking" when content is empty
        if not content.strip():
            content = msg.get("thinking", "")
        parsed = extract_json(content)
        if parsed:
            # Ensure search_query matches the original query
            if not parsed.get("search_query"):
                parsed["search_query"] = query
            if not parsed.get("action"):
                parsed["action"] = "search"
            return parsed
    except Exception as e:
        log(f"Ollama review error: {e}")

    # Fallback: just return the search without AI review
    return {
        "action": "search",
        "search_query": query,
        "reply": f'Showing results for "{query}".',
        "chips": []
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "repfind-proxy/4.0"

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
                "service": "repfind-proxy-v4",
                "mode": "search-first-ai-filter"
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
                out = {
                    "action": "clarify",
                    "search_query": None,
                    "reply": "What are you looking for? Sneakers, hoodies, bags, watches?",
                    "chips": ["Sneakers", "Hoodies", "Bags", "Watches"]
                }
            else:
                history = payload.get("history", [])

                # STEP 0: Resolve follow-up messages using conversation context
                t0 = time.time()
                resolved = resolve_query(message, history)
                resolve_time = time.time() - t0

                # STEP 1: Search products instantly
                t1 = time.time()
                matches = search_products(resolved)
                search_time = time.time() - t1
                log(f"resolve={resolve_time:.2f}s search={search_time:.2f}s query={resolved[:60]!r} matches={len(matches)}")

                # STEP 2: AI reviews matches and picks best ones
                t2 = time.time()
                out = review_with_ai(resolved, matches)
                ai_time = time.time() - t2
                log(f"ai_review={ai_time:.2f}s total={resolve_time+search_time+ai_time:.2f}s reply={out.get('reply','')[:60]!r}")

            self._headers(200)
            self.wfile.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            log(f"chat error {type(exc).__name__}: {exc}")
            self._headers(200)
            try:
                out = fallback(message, str(exc))
            except Exception:
                out = {"action": "search", "search_query": "reps", "reply": "Searching repfind.", "chips": []}
            self.wfile.write(json.dumps(out).encode())

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
            out = self._do_embed(text)
            log(f"embed len={len(out.get('embedding', []))} text={text[:60]!r}")
            self._headers(200)
            self.wfile.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            log(f"embed error {type(exc).__name__}: {exc}")
            self._headers(503)
            self.wfile.write(json.dumps({"error": str(exc)}).encode())

    def _do_embed(self, text: str) -> dict:
        payload = {"model": EMBED_MODEL, "prompt": text}
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        embedding = data.get("embedding")
        if not isinstance(embedding, list):
            raise ValueError("Ollama returned no embedding")
        return {"embedding": embedding}

    def log_message(self, format: str, *args) -> None:
        log(format % args)


if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    log(f"starting v4 host={HOST} port={PORT} model={CHAT_MODEL} mode=search-first-ai-filter")
    print(f"repfind proxy v4 on http://{HOST}:{PORT} — search-first, AI-filter", flush=True)
    httpd.serve_forever()
