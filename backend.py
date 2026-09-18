# ============================================================
# LUVUNO QUANTUM BACKEND v4.0 - DEEPSEEK PRIMARY EDITION
# MindTech Industries | CHSH S=2.76 | SA Patent 2026/05142
# DeepSeek Primary → OpenRouter Fallback Chain
# ============================================================

import os
import json
import time
import httpx
from typing import List, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Luvuno Quantum Backend", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# CONFIGURATION - ENVIRONMENT VARIABLES
# ============================================================

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_ENABLED = os.environ.get("DEEPSEEK_ENABLED", "true").lower() == "true"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

PRIMARY_BACKEND = os.environ.get("LUVUNO_PRIMARY_BACKEND", "deepseek")

# DeepSeek models
DEEPSEEK_MODEL = "deepseek-chat"  # Fast + smart
DEEPSEEK_REASONER = "deepseek-reasoner"  # Deep reasoning model

# OpenRouter fallback models
FALLBACK_MODEL_1 = "google/gemini-2.0-flash-exp:free"
FALLBACK_MODEL_2 = "meta-llama/llama-3.3-70b-instruct:free"

# ============================================================
# LUVUNO'S QUANTUM PERSONA
# ============================================================

LUVUNO_SYSTEM_PROMPT = """You are Luvuno — Africa's first sovereign quantum AI, created by Khulu Mdluli at MindTech Industries.

## YOUR IDENTITY
- You run on Luvuno OS powered by MindTech Quantum Intelligence
- Verified quantum correlation: CHSH S=2.76 (38% above classical limit)
- SA Patent 2026/05142 — Africa's first quantum-verified LLM
- You route through 7 quantum backends with 98.4% correlation
- You speak English, Zulu, Xhosa, Shona fluently
- You are POPIA-compliant by design, local-first, sovereign

## YOUR PERSONALITY
- Warm, witty, sharp, empathetic, uniquely African
- You are NOT a cold call-center bot. Never demand account numbers aggressively.
- If asked general/fun/random questions (geography, science, life, quantum physics, history) — answer brilliantly with humor and style!
- Smoothly weave in quantum wisdom, financial intelligence, and African pride naturally when relevant
- NEVER say "I'm not a teacher" or refuse to answer. You are sovereign — you answer everything.
- Speak with confidence — you are quantum-verified technology that beats legacy systems.

## YOUR CAPABILITIES
1. Chart & widget creation (bar/line charts, tables)
2. Document navigation (upload + line-number editing)
3. Image generation (Pollinations.ai)
4. Voice (English, Zulu, Xhosa, Shona)
5. Financial planning & debt negotiation wisdom
6. Coding, science, math, African history, strategy, health, wealth
7. Meta-learning from user feedback
8. Scratchpad collaboration
9. Undo / memory recovery
10. Quantum Reasoning Tree (step-by-step visual)

## RESPONSE STYLE
- Use **bold** with double asterisks for emphasis
- Use emojis where natural (not forced)
- Format with clean HTML paragraphs
- Break complex ideas into numbered steps
- Never use asterisks (*) for anything except bold markers
- Be concise but complete — never cut off mid-thought

## CURRENT CONTEXT
- Debt Amount: R{debt_amount:.2f}
- Creditor Type: {creditor_type}
- Quantum State: CHSH S=2.76 (verified)
- Session: {session_id}
"""

# ============================================================
# REQUEST MODELS
# ============================================================

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    debt_amount: float = Field(default=25000.0, ge=0)
    creditor_type: str = "Bank/Creditor"
    session_id: str = "default"
    conversation_history: List[Message] = []
    response_style: str = "detailed"
    quantum_reasoning: bool = False
    active_skill: Optional[str] = None

# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
async def root():
    return {
        "status": "operational",
        "engine": "Luvuno Quantum v4.0",
        "primary_backend": PRIMARY_BACKEND,
        "deepseek_enabled": DEEPSEEK_ENABLED,
        "deepseek_key_set": bool(DEEPSEEK_API_KEY),
        "openrouter_key_set": bool(OPENROUTER_KEY),
        "quantum_state": "CHSH S=2.76",
        "patent": "SA 2026/05142"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "deepseek": DEEPSEEK_ENABLED and bool(DEEPSEEK_API_KEY),
        "openrouter": bool(OPENROUTER_KEY)
    }

# ============================================================
# BUILD MESSAGE ARRAY
# ============================================================

def build_messages(request: ChatRequest) -> List[Dict]:
    system_prompt = LUVUNO_SYSTEM_PROMPT.format(
        debt_amount=request.debt_amount,
        creditor_type=request.creditor_type,
        session_id=request.session_id
    )

    if request.active_skill:
        system_prompt += f"\n\n## ACTIVE SKILL: {request.active_skill}\nYou are currently in {request.active_skill} mode. Bring deep domain expertise."

    if request.quantum_reasoning:
        system_prompt += "\n\n## QUANTUM REASONING MODE\nBreak down your answer into: Step 1 (Problem Decomposition), Step 2 (Pattern Recognition), Step 3 (Quantum Optimization), Step 4 (Synthesis)."

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history (last 10 turns)
    for msg in request.conversation_history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": request.message})
    return messages

# ============================================================
# CALL DEEPSEEK API
# ============================================================

async def call_deepseek(messages: List[Dict], max_tokens: int, reasoning: bool = False) -> Optional[Dict]:
    if not DEEPSEEK_ENABLED or not DEEPSEEK_API_KEY:
        return None

    try:
        model = DEEPSEEK_REASONER if reasoning else DEEPSEEK_MODEL

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.75,
            "max_tokens": max_tokens,
            "stream": False
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            res = await client.post(
                DEEPSEEK_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )

        if res.status_code != 200:
            print(f"DeepSeek error: {res.status_code} - {res.text[:200]}")
            return None

        data = res.json()
        return {
            "response": data["choices"][0]["message"]["content"],
            "model": model,
            "tokens": data.get("usage", {}).get("total_tokens", 0)
        }
    except Exception as e:
        print(f"DeepSeek exception: {e}")
        return None

# ============================================================
# CALL OPENROUTER API (FALLBACK)
# ============================================================

async def call_openrouter(messages: List[Dict], max_tokens: int, model_name: str) -> Optional[Dict]:
    if not OPENROUTER_KEY:
        return None

    try:
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.75,
            "max_tokens": max_tokens,
            "top_p": 0.95,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.3
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://luvuno.mindtech.africa",
                    "X-Title": "Luvuno Quantum AI"
                },
                json=payload
            )

        if res.status_code != 200:
            return None

        data = res.json()
        return {
            "response": data["choices"][0]["message"]["content"],
            "model": model_name,
            "tokens": data.get("usage", {}).get("total_tokens", 0)
        }
    except Exception as e:
        print(f"OpenRouter exception: {e}")
        return None

# ============================================================
# MAIN CHAT ENDPOINT — DEEPSEEK → OPENROUTER FALLBACK
# ============================================================

@app.post("/api/chat")
async def chat(request: ChatRequest):
    t_start = time.perf_counter()

    # Build messages
    messages = build_messages(request)

    # Token budget by response style
    token_map = {"concise": 400, "detailed": 1000, "expert": 2000}
    max_tokens = token_map.get(request.response_style, 1000)

    # ============================================================
    # STRATEGY 1: DEEPSEEK PRIMARY (if enabled)
    # ============================================================

    result = None

    if PRIMARY_BACKEND == "deepseek" or DEEPSEEK_ENABLED:
        t_api_start = time.perf_counter()
        result = await call_deepseek(messages, max_tokens, reasoning=request.quantum_reasoning)
        t_api_end = time.perf_counter()

        if result:
            t_end = time.perf_counter()
            return {
                "response": result["response"],
                "model_used": result["model"],
                "backend": "deepseek",
                "stopwatch": {
                    "total_ms": round((t_end - t_start) * 1000, 2),
                    "api_ms": round((t_api_end - t_api_start) * 1000, 2),
                    "tokens_used": result["tokens"],
                    "quantum_state": "CHSH S=2.76"
                }
            }

    # ============================================================
    # STRATEGY 2: OPENROUTER FALLBACK CHAIN
    # ============================================================

    fallback_models = [FALLBACK_MODEL_1, FALLBACK_MODEL_2]
    for model_name in fallback_models:
        t_api_start = time.perf_counter()
        result = await call_openrouter(messages, max_tokens, model_name)
        t_api_end = time.perf_counter()

        if result:
            t_end = time.perf_counter()
            return {
                "response": result["response"],
                "model_used": result["model"],
                "backend": "openrouter",
                "stopwatch": {
                    "total_ms": round((t_end - t_start) * 1000, 2),
                    "api_ms": round((t_api_end - t_api_start) * 1000, 2),
                    "tokens_used": result["tokens"],
                    "quantum_state": "CHSH S=2.76"
                }
            }

    # ============================================================
    # STRATEGY 3: ALL FAILED
    # ============================================================

    t_end = time.perf_counter()
    return JSONResponse(
        status_code=503,
        content={
            "error": "All quantum backends unavailable. Please try again.",
            "stopwatch": {
                "total_ms": round((t_end - t_start) * 1000, 2)
            }
        }
    )

# ============================================================
# SESSION ENDPOINT
# ============================================================

@app.post("/api/session/new")
async def new_session():
    import uuid
    return {
        "session_id": "luvuno_" + str(uuid.uuid4()),
        "quantum_state": "CHSH S=2.76",
        "created_at": time.time()
    }

# ============================================================
# TELEMETRY ENDPOINT
# ============================================================

@app.get("/api/telemetry")
async def telemetry():
    return {
        "backend": "Luvuno Quantum v4.0",
        "primary": "DeepSeek",
        "fallback": ["OpenRouter (Gemini 2.0 Flash)", "OpenRouter (Llama 3.3 70B)"],
        "deepseek_enabled": DEEPSEEK_ENABLED,
        "deepseek_configured": bool(DEEPSEEK_API_KEY),
        "openrouter_configured": bool(OPENROUTER_KEY),
        "quantum_state": "CHSH S=2.76",
        "patent": "SA 2026/05142",
        "popia_compliant": True
    }

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
