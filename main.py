from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
import os

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "KM_LENTES_SECRET_123")

@app.get("/")
async def home():
    return {"status": "El bot está vivo y listo para vender lentes"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params.get("hub.challenge"), status_code=200)
    else:
        raise HTTPException(status_code=403, detail="Token inválido")

@app.post("/webhook")
async def receive_message(request: Request):
    try:
        body = await request.json()
        
        # Navegamos dentro del JSON para encontrar el mensaje
        entry = body['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        
        # Verificamos si hay un mensaje real (a veces llegan estados de "leído" o "entregado")
        if 'messages' in value:
            message = value['messages'][0]
            
            # EXTRAEMOS LOS DATOS IMPORTANTES
            numero = message['from']
            texto = message['text']['body']
            nombre = value['contacts'][0]['profile']['name']
            
            # Por ahora, solo imprimimos limpio en la consola
            print(f"😎 NUEVO CLIENTE DETECTADO:")
            print(f"Nombre: {nombre}")
            print(f"Teléfono: {numero}")
            print(f"Dice: {texto}")
            print("-" * 20)
            
            # AQUI ES DONDE CONECTAREMOS LA BASE DE DATOS LUEGO
            
        return {"status": "received"}
        
    except Exception as e:
        # Si algo falla (ej. formato inesperado), lo imprimimos pero no rompemos el servidor
        print(f"Error procesando mensaje: {e}")
        return {"status": "error"}