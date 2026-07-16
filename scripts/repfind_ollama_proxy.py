#!/usr/bin/env python3
"""CORS-safe repfind chat proxy backed by local Ollama.

Public browser -> Cloudflare Tunnel -> this proxy -> local Ollama.
Returns the same JSON shape the repfind frontend expects from the old n8n webhook.
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
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
MODEL = os.environ.get("REPFIND_OLLAMA_MODEL", "repfind:latest")
ALLOWED_ORIGIN = os.environ.get("REPFIND_ALLOWED_ORIGIN", "https://jack108510.github.io")
LOG_PATH = os.environ.get("REPFIND_PROXY_LOG", "/tmp/repfind-ollama-proxy.log")

SYSTEM_PROMPT = """You are the repfind shopping assistant.
Your job is to interpret a user's rep product request and return STRICT JSON only.
No markdown. No prose outside JSON.

Schema:
{
  "action": "search" | "clarify",
  "search_query": "short product search query",
  "reply": "short helpful assistant sentence",
  "chips": ["optional follow up chip", "optional follow up chip"]
}

Rules:
- Prefer action "search" for concrete product/category requests.
- Use a concise search_query with brand/product/category keywords only.
- Use action "clarify" only when the user is genuinely ambiguous.
- If unsure, search anyway using the best concise query.
"""


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def cors_origin(origin: str | None) -> str:
    if origin == ALLOWED_ORIGIN:
        return origin or ALLOWED_ORIGIN
    # Allow local smoke tests and direct curls while keeping production locked to GitHub Pages.
    if origin and (origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")):
        return origin
    return ALLOWED_ORIGIN


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


def ask_ollama(message: str, history: list | None) -> dict:
    history = history or []
    recent = []
    for item in history[-6:]:
        role = item.get("role") if isinstance(item, dict) else None
        content = item.get("content") if isinstance(item, dict) else None
        if role in {"user", "assistant"} and content:
            recent.append({"role": role, "content": str(content)[:500]})

    payload = {
        "model": MODEL,
        "stream": False,
        "options": {"temperature": 0.15, "num_ctx": 2048},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *recent,
            {"role": "user", "content": message},
        ],
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    msg = data.get("message") or {}
    content = msg.get("content") if isinstance(msg, dict) else ""
    content = content or data.get("response") or ""
    parsed = extract_json(content)
    if not parsed:
        return fallback(message, f"ollama returned non-json: {content[:200]!r}")

    action = parsed.get("action") if parsed.get("action") in {"search", "clarify"} else "search"
    search_query = str(parsed.get("search_query") or message).strip()[:140]
    reply = str(parsed.get("reply") or f"I searched repfind for \"{search_query}\".").strip()[:500]
    chips = parsed.get("chips") if isinstance(parsed.get("chips"), list) else []
    chips = [str(c)[:60] for c in chips[:6] if str(c).strip()]
    return {"action": action, "search_query": search_query, "reply": reply, "chips": chips}


class Handler(BaseHTTPRequestHandler):
    server_version = "repfind-ollama-proxy/1.0"

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
            self.wfile.write(json.dumps({"ok": True, "model": MODEL, "service": "repfind-ollama-proxy"}).encode())
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
                out = {"action": "clarify", "search_query": "", "reply": "What are you looking for?", "chips": ["hoodies", "sneakers", "room decor"]}
            else:
                out = ask_ollama(message, payload.get("history"))
            log(f"ok path={self.path!r} msg={message[:80]!r} out={out}")
            self._headers(200)
            self.wfile.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))
        except Exception as exc:
            log(f"error {type(exc).__name__}: {exc}")
            self._headers(200)
            # Keep frontend alive even if Ollama is temporarily slow.
            try:
                out = fallback(message, str(exc))
            except Exception:
                out = {"action": "search", "search_query": "reps", "reply": "I searched repfind.", "chips": []}
            self.wfile.write(json.dumps(out).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        log(format % args)


if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    log(f"starting host={HOST} port={PORT} model={MODEL} ollama={OLLAMA_URL}")
    print(f"repfind ollama proxy listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()
