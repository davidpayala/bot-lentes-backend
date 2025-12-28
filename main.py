from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from pydantic import BaseModel
import os

# --- CONFIGURACIÓN BASE DE DATOS ---
# Railway nos da la URL en esta variable. Si no existe (local), usa sqlite.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# Ajuste necesario porque Railway a veces da la URL con 'postgres://' y SQLAlchemy quiere 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELO (TABLA) ---
class Mensaje(Base):
    __tablename__ = "mensajes"
    id = Column(Integer, primary_key=True, index=True)
    cliente_nombre = Column(String(100))
    telefono = Column(String(50))
    texto = Column(Text)
    fecha = Column(DateTime, default=datetime.utcnow)

class Producto(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100))      # Ej: Freshlady Dream
    color = Column(String(50))        # Ej: Honey, Green
    precio = Column(Integer)          # Ej: 55
    stock = Column(Integer)           # Ej: 10
    descripcion = Column(Text)        # Ej: Lentes anuales, muy naturales

# Crear las tablas en la BD (si no existen)
Base.metadata.create_all(bind=engine)

# --- APP ---
app = FastAPI()
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "KM_LENTES_SECRET_123")

@app.get("/")
def home():
    return {"status": "Bot con Memoria Activo 🧠"}

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
        entry = body['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        
        if 'messages' in value:
            msg_data = value['messages'][0]
            contact_data = value['contacts'][0]
            
            # 1. Extraer datos
            texto = msg_data['text']['body']
            telefono = msg_data['from']
            nombre = contact_data['profile']['name']
            
            # 2. Guardar en Base de Datos
            db = SessionLocal()
            nuevo_mensaje = Mensaje(
                cliente_nombre=nombre,
                telefono=telefono,
                texto=texto
            )
            db.add(nuevo_mensaje)
            db.commit()
            db.close()
            
            print(f"✅ Guardado en BD: {nombre} dijo '{texto}'")
            
        return {"status": "received"}
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error"}
    
# Esto sirve para validar los datos que envíes
class ProductoCrear(BaseModel):
    nombre: str
    color: str
    precio: int
    stock: int
    descripcion: str

@app.post("/crear-producto")
async def crear_producto(producto: ProductoCrear):
    db = SessionLocal()
    nuevo_producto = Producto(
        nombre=producto.nombre,
        color=producto.color,
        precio=producto.precio,
        stock=producto.stock,
        descripcion=producto.descripcion
    )
    db.add(nuevo_producto)
    db.commit()
    db.close()
    return {"status": "Producto agregado", "producto": producto.nombre}

@app.get("/productos")
async def listar_productos():
    db = SessionLocal()
    productos = db.query(Producto).all()
    db.close()
    return productos