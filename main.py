from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from pydantic import BaseModel
import os
from sqlalchemy import func  # <--- AGREGAR ESTO ARRIBA
from datetime import datetime, timedelta # <--- Agrega ", timedelta"

# --- CONFIGURACIÓN BASE DE DATOS ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# Ajuste para Railway (postgres -> postgresql)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELOS (TABLAS ACTUALIZADAS) ---
# Definimos la tabla Clientes para poder buscar el ID
class Cliente(Base):
    __tablename__ = "clientes" # Asegúrate de que coincida con tu BD (mayus/minus)
    # Nota: En Postgres a veces se crean como "Clientes" o "clientes". 
    # Si falla, prueba cambiar a "Clientes" (con C mayúscula).
    id_cliente = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    apellido = Column(String)
    telefono = Column(String)

# --- APP ---
app = FastAPI()
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "KM_LENTES_SECRET_123")

# Definimos la tabla Mensajes con la NUEVA estructura
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

async def receive_whatsapp(request: Request):
    try:
        body = await request.json()
        
        # 1. PARSEO BÁSICO (Esto extrae los datos de WhatsApp)
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        
        if "messages" in value:
            message = value["messages"][0]
            telefono_bruto = message["from"]  # El número tal cual viene (ej: 51986...)
            texto_recibido = message["text"]["body"]
            w_id = message["id"]
            nombre_perfil = value["contacts"][0]["profile"]["name"]

            # --- 2. LÓGICA RECUPERADA: BUSCAR EL ID DEL CLIENTE ---
            # Abrimos conexión para buscar
            db = SessionLocal()
            try:
                # Buscamos si existe un cliente con ese teléfono
                query = text("SELECT id_cliente FROM Clientes WHERE telefono = :tel LIMIT 1")
                resultado = db.execute(query, {"tel": telefono_bruto}).fetchone()
                
                if resultado:
                    id_cliente_final = resultado[0] # ¡Lo encontramos!
                else:
                    id_cliente_final = None # Es un cliente nuevo o desconocido
                
                # --- 3. AHORA SÍ GUARDAMOS (Ya tenemos id_cliente_final) ---
                hora_peru = datetime.utcnow() - timedelta(hours=5)

                nuevo_mensaje = Mensaje(
                    id_cliente=id_cliente_final, # <--- Ahora esta variable SÍ existe
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
                print(f"✅ Mensaje guardado de {nombre_perfil} ({id_cliente_final})")
                
            except Exception as e:
                print(f"❌ Error interno DB: {e}")
                db.rollback()
            finally:
                db.close()
                
        return {"status": "ok"}
        
    except Exception as e:
        # Si no es un mensaje (ej: estado, check azul), lo ignoramos sin romper
        return {"status": "ignored"}

# Crear tablas si no existen (solo necesario si es una BD nueva)
# Base.metadata.create_all(bind=engine)

@app.get("/")
def home():
    return {"status": "🤖 Webhook CRM Activo v2.0"}

# Validación de WhatsApp (Meta)
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params.get("hub.challenge"), status_code=200)
    else:
        raise HTTPException(status_code=403, detail="Token inválido")

# Recepción de Mensajes
@app.post("/webhook")
async def receive_whatsapp(request: Request):
    try:
        body = await request.json()
        
        # Extracción de datos básica
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        
        if "messages" in value:
            message = value["messages"][0]
            telefono_bruto = message["from"]
            texto_recibido = message["text"]["body"]
            w_id = message["id"]
            nombre_perfil = value["contacts"][0]["profile"]["name"]

            # 1. BUSCAR ID DEL CLIENTE
            db = SessionLocal()
            try:
                query = text("SELECT id_cliente FROM Clientes WHERE telefono = :tel LIMIT 1")
                resultado = db.execute(query, {"tel": telefono_bruto}).fetchone()
                
                id_cliente_final = resultado[0] if resultado else None
                
                # --- 2. CALCULAR HORA PERÚ ---
                # Esta línea es la clave: UTC menos 5 horas
                hora_peru = datetime.utcnow() - timedelta(hours=5) # ⬅️ IMPORTANTE

                # --- 3. CREAR MENSAJE ---
                nuevo_mensaje = Mensaje(
                    id_cliente=id_cliente_final,
                    tipo="ENTRANTE",
                    contenido=texto_recibido,
                    cliente_nombre=nombre_perfil,
                    telefono=telefono_bruto,
                    whatsapp_id=w_id,
                    leido=False, 
                    fecha=hora_peru  # ⬅️ IMPORTANTE: Si borras esta línea, usará la hora de Londres
                )
                
                db.add(nuevo_mensaje)
                db.commit()
                print(f"✅ Mensaje guardado a las {hora_peru}")
                
            except Exception as e:
                print(f"❌ Error DB: {e}")
                db.rollback()
            finally:
                db.close()
                
        return {"status": "ok"}
        
    except Exception as e:
        return {"status": "ignored"}

# --- EXTRAS (Productos) ---
# (Mantenemos tu código de productos igual, no afecta al chat)
class ProductoCrear(BaseModel):
    nombre: str
    color: str
    precio: int
    stock: int
    descripcion: str

class ProductoDB(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100))
    color = Column(String(50))
    precio = Column(Integer)
    stock = Column(Integer)
    descripcion = Column(Text)

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