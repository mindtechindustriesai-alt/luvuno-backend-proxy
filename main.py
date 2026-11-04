import os
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="MindTech Intelligence Gateway", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Lock this down to your domains later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    prompt: str
    history: Optional[List[ChatMessage]] = []
    system_prompt: Optional[str] = "You are a helpful AI assistant."

@app.post("/api/chat")
async def chat_gateway(req: ChatRequest):
    live_context = ""
    sources = []

    # 1. Fetch Live Web Intel securely
    if TAVILY_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                tavily_res = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": TAVILY_API_KEY,
                        "query": req.prompt,
                        "search_depth": "basic",
                        "include_answer": True,
                        "max_results": 3
                    },
                    timeout=10.0
                )
                if tavily_res.status_code == 200:
                    data = tavily_res.json()
                    if data.get("answer"):
                        live_context = f"\n[CURRENT INFO]: {data['answer']}\n"
                    for r in data.get("results", []):
                        sources.append(r.get("url"))
        except Exception as e:
            print(f"Tavily error: {e}")

    # 2. Build the message array for the AI
    messages = [{"role": "system", "content": req.system_prompt}]
    
    # Add history (last 5 messages for continuity)
    for msg in req.history[-5:]:
        messages.append({"role": msg.role, "content": msg.content})
        
    # Add the current prompt with live context injected
    final_user_content = req.prompt
    if live_context:
        final_user_content = f"{live_context}\n\nQuestion: {req.prompt}\n(Use the CURRENT INFO above to answer accurately)."
    
    messages.append({"role": "user", "content": final_user_content})

    # 3. Call the AI (Pollinations OpenAI-compatible endpoint)
    try:
        async with httpx.AsyncClient() as client:
            ai_res = await client.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                json={
                    "model": "openai",
                    "messages": messages,
                    "temperature": 0.7
                },
                timeout=30.0
            )
            
            if ai_res.status_code == 200:
                ai_data = ai_res.json()
                reply = ai_data["choices"][0]["message"]["content"]
                
                # Append sources if they exist
                if sources:
                    reply += "\n\n**Sources:**\n"
                    for s in set(sources):
                        reply += f"- {s}\n"
            else:
                reply = "I am having trouble connecting to my reasoning engine right now."
                
    except Exception as e:
        print(f"AI error: {e}")
        reply = "I am currently offline. Please try again later."

    return {
        "success": True,
        "reply": reply,
        "has_live_context": bool(live_context),
        "sources": list(set(sources))
    }