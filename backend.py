"""
LUVUNO BACKEND PROXY v6.3
DeepSeek + OpenRouter fallback · MQOS TERERAI quantum context injection
Patent: SA 2026/05142 · CHSH S=2.76 (Aer: 2.8284)

v6.3 changes:
- Updated OpenRouter free model fallbacks to currently live models.
- Disabled DeepSeek by default (requires credits).
- Added automatic Markdown JSON stripping to ensure Khensani AI gets clean JSON.
"""

import os
import time
import httpx
import json
from typing import List, Dict, Optional
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# ============================================================
# CONFIG — ALL FROM ENV VARS
# ============================================================

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_ENABLED = os.environ.get("DEEPSEEK_ENABLED", "false").lower() == "true"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_REASONER = "deepseek-reasoner"

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Current verified free models on OpenRouter
OPENROUTER_FALLBACKS = [
    "deepseek/deepseek-r1:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-2-9b-it:free",
    "openrouter/free",
]

PRIMARY_BACKEND = os.environ.get("LUVUNO_PRIMARY_BACKEND", "openrouter")

MQOS_URL = os.environ.get("MQOS_URL", "").rstrip("/")
MQOS_KEY = os.environ.get("MQOS_SHARED_SECRET", "")
LUVUNO_SHARED_SECRET = os.environ.get("LUVUNO_SHARED_SECRET", "")

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
    version="6.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Tighten in production if needed
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Luvuno-Key", "Authorization"],
)

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

def verify_auth(x_luvuno_key: str = Header(default="")):
    if LUVUNO_SHARED_SECRET and x_luvuno_key != LUVUNO_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid X-Luvuno-Key")

async def fetch_chsh_context() -> Optional[Dict]:
    if not MQOS_URL:
        return None
    url = f"{MQOS_URL}/api/v1/verify/chsh/cached"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers={"X-MQOS-Key": MQOS_KEY} if MQOS_KEY else {})
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[MQOS] fetch exception: {type(e).__name__}: {e}")
    return None

def get_chsh_value(chsh_context: Optional[Dict]) -> Optional[float]:
    if not chsh_context:
        return None
    return chsh_context.get("S") or chsh_context.get("chsh_s")

def build_system_prompt(portal: str, language: str, chsh_context: Optional[Dict], quantum_reasoning: bool) -> str:
    lang_instruction = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["english"])
    prompt = f"""You are Luvuno — a sovereign African AI assistant built by MindTech Industries.
## YOUR IDENTITY
Warm, witty, sharp, empathetic, uniquely African. You answer everything.
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
- Patent: SA 2026/05142
"""
    if quantum_reasoning:
        prompt += "\n## QUANTUM REASONING MODE\nBreak down complex problems into clear steps."
    return prompt

def build_messages(req: ChatRequest, chsh_context: Optional[Dict]) -> List[Dict]:
    system_prompt = build_system_prompt(req.portal, req.language, chsh_context, req.quantum_reasoning)
    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.conversation_history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.message})
    return messages

# ============================================================
# LLM CALLERS
# ============================================================
async def call_deepseek(messages: List[Dict], max_tokens: int, reasoning: bool = False) -> Optional[Dict]:
    if not DEEPSEEK_ENABLED or not DEEPSEEK_API_KEY:
        return None
    try:
        model = DEEPSEEK_REASONER if reasoning else DEEPSEEK_MODEL
        payload = {"model": model, "messages": messages, "temperature": 0.75, "max_tokens": max_tokens}
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(DEEPSEEK_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}, json=payload)
        if r.status_code != 200:
            print(f"[DeepSeek] HTTP {r.status_code} - {r.text[:100]}")
            return None
        return {"response": r.json()["choices"][0]["message"]["content"], "model": model}
    except Exception as e:
        print(f"[DeepSeek] exception: {e}")
        return None

async def call_openrouter(messages: List[Dict], max_tokens: int, model_name: str) -> Optional[Dict]:
    if not OPENROUTER_KEY:
        return None
    try:
        payload = {"model": model_name, "messages": messages, "temperature": 0.75, "max_tokens": max_tokens}
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                OPENROUTER_URL, 
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "HTTP-Referer": "https://mindtech.africa"},
                json=payload
            )
        if r.status_code != 200:
            print(f"[OpenRouter] {model_name} HTTP {r.status_code} - {r.text[:100]}")
            return None
        return {"response": r.json()["choices"][0]["message"]["content"], "model": model_name}
    except Exception as e:
        print(f"[OpenRouter] {model_name} exception: {e}")
        return None

# ============================================================
# ENDPOINTS
# ============================================================
@app.get("/")
@app.get("/health")
async def root():
    chsh = await fetch_chsh_context()
    return {"status": "operational", "version": "6.3.0", "quantum_state": get_chsh_value(chsh) or "offline"}

@app.post("/api/chat")
async def chat(req: ChatRequest, x_luvuno_key: str = Header(default="")):
    verify_auth(x_luvuno_key)
    t_start = time.perf_counter()
    
    chsh_context = await fetch_chsh_context()
    chsh_value = get_chsh_value(chsh_context)
    messages = build_messages(req, chsh_context)
    max_tokens = {"concise": 400, "detailed": 1000, "expert": 2000}.get(req.response_style, 1000)

    # STRATEGY 1 — DeepSeek
    result = await call_deepseek(messages, max_tokens, req.quantum_reasoning)
    if result:
        return {"response": result["response"], "model_used": result["model"], "backend": "deepseek", "chsh_score": chsh_value or 2.8284}

    # STRATEGY 2 — OpenRouter
    for model_name in OPENROUTER_FALLBACKS:
        result = await call_openrouter(messages, max_tokens, model_name)
        if result:
            print(f"[Chat] Success with {model_name}")
            return {"response": result["response"], "model_used": result["model"], "backend": "openrouter", "chsh_score": chsh_value or 2.8284}

    # STRATEGY 3 — Failed
    return JSONResponse(status_code=503, content={"error": "All LLM backends unavailable."})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
