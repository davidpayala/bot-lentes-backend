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

# Definimos la tabla Mensajes con la NUEVA estructura
class Mensaje(Base):
    __tablename__ = "mensajes"
    id_mensaje = Column(Integer, primary_key=True, index=True) # Antes era 'id'
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=True)
    tipo = Column(String(20), default="ENTRANTE") # 'ENTRANTE' o 'SALIENTE'
    contenido = Column(Text) # Antes era 'texto'
    fecha = Column(DateTime, default=datetime.now)
    leido = Column(Boolean, default=False)
    whatsapp_id = Column(String(100), nullable=True)
    
    # Mantenemos estas columnas por si acaso (para no perder datos si el cliente es nuevo)
    telefono = Column(String(50), nullable=True)
    cliente_nombre = Column(String(100), nullable=True)

    hora_peru = datetime.utcnow() - timedelta(hours=5)

    # Creamos el nuevo mensaje con la hora corregida
    nuevo_mensaje = Mensaje(
    id_cliente=id_cliente_final,
    tipo="ENTRANTE",
    contenido=texto_recibido,
    cliente_nombre=nombre_perfil,
    telefono=telefono_bruto,
    whatsapp_id=w_id,
    leido=False, 
    fecha=hora_peru  # <--- AQUÍ USAMOS LA VARIABLE CORREGIDA
    )
                
    db.add(nuevo_mensaje)
    db.commit()
    print(f"✅ Mensaje guardado: {texto_recibido} a las {hora_peru}")


# Crear tablas si no existen (solo necesario si es una BD nueva)
# Base.metadata.create_all(bind=engine)

# --- APP ---
app = FastAPI()
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "KM_LENTES_SECRET_123")

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
async def receive_message(request: Request):
    try:
        body = await request.json()
        
        # Validamos que sea un mensaje real
        if 'entry' in body and len(body['entry']) > 0:
            changes = body['entry'][0]['changes'][0]
            value = changes['value']
            
            if 'messages' in value:
                msg_data = value['messages'][0]
                contact_data = value['contacts'][0]
                
                # 1. Extraer datos básicos
                texto_recibido = msg_data['text']['body']
                telefono_bruto = msg_data['from'] # Ej: 51999888777
                nombre_perfil = contact_data['profile']['name']
                w_id = msg_data['id']

                # 2. Limpiar teléfono para buscar en DB
                # Queremos los últimos 9 dígitos para comparar (Ej: 999888777)
                telefono_limpio = telefono_bruto.replace(" ", "").replace("+", "")
                if len(telefono_limpio) > 9:
                    telefono_busqueda = telefono_limpio[-9:]
                else:
                    telefono_busqueda = telefono_limpio

                # 3. Guardar en Base de Datos
                db = SessionLocal()
                
                # A) BÚSQUEDA ROBUSTA (Ignorando espacios y símbolos)
                # Limpiamos el campo 'telefono' de la base de datos al vuelo para comparar
                cliente_encontrado = db.query(Cliente).filter(
                    func.replace(func.replace(Cliente.telefono, ' ', ''), '+', '').like(f"%{telefono_busqueda}%")
                ).first()
                
                id_cliente_final = cliente_encontrado.id_cliente if cliente_encontrado else None

                # B) Creamos el mensaje con la estructura nueva
                nuevo_mensaje = Mensaje(
                    id_cliente=id_cliente_final,
                    tipo="ENTRANTE",           # Importante para el Chat Center
                    contenido=texto_recibido,  # Importante: ahora es 'contenido'
                    cliente_nombre=nombre_perfil, # Guardamos nombre de WhatsApp por si acaso
                    telefono=telefono_bruto,
                    whatsapp_id=w_id,
                    leido=False,
                    fecha=datetime.now()
                )
                
                db.add(nuevo_mensaje)
                db.commit()
                db.close()
                
                print(f"✅ Mensaje guardado de {nombre_perfil}. ID Cliente: {id_cliente_final}")
                
        return {"status": "received"}
    except Exception as e:
        print(f"Error procesando mensaje: {e}")
        return {"status": "error"}

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