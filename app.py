import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="MindTech Intelligence Router", version="6.0")

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

    # 1. Fetch DEEP Live Web Intel
    if TAVILY_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                tavily_res = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": TAVILY_API_KEY,
                        "query": req.prompt,
                        "search_depth": "advanced",  # UPGRADED: Pulls full page text
                        "include_answer": True,
                        "max_results": 5               # UPGRADED: More sources
                    },
                    timeout=15.0
                )
                if tavily_res.status_code == 200:
                    data = tavily_res.json()
                    if data.get("answer"):
                        live_context = f"\n[CURRENT INFO]: {data['answer']}\n"
                    for r in data.get("results", []):
                        # We now include the full content snippet from the page
                        live_context += f"\n[SOURCE: {r.get('url')}]\n{r.get('content')}\n"
                        sources.append(r.get("url"))
        except Exception as e:
            print(f"Tavily error: {e}")

    final_user_content = req.prompt
    if live_context:
        # UPGRADED PROMPT: Forces the AI to use the deep context
        final_user_content = (
            f"{live_context}\n\n"
            f"Based on the extensive sources above, answer the following request thoroughly. "
            f"If an essay is requested, write a full, multi-paragraph essay. Be comprehensive.\n\n"
            f"Request: {req.prompt}"
        )

    if not GEMINI_API_KEY:
        return {"success": False, "reply": "Gemini API key is missing."}

    url = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }

    # 3.5 for speed, 3.8 for deep reasoning (like essays)
    models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
    errors_log = []

    for model_name in models_to_try:
        contents = []
        for msg in req.history[-6:]:
            contents.append({
                "role": "user" if msg.role == "user" else "model",
                "parts": [{"text": msg.content}]
            })
        
        contents.append({"role": "user", "parts": [{"text": final_user_content}]})

        # UPGRADED: Slightly higher temperature for more expressive writing
        payload = {
            "systemInstruction": {"parts": [{"text": req.system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.8, "maxOutputTokens": 2048}
        }

        try:
            async with httpx.AsyncClient() as client:
                formatted_url = url.format(model=model_name)
                ai_res = await client.post(formatted_url, headers=headers, json=payload, timeout=45.0)
                
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
                    errors_log.append(f"{model_name}: 503")
                    continue 
                else:
                    errors_log.append(f"{model_name}: {ai_res.status_code}")
                    break 
                    
        except httpx.ReadTimeout:
            errors_log.append(f"{model_name}: Timeout")
            continue
        except Exception as e:
            errors_log.append(f"{model_name}: {str(e)}")
            break

    return {
        "success": False,
        "reply": f"All AI engines are currently unavailable. (Errors: {' | '.join(errors_log)})",
        "provider": "None",
    }