from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import os
from datetime import datetime
import uvicorn

app = FastAPI(title="Luvuno Backend Proxy", description="Secure proxy for DeepSeek API")

# CORS - Allow your frontend domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:5500",
        "https://luvuno-quantum-x.onrender.com",
        "https://luvuno-chat-quantumx1.onrender.com",
        "https://*.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get API key from environment variable
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    print("⚠️ WARNING: DEEPSEEK_API_KEY environment variable not set!")

@app.get("/")
async def root():
    return {
        "service": "Luvuno Backend Proxy",
        "status": "operational",
        "version": "1.0.0",
        "endpoints": ["POST /api/chat", "GET /health"],
        "api_key_configured": bool(DEEPSEEK_API_KEY)
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "api_key_configured": bool(DEEPSEEK_API_KEY)
    }

@app.post("/api/chat")
async def chat(request: Request):
    # Check if API key is configured
    if not DEEPSEEK_API_KEY:
        return JSONResponse(
            status_code=500,
            content={"error": "DEEPSEEK_API_KEY not configured on server"}
        )
    
    # Parse request body
    try:
        body = await request.json()
        message = body.get("message")
        portal = body.get("portal", "quantum")
        custom_system = body.get("system", "")
        
        if not message:
            return JSONResponse(status_code=400, content={"error": "Message is required"})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid request: {str(e)}"})
    
    # Build system prompt
    system_prompt = f"You are Luvuno, an AI assistant for Luvuno OS. Current portal: {portal}. Answer clearly, concisely, and helpfully. Use emojis where appropriate. Format with proper paragraphs. Be warm and engaging."
    
    if custom_system == "quantumthink":
        system_prompt += " Break down complex problems into clear steps. Use format: Step 1, Step 2, Step 3, Summary."
    
    # Call DeepSeek API
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2048
                }
            )
            
            if response.status_code != 200:
                print(f"DeepSeek API error: {response.status_code} - {response.text}")
                return JSONResponse(
                    status_code=response.status_code,
                    content={"error": f"DeepSeek API error: {response.text[:200]}"}
                )
            
            data = response.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "No response")
            
            return {"response": reply, "portal": portal}
            
    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"error": "DeepSeek API timeout"})
    except Exception as e:
        print(f"Internal error: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Internal error: {str(e)}"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
