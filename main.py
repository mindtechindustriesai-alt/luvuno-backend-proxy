import os
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="MindTech Intelligence Gateway", version="1.8")

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
        return {"success": False, "reply": "Gemini API key is missing."}

    url = "https://generativelanguage.googleapis.com/v1beta/interactions"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }

    # Fallback list: Try 3.8, then 1.5 (which is stable for older accounts)
    models_to_try = ["gemini-3.8-flash", "gemini-1.5-flash"]
    reply = "I am currently offline. All Gemini models failed."

    for model_name in models_to_try:
        payload = {
            "model": model_name,
            "input": final_user_content,
            "system_instruction": req.system_prompt
        }

        try:
            async with httpx.AsyncClient() as client:
                ai_res = await client.post(url, headers=headers, json=payload, timeout=30.0)
                
                if ai_res.status_code == 200:
                    ai_data = ai_res.json()
                    reply = ""
                    
                    if "output_text" in ai_data:
                        reply = ai_data["output_text"]
                    elif "steps" in ai_data:
                        for step in ai_data["steps"]:
                            if step.get("type") == "model_output":
                                for content in step.get("content", []):
                                    if content.get("type") == "text":
                                        reply += content.get("text", "")
                    
                    if not reply:
                        reply = f"No text output found. Raw: {str(ai_data)[:200]}"
                    
                    if sources:
                        reply += "\n\n**Sources:**\n"
                        for s in set(sources):
                            reply += f"- {s}\n"
                    
                    break # Success! Stop trying models.
                    
                elif ai_res.status_code == 503:
                    print(f"{model_name} overloaded. Trying next...")
                    continue # Try the next model
                else:
                    reply = f"Gemini Error ({model_name}): {ai_res.status_code} - {ai_res.text}"
                    break # Real error (like 400), stop trying
                    
        except Exception as e:
            reply = f"Connection Error: {str(e)}"
            break

    return {
        "success": True,
        "reply": reply,
        "has_live_context": bool(live_context),
        "sources": list(set(sources))
    }