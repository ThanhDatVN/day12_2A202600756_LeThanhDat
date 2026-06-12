"""
Production AI Agent — Kết hợp tất cả Day 12 concepts

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ API Key authentication
  ✅ Rate limiting
  ✅ Cost guard
  ✅ Input validation (Pydantic)
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown
  ✅ Security headers
  ✅ CORS
  ✅ Error handling
"""
import time
import signal
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from fastapi.responses import HTMLResponse

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_and_record_cost, current_cost

# LLM: Gemini thật nếu có GEMINI_API_KEY, ngược lại fallback mock
from app.llm import ask as llm_ask, provider as llm_provider

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# Auth / rate limiting / cost guard được tách ra các module riêng:
#   app/auth.py · app/rate_limiter.py · app/cost_guard.py

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    time.sleep(0.1)  # simulate init
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # MutableHeaders has no .pop(); delete with a guard instead
        if "server" in response.headers:
            del response.headers["server"]
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str

# ─────────────────────────────────────────────────────────
# Web UI (chat)
# ─────────────────────────────────────────────────────────
INDEX_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Production AI Agent — Chat</title>
  <style>
    * { box-sizing: border-box; }
    body { margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
      background:linear-gradient(135deg,#1e293b,#0f172a); color:#e2e8f0;
      min-height:100vh; display:flex; align-items:center; justify-content:center; padding:16px; }
    .card { width:100%; max-width:680px; background:#1e293b; border:1px solid #334155;
      border-radius:16px; overflow:hidden; box-shadow:0 20px 60px rgba(0,0,0,.4); }
    header { padding:18px 22px; border-bottom:1px solid #334155; }
    header h1 { margin:0; font-size:17px; }
    header p { margin:4px 0 0; font-size:12px; color:#94a3b8; }
    .badge { display:inline-block; font-size:11px; background:#22c55e; color:#04210f;
      padding:2px 8px; border-radius:999px; margin-left:8px; vertical-align:middle; font-weight:700; }
    .keybar { display:flex; gap:8px; padding:12px 22px; border-bottom:1px solid #334155; background:#16212e; }
    .keybar input { flex:1; padding:9px 12px; border-radius:9px; border:1px solid #475569;
      background:#0f172a; color:#e2e8f0; font-size:13px; outline:none; }
    #chat { height:360px; overflow-y:auto; padding:18px 22px; display:flex; flex-direction:column; gap:11px; }
    .msg { max-width:82%; padding:10px 14px; border-radius:14px; font-size:14px; line-height:1.45; white-space:pre-wrap; }
    .me { align-self:flex-end; background:#0ea5e9; color:#fff; border-bottom-right-radius:4px; }
    .bot { align-self:flex-start; background:#334155; color:#e2e8f0; border-bottom-left-radius:4px; }
    .meta { font-size:11px; color:#64748b; align-self:flex-start; }
    form { display:flex; gap:8px; padding:14px 22px; border-top:1px solid #334155; }
    #q { flex:1; padding:12px 14px; border-radius:10px; border:1px solid #475569;
      background:#0f172a; color:#e2e8f0; font-size:14px; outline:none; }
    #q:focus,.keybar input:focus { border-color:#0ea5e9; }
    button { padding:12px 18px; border:0; border-radius:10px; background:#0ea5e9;
      color:#fff; font-weight:600; cursor:pointer; font-size:14px; }
    button:disabled { opacity:.5; cursor:not-allowed; }
  </style>
</head>
<body>
  <div class="card">
    <header>
      <h1>🤖 Production AI Agent <span class="badge" id="prov">LLM</span></h1>
      <p>Nhập <b>API Key</b> rồi chat. Backend gọi Gemini qua endpoint bảo mật <code>/ask</code>.</p>
    </header>
    <div class="keybar">
      <input id="key" type="password" placeholder="X-API-Key (vd: tuan-day12-...)" autocomplete="off">
    </div>
    <div id="chat">
      <div class="msg bot">Xin chào! Nhập API key ở trên, rồi hỏi mình bất cứ điều gì 👇</div>
    </div>
    <form id="f">
      <input id="q" placeholder="Nhập câu hỏi..." autocomplete="off" autofocus>
      <button id="send" type="submit">Gửi</button>
    </form>
  </div>
  <script>
    const chat=document.getElementById('chat'),form=document.getElementById('f'),
      input=document.getElementById('q'),send=document.getElementById('send'),
      keyEl=document.getElementById('key'),prov=document.getElementById('prov');
    keyEl.value=localStorage.getItem('agentKey')||'';
    keyEl.addEventListener('change',()=>localStorage.setItem('agentKey',keyEl.value));
    fetch('/info').then(r=>r.json()).then(d=>{prov.textContent=(d.llm||'llm')+' · '+(d.model||'');}).catch(()=>{});
    function add(text,who,meta){const d=document.createElement('div');d.className='msg '+who;d.textContent=text;
      chat.appendChild(d);if(meta){const m=document.createElement('div');m.className='meta';m.textContent=meta;chat.appendChild(m);}
      chat.scrollTop=chat.scrollHeight;}
    form.addEventListener('submit',async e=>{e.preventDefault();
      const question=input.value.trim();if(!question)return;
      const key=keyEl.value.trim();if(!key){add('⚠️ Nhập API key trước đã.','bot');return;}
      add(question,'me');input.value='';send.disabled=true;
      const typing=document.createElement('div');typing.className='msg bot';typing.textContent='...';
      chat.appendChild(typing);chat.scrollTop=chat.scrollHeight;
      try{const t0=performance.now();
        const res=await fetch('/ask',{method:'POST',
          headers:{'Content-Type':'application/json','X-API-Key':key},
          body:JSON.stringify({question})});
        const ms=Math.round(performance.now()-t0);const data=await res.json();typing.remove();
        if(res.ok){add(data.answer,'bot',res.status+' · '+ms+'ms · '+(data.model||''));}
        else{add('❌ '+(data.detail||JSON.stringify(data)),'bot',res.status+'');}
      }catch(err){typing.remove();add('Lỗi: '+err.message,'bot');}
      finally{send.disabled=false;input.focus();}
    });
  </script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, tags=["Info"])
def ui():
    """Giao diện chat để test agent ngay trên trình duyệt."""
    return INDEX_HTML


@app.get("/info", tags=["Info"])
def info():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "llm": llm_provider(),
        "model": settings.llm_model,
        "endpoints": {
            "ui": "GET /",
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    """
    Send a question to the AI agent.

    **Authentication:** Include header `X-API-Key: <your-key>`
    """
    # Rate limit per API key
    check_rate_limit(_key[:8])  # use first 8 chars as key bucket

    # Budget check
    input_tokens = len(body.question.split()) * 2
    check_and_record_cost(input_tokens, 0)

    logger.info(json.dumps({
        "event": "agent_call",
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    answer = llm_ask(body.question)

    output_tokens = len(answer.split()) * 2
    check_and_record_cost(0, output_tokens)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Platform restarts container if this fails."""
    status = "ok"
    checks = {"llm": llm_provider()}
    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Load balancer stops routing here if not ready."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    cost = current_cost()
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "daily_cost_usd": round(cost, 4),
        "daily_budget_usd": settings.daily_budget_usd,
        "budget_used_pct": round(cost / settings.daily_budget_usd * 100, 1),
    }


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API Key: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
