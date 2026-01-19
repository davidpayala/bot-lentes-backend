from fastapi import FastAPI, Depends, Request, Header, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, text, create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic import BaseModel
import os
from datetime import datetime, timedelta
import hmac
import hashlib

# --- 1. CONFIGURACIÓN DE SEGURIDAD (META) ---
APP_SECRET = os.getenv("APP_SECRET")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "KM_LENTES_SECRET_123")

async def verify_signature(request: Request, x_hub_signature_256: str = Header(None)):
    """
    Valida que la petición venga realmente de Facebook/Meta usando HMAC-SHA256.
    """
    if not APP_SECRET:
        print("⚠️ ADVERTENCIA: APP_SECRET no configurado. Saltando seguridad.")
        return

    if not x_hub_signature_256:
        raise HTTPException(status_code=403, detail="Firma de seguridad ausente")

    payload = await request.body()
    secret = bytes(APP_SECRET, 'utf-8')
    expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    expected_signature_with_prefix = f"sha256={expected_signature}"

    if not hmac.compare_digest(expected_signature_with_prefix, x_hub_signature_256):
        print(f"❌ Firma inválida. Recibida: {x_hub_signature_256}")
        raise HTTPException(status_code=403, detail="Firma de seguridad inválida")

# --- 2. CONFIGURACIÓN BASE DE DATOS ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# Ajuste para Railway (postgres -> postgresql)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 3. MODELOS DB ---
class Cliente(Base):
    __tablename__ = "clientes"
    id_cliente = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    apellido = Column(String)
    telefono = Column(String)
    # Agrega esto para que coincida con tu base de datos:
    fecha_registro = Column(DateTime, default=datetime.now)

class Mensaje(Base):
    __tablename__ = "mensajes"
    id_mensaje = Column(Integer, primary_key=True, index=True) 
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=True)
    tipo = Column(String(20), default="ENTRANTE")
    contenido = Column(Text)
    fecha = Column(DateTime, default=datetime.now)
    leido = Column(Boolean, default=False)
    whatsapp_id = Column(String(100), nullable=True)
    telefono = Column(String(50), nullable=True)
    cliente_nombre = Column(String(100), nullable=True)

class ProductoDB(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100))
    color = Column(String(50))
    precio = Column(Integer)
    stock = Column(Integer)
    descripcion = Column(Text)

class ProductoCrear(BaseModel):
    nombre: str
    color: str
    precio: int
    stock: int
    descripcion: str

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# --- 4. APLICACIÓN FASTAPI ---
app = FastAPI()

@app.get("/")
def home():
    return {"status": "🤖 Webhook CRM Seguro Activo v3.0"}

# Validación del Webhook (El "Handshake" inicial con Meta)
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params.get("hub.challenge"), status_code=200)
    else:
        raise HTTPException(status_code=403, detail="Token inválido")

# --- 5. RECEPCIÓN DE MENSAJES (PROTEGIDO) ---
@app.post("/webhook", dependencies=[Depends(verify_signature)])
async def receive_whatsapp(request: Request):
    try:
        body = await request.json()
        
        # Parseo inicial para asegurar que es un mensaje
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        
        if "messages" not in value:
            # Es una actualización de estado (leído, enviado), lo ignoramos por ahora
            return {"status": "ignored"}

        # Datos básicos del mensaje
        message = value["messages"][0]
        telefono_bruto = message["from"]
        w_id = message["id"]
        nombre_perfil = value["contacts"][0]["profile"]["name"]
        
        # --- DETECCIÓN DE TIPO DE MENSAJE ---
        tipo_mensaje = message["type"]
        texto_recibido = ""
        
        if tipo_mensaje == "text":
            texto_recibido = message["text"]["body"]
        
        elif tipo_mensaje == "image":
            media_id = message["image"]["id"] 
            caption = message["image"].get("caption", "")
            texto_recibido = f"📷 [Imagen] {caption} |ID:{media_id}|"

        elif tipo_mensaje == "sticker":
            media_id = message["sticker"]["id"]
            texto_recibido = f"👾 [Sticker] |ID:{media_id}|"

        elif tipo_mensaje == "audio":
            media_id = message["audio"]["id"]
            texto_recibido = f"🎤 [Audio] |ID:{media_id}|"
        
        elif tipo_mensaje == "document":
            media_id = message["document"]["id"]
            filename = message["document"].get("filename", "Archivo")
            texto_recibido = f"PFA [Documento] {filename} |ID:{media_id}|"
            
        else:
            texto_recibido = f"[{tipo_mensaje.upper()} RECIBIDO]"

        # --- LÓGICA DE BASE DE DATOS ---
        db = SessionLocal()
        try:
            # 1. Búsqueda inteligente de cliente (ignorando espacios/+/-)
            telefono_short = telefono_bruto[-9:] # Últimos 9 dígitos
            
            query = text("""
                SELECT id_cliente 
                FROM Clientes 
                WHERE REPLACE(REPLACE(REPLACE(telefono, ' ', ''), '-', ''), '+', '') LIKE :tel_parcial 
                LIMIT 1
            """)
            resultado = db.execute(query, {"tel_parcial": f"%{telefono_short}"}).fetchone()
            
            if resultado:
                id_cliente_final = resultado[0]
                print(f"✅ Cliente identificado: {id_cliente_final}")
            else:
                id_cliente_final = None
                print(f"⚠️ Nuevo contacto: {telefono_bruto}")
                # AQUI FALTA EL CÓDIGO PARA CREAR EL CLIENTE

            # 2. Guardar Mensaje
            hora_peru = datetime.utcnow() - timedelta(hours=5)

            nuevo_mensaje = Mensaje(
                id_cliente=id_cliente_final,
                tipo="ENTRANTE",
                contenido=texto_recibido,
                cliente_nombre=nombre_perfil,
                telefono=telefono_bruto,
                whatsapp_id=w_id,
                leido=False, 
                fecha=hora_peru 
            )
            
            db.add(nuevo_mensaje)
            db.commit()
            print("💾 Mensaje guardado en DB")
            
        except Exception as e:
            print(f"❌ Error DB: {e}")
            db.rollback()
        finally:
            db.close()
            
        return {"status": "ok"}
        
    except Exception as e:
        print(f"❌ Error general en webhook: {e}")
        return {"status": "error", "detail": str(e)}

# --- 6. ENDPOINTS DE PRODUCTOS ---
@app.post("/crear-producto")
async def crear_producto(producto: ProductoCrear):
    db = SessionLocal()
    nuevo_producto = ProductoDB(**producto.dict())
    db.add(nuevo_producto)
    db.commit()
    db.close()
    return {"status": "ok"}

@app.get("/productos")
async def listar_productos():
    db = SessionLocal()
    productos = db.query(ProductoDB).all()
    db.close()
    return productos