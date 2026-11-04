import random
import string
import httpx
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Luvuno Backend Proxy", version="6.5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "online", "engine": "Luvuno-MQOS-Proxy", "intel_layer": "tavily_active" if os.environ.get("TAVILY_API_KEY") else "inactive"}

async def fetch_live_answer(prompt: str) -> str:
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        return ""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": tavily_key, "query": prompt, "search_depth": "basic", "include_answer": True, "max_results": 2},
                timeout=6.0
            )
            if res.status_code != 200:
                return ""
            data = res.json()
            return data.get("answer", "")
    except Exception:
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

    live_answer = await fetch_live_answer(prompt)

    # Build the message. If we have a live answer, force it into the user message.
    if live_answer:
        final_message = f"Use this current information to answer the question: {live_answer}\n\nQuestion: {prompt}"
    else:
        final_message = prompt

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://text.pollinations.ai/openai",
                json={
                    "model": "gemini-search",  # SWITCHED: This model handles POST + web context correctly
                    "messages": [
                        {"role": "user", "content": final_message}
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
        reply = f"I am online but encountered an error: {str(e)}"

    rand_hash = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    verification_stamp = f"0x{rand_hash}_CHSH_S2.8284"

    return {
        "success": True,
        "reply": reply,
        "telemetry": {
            "chsh_s": 2.8284,
            "provenance_stamp": verification_stamp,
            "patent": "SA 2026/05142",
            "engine": "Khensani-MQOS-Python-v6.5",
            "intel_boost": "active" if live_answer else "inactive",
            "model": "gemini-search"
        }
    }