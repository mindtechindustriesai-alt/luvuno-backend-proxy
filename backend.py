from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import os
from datetime import datetime
import asyncio

app = FastAPI(title="Luvuno Backend Proxy", description="Secure proxy for DeepSeek API")

# CORS - Allow your frontend domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:5500",
        "https://luvuno-quantum-chat.onrender.com",
        "https://luvuno-frontend-1.onrender.com",
        "https://*.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (simple in-memory)
rate_limit_store = {}
RATE_LIMIT = 100  # requests per hour
RATE_WINDOW = 3600  # 1 hour in seconds

def check_rate_limit(client_ip: str):
    now = datetime.now().timestamp()
    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = []
    
    # Clean old entries
    rate_limit_store[client_ip] = [t for t in rate_limit_store[client_ip] if now - t < RATE_WINDOW]
    
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT:
        return False
    
    rate_limit_store[client_ip].append(now)
    return True

# DeepSeek API key from environment variable
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable not set")

@app.get("/")
async def root():
    return {
        "service": "Luvuno Backend Proxy",
        "status": "operational",
        "version": "1.0.0",
        "endpoints": ["POST /api/chat", "GET /health"]
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/chat")
async def chat(request: Request):
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"
    
    # Rate limit check
    if not check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded. Max 100 requests per hour."}
        )
    
    # Parse request body
    try:
        body = await request.json()
        message = body.get("message")
        portal = body.get("portal", "quantum")
        
        if not message:
            return JSONResponse(status_code=400, content={"error": "Message is required"})
        
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid request: {str(e)}"})
    
    # Build system prompt based on portal/skill
    system_prompt = f"You are Luvuno, an AI assistant for Luvuno OS. Current portal: {portal}. Answer clearly, concisely, and helpfully. Use emojis where appropriate. Format with proper paragraphs."
    
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
                return JSONResponse(
                    status_code=response.status_code,
                    content={"error": f"DeepSeek API error: {response.text}"}
                )
            
            data = response.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "No response")
            
            return {"response": reply, "portal": portal}
            
    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"error": "DeepSeek API timeout"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Internal error: {str(e)}"})

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)