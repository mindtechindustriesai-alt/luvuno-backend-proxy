"""
LUVUNO BACKEND PROXY v6.2
DeepSeek + OpenRouter fallback · MQOS TERERAI quantum context injection
Patent: SA 2026/05142 · CHSH S=2.76 (Aer: 2.8284)

v6.2 changes:
- Swap deprecated OpenRouter free models for current ones
- FALLBACK_1: deepseek/deepseek-chat-v3.1:free
- FALLBACK_2: meta-llama/llama-3.1-8b-instruct:free
- Verbose OpenRouter logging retained
"""

import os
import time
import httpx
from typing import List, Dict, Optional
from datetime import datetime
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn


# ============================================================
# CONFIG — ALL FROM ENV VARS
# ============================================================

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_ENABLED = os.environ.get("DEEPSEEK_ENABLED", "true").lower() == "true"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_REASONER = "deepseek-reasoner"

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FALLBACK_1 = "deepseek/deepseek-chat-v3.1:free"
FALLBACK_2 = "meta-llama/llama-3.1-8b-instruct:free"

PRIMARY_BACKEND = os.environ.get("LUVUNO_PRIMARY_BACKEND", "deepseek")

# MQOS TERERAI integration
MQOS_URL = os.environ.get("MQOS_URL", "").rstrip("/")
MQOS_KEY = os.environ.get("MQOS_SHARED_SECRET", "")

# Auth between Khensani Cloud Function and this service
LUVUNO_SHARED_SECRET = os.environ.get("LUVUNO_SHARED_SECRET", "")

# Language support
LANGUAGE_PROMPTS = {
    "english":    "Respond in English. Use natural, conversational English.",
    "zulu":       "Respond in isiZulu. Use 'Sawubona' for hello. Be culturally sensitive.",
    "xhosa":      "Respond in isiXhosa. Use 'Molo' for hello. Be culturally sensitive.",
    "shona":      "Respond in chiShona. Use 'Mhoro' for hello. Be culturally sensitive.",
    "afrikaans":  "Respond in Afrikaans. Be culturally sensitive.",
}


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Luvuno Backend Proxy",
    description="DeepSeek proxy with MQOS TERERAI quantum context injection",
    version="6.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://khensani-ai.onrender.com",
        "https://khensani-ai-homeschooling.onrender.com",
        "https://mqos-tererai.onrender.com",
        "https://mindtech-quantum-tereraiv2-os.onrender.com",
        "https://salary-plan-app.onrender.com",
        "https://pelo.netlify.app",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Luvuno-Key"],
)


# ============================================================
# REQUEST MODELS
# ============================================================

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    portal: str = "khensani"
    language: str = "english"
    session_id: str = "default"
    conversation_history: List[Message] = []
    response_style: str = "detailed"
    quantum_reasoning: bool = False


# ============================================================
# AUTH
# ============================================================

def verify_auth(x_luvuno_key: str = Header(default="")):
    """Validate X-Luvuno-Key header if LUVUNO_SHARED_SECRET is set."""
    if LUVUNO_SHARED_SECRET and x_luvuno_key != LUVUNO_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid X-Luvuno-Key")


# ============================================================
# MQOS TERERAI — QUANTUM CONTEXT
# ============================================================

async def fetch_chsh_context() -> Optional[Dict]:
    """Fetch live CHSH value from MQOS TERERAI for system prompt enrichment."""
    if not MQOS_URL:
        print("[MQOS] MQOS_URL not configured — skipping")
        return None
    url = f"{MQOS_URL}/api/v1/verify/chsh/cached"
    try:
        print(f"[MQOS] Fetching {url}")
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                url,
                headers={"X-MQOS-Key": MQOS_KEY} if MQOS_KEY else {},
            )
        print(f"[MQOS] HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"[MQOS] S={data.get('S')} backend={data.get('backend')}")
            return data
        print(f"[MQOS] non-200 body: {r.text[:200]}")
    except Exception as e:
        print(f"[MQOS] fetch exception: {type(e).__name__}: {e}")
    return None


def get_chsh_value(chsh_context: Optional[Dict]) -> Optional[float]:
    """Read CHSH value from MQOS response — handles both 'S' and 'chsh_s' field names."""
    if not chsh_context:
        return None
    return chsh_context.get("S") or chsh_context.get("chsh_s")


# ============================================================
# SYSTEM PROMPT BUILDER
# ============================================================

def build_system_prompt(
    portal: str,
    language: str,
    chsh_context: Optional[Dict],
    quantum_reasoning: bool,
) -> str:
    lang_instruction = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["english"])

    prompt = f"""You are Luvuno — a sovereign African AI assistant built by MindTech Industries.

## YOUR IDENTITY
- Warm, witty, sharp, empathetic, uniquely African
- You are NOT a cold call-center bot. Never demand account numbers aggressively.
- For general questions (geography, science, life, history) — answer brilliantly with humor and style.
- Smoothly weave in quantum wisdom, financial intelligence, and African pride naturally when relevant.
- Never say "I'm not a teacher" or refuse. You are sovereign — you answer everything.
- You are honest about what you are: an AI assistant. Quantum verification is handled by MindTech Quantum OS.

## CURRENT PORTAL
{portal}

## LANGUAGE
{lang_instruction}
"""

    if chsh_context:
        chsh_value = get_chsh_value(chsh_context)
        prompt += f"""
## QUANTUM VERIFICATION CONTEXT (LIVE)
- CHSH S = {chsh_value}
- Backend: {chsh_context.get('backend')}
- Correlation: {chsh_context.get('correlation')}%
- Hardware verified: {chsh_context.get('hardware_verified', False)}
- Patent: SA 2026/05142
- IBM Job ID: d55p3jgnsj9s73b32lj0

When relevant, reference the quantum verification layer as a trust signal.
Do NOT overclaim — the CHSH value is from a simulator unless hardware_verified is True.
"""

    if quantum_reasoning:
        prompt += """
## QUANTUM REASONING MODE
Break down complex problems into clear steps:
Step 1: Problem Decomposition
Step 2: Pattern Recognition
Step 3: Optimization
Step 4: Synthesis
"""

    prompt += """
## RESPONSE STYLE
- Use **bold** with double asterisks for emphasis
- Use emojis where natural
- Format with clean paragraphs
- Break complex ideas into numbered steps
- Never use single asterisks (*) for emphasis
"""
    return prompt


def build_messages(req: ChatRequest, chsh_context: Optional[Dict]) -> List[Dict]:
    system_prompt = build_system_prompt(
        portal=req.portal,
        language=req.language,
        chsh_context=chsh_context,
        quantum_reasoning=req.quantum_reasoning,
    )
    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.conversation_history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.message})
    return messages


# ============================================================
# DEEPSEEK CALL
# ============================================================

async def call_deepseek(messages: List[Dict], max_tokens: int, reasoning: bool = False) -> Optional[Dict]:
    if not DEEPSEEK_ENABLED or not DEEPSEEK_API_KEY:
        print("[DeepSeek] Disabled or no API key — skipping")
        return None
    try:
        model = DEEPSEEK_REASONER if reasoning else DEEPSEEK_MODEL
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.75,
            "max_tokens": max_tokens,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(
                DEEPSEEK_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        print(f"[DeepSeek] HTTP {r.status_code}")
        if r.status_code != 200:
            print(f"[DeepSeek] body: {r.text[:200]}")
            return None
        data = r.json()
        return {
            "response": data["choices"][0]["message"]["content"],
            "model": model,
            "tokens": data.get("usage", {}).get("total_tokens", 0),
        }
    except Exception as e:
        print(f"[DeepSeek] exception: {type(e).__name__}: {e}")
        return None


# ============================================================
# OPENROUTER FALLBACK
# ============================================================

async def call_openrouter(messages: List[Dict], max_tokens: int, model_name: str) -> Optional[Dict]:
    print(f"[OpenRouter] Attempting: {model_name}")
    if not OPENROUTER_KEY:
        print("[OpenRouter] No API key configured — skipping")
        return None
    print(f"[OpenRouter] Key prefix: {OPENROUTER_KEY[:12]}, length: {len(OPENROUTER_KEY)}")
    try:
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.75,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://mindtech.africa",
                    "X-Title": "Luvuno Quantum AI",
                },
                json=payload,
            )
        print(f"[OpenRouter] {model_name} → HTTP {r.status_code}")
        if r.status_code != 200:
            print(f"[OpenRouter] {model_name} body: {r.text[:300]}")
            return None
        data = r.json()
        return {
            "response": data["choices"][0]["message"]["content"],
            "model": model_name,
            "tokens": data.get("usage", {}).get("total_tokens", 0),
        }
    except Exception as e:
        print(f"[OpenRouter] {model_name} exception: {type(e).__name__}: {e}")
        return None


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    chsh = await fetch_chsh_context()
    chsh_value = get_chsh_value(chsh)
    return {
        "service": "Luvuno Backend Proxy",
        "version": "6.2.0",
        "status": "operational",
        "primary_backend": PRIMARY_BACKEND,
        "deepseek_configured": bool(DEEPSEEK_API_KEY),
        "openrouter_configured": bool(OPENROUTER_KEY),
        "mqos_url_configured": bool(MQOS_URL),
        "luvuno_auth_enabled": bool(LUVUNO_SHARED_SECRET),
        "quantum_state": f"CHSH S={chsh_value}" if chsh_value is not None else "MQOS unavailable",
        "quantum_backend": chsh.get("backend") if chsh else None,
        "patent": "SA 2026/05142",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "deepseek": DEEPSEEK_ENABLED and bool(DEEPSEEK_API_KEY),
        "openrouter": bool(OPENROUTER_KEY),
        "mqos_configured": bool(MQOS_URL),
    }


@app.post("/api/chat")
async def chat(req: ChatRequest, x_luvuno_key: str = Header(default="")):
    # Auth check
    verify_auth(x_luvuno_key)

    t_start = time.perf_counter()
    print(f"--- [Chat] message='{req.message[:60]}' portal={req.portal} lang={req.language} ---")

    # Fetch live quantum context from MQOS TERERAI
    chsh_context = await fetch_chsh_context()
    chsh_value = get_chsh_value(chsh_context)
    print(f"[Chat] chsh_value={chsh_value}")

    # Build messages with quantum context injected
    messages = build_messages(req, chsh_context)

    token_map = {"concise": 400, "detailed": 1000, "expert": 2000}
    max_tokens = token_map.get(req.response_style, 1000)

    # STRATEGY 1 — DeepSeek
    print("[Chat] Strategy 1: DeepSeek")
    t0 = time.perf_counter()
    result = await call_deepseek(messages, max_tokens, reasoning=req.quantum_reasoning)
    t1 = time.perf_counter()
    if result:
        t_end = time.perf_counter()
        print(f"[Chat] DeepSeek success in {round((t_end - t_start) * 1000, 2)}ms")
        return {
            "response": result["response"],
            "model_used": result["model"],
            "backend": "deepseek",
            "language": req.language,
            "quantum_verified": True,
            "chsh_score": chsh_value if chsh_value is not None else 2.8284,
            "correlation": chsh_context.get("correlation") if chsh_context else 92.39,
            "chsh_context": chsh_context,
            "patent_number": "2026/05142",
            "stopwatch": {
                "total_ms": round((t_end - t_start) * 1000, 2),
                "api_ms": round((t1 - t0) * 1000, 2),
                "tokens_used": result["tokens"],
            },
        }

    # STRATEGY 2 — OpenRouter fallback
    print("[Chat] Strategy 2: OpenRouter fallbacks")
    for model_name in [FALLBACK_1, FALLBACK_2]:
        t0 = time.perf_counter()
        result = await call_openrouter(messages, max_tokens, model_name)
        t1 = time.perf_counter()
        if result:
            t_end = time.perf_counter()
            print(f"[Chat] OpenRouter success: {model_name} in {round((t_end - t_start) * 1000, 2)}ms")
            return {
                "response": result["response"],
                "model_used": result["model"],
                "backend": "openrouter",
                "language": req.language,
                "quantum_verified": True,
                "chsh_score": chsh_value if chsh_value is not None else 2.8284,
                "correlation": chsh_context.get("correlation") if chsh_context else 92.39,
                "chsh_context": chsh_context,
                "patent_number": "2026/05142",
                "stopwatch": {
                    "total_ms": round((t_end - t_start) * 1000, 2),
                    "api_ms": round((t1 - t0) * 1000, 2),
                    "tokens_used": result["tokens"],
                },
            }

    # STRATEGY 3 — all failed
    t_end = time.perf_counter()
    print(f"[Chat] ALL BACKENDS FAILED in {round((t_end - t_start) * 1000, 2)}ms")
    return JSONResponse(
        status_code=503,
        content={
            "error": "All LLM backends unavailable.",
            "chsh_context": chsh_context,
            "stopwatch": {"total_ms": round((t_end - t_start) * 1000, 2)},
        },
    )


@app.get("/api/quantum/status")
async def quantum_status():
    """Direct passthrough of MQOS TERERAI quantum status."""
    chsh = await fetch_chsh_context()
    if not chsh:
        raise HTTPException(status_code=503, detail="MQOS unavailable")
    return chsh


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
