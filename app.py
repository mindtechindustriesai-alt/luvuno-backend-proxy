import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="MindTech Intelligence Router", version="5.0")

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

    final_user_content = req.prompt
    if live_context:
        final_user_content = f"{live_context}\n\nQuestion: {req.prompt}\n(Use the CURRENT INFO above to answer accurately)."

    if not GEMINI_API_KEY:
        return {"success": False, "reply": "Gemini API key is missing in Render Environment."}

    url = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }

    # The exact models you verified:
    # 1. 3.5 Flash-Lite (Fast, High-volume, Stable)
    # 2. 3.8 Flash (Smarter, for complex workflows)
    models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
    errors_log = []

    for model_name in models_to_try:
        # Build the standard Gemini API payload
        contents = []
        for msg in req.history[-6:]:
            contents.append({
                "role": "user" if msg.role == "user" else "model",
                "parts": [{"text": msg.content}]
            })
        
        contents.append({
            "role": "user",
            "parts": [{"text": final_user_content}]
        })

        payload = {
            "systemInstruction": {"parts": [{"text": req.system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.7}
        }

        try:
            async with httpx.AsyncClient() as client:
                # 15 second timeout ensures it fails fast so the fallback can kick in
                formatted_url = url.format(model=model_name)
                ai_res = await client.post(formatted_url, headers=headers, json=payload, timeout=15.0)
                
                if ai_res.status_code == 200:
                    ai_data = ai_res.json()
                    reply = ai_data["candidates"][0]["content"]["parts"][0]["text"]
                    
                    if sources:
                        reply += "\n\n**Sources:**\n"
                        for s in set(sources):
                            reply += f"- {s}\n"
                    
                    return {
                        "success": True,
                        "reply": reply,
                        "provider": model_name,
                        "has_live_context": bool(live_context),
                        "sources": list(set(sources))
                    }
                    
                elif ai_res.status_code == 503:
                    print(f"[{model_name}] is overloaded (503). Trying next model...")
                    errors_log.append(f"{model_name}: 503 Overloaded")
                    continue 
                else:
                    print(f"[{model_name}] failed with {ai_res.status_code}: {ai_res.text}")
                    errors_log.append(f"{model_name}: {ai_res.status_code} - {ai_res.text[:50]}")
                    break # If it's a 400/401 error, fail immediately, don't try next
                    
        except httpx.ReadTimeout:
            print(f"[{model_name}] timed out after 15s. Trying next model...")
            errors_log.append(f"{model_name}: Timeout")
            continue
        except Exception as e:
            print(f"[{model_name}] connection error: {str(e)}")
            errors_log.append(f"{model_name}: {str(e)}")
            break

    # If we get here, all models failed
    return {
        "success": False,
        "reply": f"I tried multiple AI engines but they are all currently unavailable. (Errors: {' | '.join(errors_log)})",
        "provider": "None",
        "has_live_context": bool(live_context),
        "sources": list(set(sources))
    }