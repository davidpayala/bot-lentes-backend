from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
import os

app = FastAPI()

# Usamos una variable de entorno para seguridad, o un valor por defecto si probamos local
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "KM_LENTES_SECRET_123")

@app.get("/")
async def home():
    return {"status": "El bot está vivo"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params.get("hub.challenge"), status_code=200)
    else:
        raise HTTPException(status_code=403, detail="Token inválido")

@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()
    print("¡Mensaje Recibido!", body)
    return {"status": "received"}