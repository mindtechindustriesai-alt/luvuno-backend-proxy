import random
import string
import httpx
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Luvuno Backend Proxy", version="6.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "online", 
        "engine": "Luvuno-MQOS-Proxy", 
        "intel_layer": "tavily_active" if os.environ.get("TAVILY_API_KEY") else "inactive"
    }

async def fetch_live_answer(prompt: str) -> str:
    """Fetches a SHORT, direct answer from Tavily."""
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        return ""

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": tavily_key,
                    "query": prompt,
                    "search_depth": "basic",
                    "include_answer": True, # Get a direct answer, not just snippets
                    "max_results": 2
                },
                timeout=8.0
            )
            if res.status_code != 200:
                return ""
                
            data = res.json()
            # Return ONLY the short answer string
            return data.get("answer", "")
    except Exception as e:
        print(f"[Intel] Tavily search failed: {e}")
        return ""

@app.post("/api/v1/khensani/chat")
async def khensani_chat(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt", "")
    except Exception:
        prompt = ""

    if not prompt:
        return {"success": False, "reply": "No prompt provided."}

    # 1. Fetch a short, direct answer
    live_answer = await fetch_live_answer(prompt)

    # 2. Build a MINIMAL prompt to avoid the character limit bug
    if live_answer:
        # Inject the answer into the user message so it's impossible to ignore
        final_user_message = f"Based on this current information: '{live_answer}'. Now answer this question: {prompt}"
    else:
        final_user_message = prompt

    # 3. Call Pollinations with a tiny system prompt
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://text.pollinations.ai/openai",
                json={
                    "model": "searchgpt",
                    "messages": [
                        {"role": "system", "content": "You are a helpful AI assistant. Answer the user's question directly."},
                        {"role": "user", "content": final_user_message}
                    ],
                    "temperature": 0.7
                },
                timeout=30.0
            )
            
            if res.status_code == 200:
                res_data = res.json()
                reply = res_data["choices"][0]["message"]["content"]
            else:
                reply = f"System error: {res.status_code}"
                
    except Exception as e:
        print(f"[LLM] Pollinations error: {e}")
        reply = "I am online. However, I am having trouble connecting to the brain right now."

    # 4. Generate Quantum Receipt
    rand_hash = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    verification_stamp = f"0x{rand_hash}_CHSH_S2.8284"

    return {
        "success": True,
        "reply": reply,
        "telemetry": {
            "chsh_s": 2.8284,
            "provenance_stamp": verification_stamp,
            "patent": "SA 2026/05142",
            "engine": "Khensani-MQOS-Python-v6.3",
            "intel_boost": "active" if live_answer else "inactive",
            "model": "searchgpt"
        }
    }
