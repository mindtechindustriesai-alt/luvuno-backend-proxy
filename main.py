import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="MindTech Intelligence Gateway", version="1.4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

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

    # 1. Fetch Live Web Intel securely via Tavily
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

    # 2. Build the message array
    messages = []
    
    for msg in req.history[-5:]:
        role = "user" if msg.role == "user" else "model"
        messages.append({"role": role, "parts": [{"text": msg.content}]})
        
    final_user_content = req.prompt
    if live_context:
        final_user_content = f"{live_context}\n\nQuestion: {req.prompt}\n(Use the CURRENT INFO above to answer accurately)."
    
    messages.append({"role": "user", "parts": [{"text": final_user_content}]})

    # 3. Call Gemini 3.8 Flash
    if not GEMINI_API_KEY:
        return {"success": False, "reply": "Gemini API key is missing in Render Environment."}

    try:
        # Changed to gemini-3.8-flash based on Google's error message
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "systemInstruction": {
                "parts": [{"text": req.system_prompt}]
            },
            "contents": messages,
            "generationConfig": {
                "temperature": 0.7
            }
        }

        async with httpx.AsyncClient() as client:
            ai_res = await client.post(url, json=payload, timeout=30.0)
            
            if ai_res.status_code == 200:
                ai_data = ai_res.json()
                reply = ai_data["candidates"][0]["content"]["parts"][0]["text"]
                
                if sources:
                    reply += "\n\n**Sources:**\n"
                    for s in set(sources):
                        reply += f"- {s}\n"
            else:
                reply = f"Gemini Error: {ai_res.status_code} - {ai_res.text}"
                
    except Exception as e:
        reply = f"I am currently offline. Error: {str(e)}"

    return {
        "success": True,
        "reply": reply,
        "has_live_context": bool(live_context),
        "sources": list(set(sources))
    }