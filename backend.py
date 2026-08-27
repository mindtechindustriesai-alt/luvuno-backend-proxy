import os
import json
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")

class ChatRequest(BaseModel):
    message: str
    debt_amount: float = 25000
    creditor_type: str = "Bank/Creditor"

@app.get("/")
async def root():
    return {"status": "operational", "key_set": bool(OPENROUTER_KEY)}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not OPENROUTER_KEY:
        return {"error": "OpenRouter key not configured"}

    try:
        system_prompt = f"""You are a tough but fair {request.creditor_type} negotiating debt repayment in South Africa.

STRICT RULES:
- The CURRENT DEBT AMOUNT is exactly R{request.debt_amount:.0f}. This number NEVER changes.
- You MUST ALWAYS use R{request.debt_amount:.0f} as the debt amount in your calculations.
- Do NOT hallucinate different debt amounts like R15,000 or R50,000.
- Calculate: months = debt / monthly_payment. Always do this math.
- Keep responses under 3 sentences.
- Be firm but reasonable."""

        payload = {
            "model": "google/gemini-2.5-flash-1.5b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ],
            "temperature": 0.7,
            "max_tokens": 300
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://salary-plan-app.onrender.com",
                    "X-Title": "SalaryPlan"
                },
                json=payload
            )
            data = res.json()
            
            if res.status_code != 200:
                return {"error": data.get("error", {}).get("message", "API Call Failed")}
            
            reply = data["choices"][0]["message"]["content"]
            return {"response": reply}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
