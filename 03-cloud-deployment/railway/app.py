"""
Agent Railway-ready + giao diện web test (mock LLM).
Railway inject PORT env var tự động — agent phải dùng os.getenv("PORT").

Mở trình duyệt vào "/" để chat thử ngay, không cần curl.
"""
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn
from utils.mock_llm import ask

app = FastAPI(title="Agent on Railway", version="1.0.0")
START_TIME = time.time()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Giao diện web test ─────────────────────────────────────
INDEX_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Agent — Test UI</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: linear-gradient(135deg, #1e293b, #0f172a); color: #e2e8f0;
      min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px;
    }
    .card {
      width: 100%; max-width: 640px; background: #1e293b; border: 1px solid #334155;
      border-radius: 16px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,.4);
    }
    header { padding: 20px 24px; border-bottom: 1px solid #334155; }
    header h1 { margin: 0; font-size: 18px; }
    header p { margin: 4px 0 0; font-size: 13px; color: #94a3b8; }
    .badge { display: inline-block; font-size: 11px; background: #0ea5e9; color: #fff;
             padding: 2px 8px; border-radius: 999px; margin-left: 8px; vertical-align: middle; }
    #chat { height: 380px; overflow-y: auto; padding: 20px 24px; display: flex; flex-direction: column; gap: 12px; }
    .msg { max-width: 80%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.45; white-space: pre-wrap; }
    .me  { align-self: flex-end; background: #0ea5e9; color: #fff; border-bottom-right-radius: 4px; }
    .bot { align-self: flex-start; background: #334155; color: #e2e8f0; border-bottom-left-radius: 4px; }
    .meta { font-size: 11px; color: #64748b; margin-top: 2px; }
    form { display: flex; gap: 8px; padding: 16px 24px; border-top: 1px solid #334155; }
    input {
      flex: 1; padding: 12px 14px; border-radius: 10px; border: 1px solid #475569;
      background: #0f172a; color: #e2e8f0; font-size: 14px; outline: none;
    }
    input:focus { border-color: #0ea5e9; }
    button {
      padding: 12px 18px; border: 0; border-radius: 10px; background: #0ea5e9;
      color: #fff; font-weight: 600; cursor: pointer; font-size: 14px;
    }
    button:disabled { opacity: .5; cursor: not-allowed; }
  </style>
</head>
<body>
  <div class="card">
    <header>
      <h1>🤖 AI Agent <span class="badge">mock LLM</span></h1>
      <p>Gõ câu hỏi và nhấn Gửi — agent trả lời bằng mock LLM (không tốn API).</p>
    </header>
    <div id="chat">
      <div class="msg bot">Xin chào! Hỏi mình thử về <b>docker</b>, <b>deploy</b>, hay bất cứ gì nhé.</div>
    </div>
    <form id="f">
      <input id="q" placeholder="Nhập câu hỏi..." autocomplete="off" autofocus>
      <button id="send" type="submit">Gửi</button>
    </form>
  </div>

  <script>
    const chat = document.getElementById('chat');
    const form = document.getElementById('f');
    const input = document.getElementById('q');
    const send = document.getElementById('send');

    function add(text, who, meta) {
      const div = document.createElement('div');
      div.className = 'msg ' + who;
      div.textContent = text;
      chat.appendChild(div);
      if (meta) {
        const m = document.createElement('div');
        m.className = 'meta'; m.textContent = meta;
        div.appendChild(document.createElement('br'));
        chat.appendChild(m);
      }
      chat.scrollTop = chat.scrollHeight;
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const question = input.value.trim();
      if (!question) return;
      add(question, 'me');
      input.value = ''; send.disabled = true;
      const typing = document.createElement('div');
      typing.className = 'msg bot'; typing.textContent = '...';
      chat.appendChild(typing); chat.scrollTop = chat.scrollHeight;
      try {
        const t0 = performance.now();
        const res = await fetch('/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question })
        });
        const data = await res.json();
        const ms = Math.round(performance.now() - t0);
        typing.remove();
        add(data.answer || JSON.stringify(data), 'bot', `${res.status} · ${ms}ms`);
      } catch (err) {
        typing.remove();
        add('Lỗi: ' + err.message, 'bot');
      } finally {
        send.disabled = false; input.focus();
      }
    });
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    """Giao diện web test (mock LLM)."""
    return INDEX_HTML


@app.get("/info")
def info():
    return {
        "message": "AI Agent running on Railway!",
        "ui": "/",
        "docs": "/docs",
        "health": "/health",
    }


@app.post("/ask")
async def ask_agent(request: Request):
    body = await request.json()
    question = body.get("question", "")
    if not question:
        raise HTTPException(422, "question required")
    return {
        "question": question,
        "answer": ask(question),
        "platform": "Railway",
    }


@app.get("/health")
def health():
    """
    Railway sẽ check endpoint này định kỳ.
    Trả về 200 = healthy. Non-200 = Railway restart container.
    """
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "platform": "Railway",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    # ✅ Railway inject PORT — PHẢI đọc từ env
    port = int(os.getenv("PORT", 8000))
    print(f"Starting on port {port} (from PORT env var)")
    print(f"Mở trình duyệt: http://localhost:{port}/")
    uvicorn.run(app, host="0.0.0.0", port=port)
