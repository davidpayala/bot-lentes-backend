import os
import pandas as pd
from sqlalchemy import create_engine
from woocommerce import API
import urllib.parse
import time

# --- 1. CONFIGURACIÓN RAILWAY ---
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')

# --- 2. CONFIGURACIÓN WORDPRESS ---
WC_URL = os.getenv('WC_URL')
WC_KEY = os.getenv('WC_KEY')
WC_SECRET = os.getenv('WC_SECRET')

def obtener_datos_railway():
    print("📥 Leyendo stock total desde Railway...")
    password_encoded = urllib.parse.quote_plus(DB_PASS)
    connection_string = f'postgresql+psycopg2://{DB_USER}:{password_encoded}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    
    engine = create_engine(connection_string)
    with engine.connect() as conn:
        query = "SELECT sku, stock_total_web FROM Vista_Stock_Web"
        df = pd.read_sql(query, conn)
    
    return dict(zip(df['sku'], df['stock_total_web']))

def actualizar_woocommerce():
    stock_db = obtener_datos_railway()
    print(f"📊 Base de datos tiene {len(stock_db)} SKUs listos.")

    wcapi = API(
        url=WC_URL,
        consumer_key=WC_KEY,
        consumer_secret=WC_SECRET,
        version="wc/v3",
        timeout=60 # Aumentamos tiempo de espera por seguridad
    )

    print("🌍 Conectando a WooCommerce...")
    
    page = 1
    productos_actualizados = 0
    
    while True:
        print(f"   🔍 Escaneando página {page}...")
        try:
            products = wcapi.get("products", params={"page": page, "per_page": 20}).json()
        except Exception as e:
            print(f"❌ Error de conexión en pág {page}: {e}")
            break
        
        if not products:
            break
        
        batch_simple_update = [] 

        for p in products:
            # === CASO A: PRODUCTO VARIABLE (LENTES CON MEDIDA) ===
            if p['type'] == 'variable':
                variations = wcapi.get(f"products/{p['id']}/variations", params={"per_page": 100}).json()
                
                stock_total_calculado = 0 # Sumaremos el stock de las variantes para decidir si mostramos el padre
                cambios_en_hijos = False

                for v in variations:
                    sku_web = v.get('sku')
                    if sku_web and sku_web in stock_db:
                        nuevo_stock = stock_db[sku_web]
                        stock_total_calculado += nuevo_stock # Vamos sumando
                        
                        stock_actual = v.get('stock_quantity')
                        # A veces stock_actual es None si no se gestionaba inventario
                        if stock_actual is None: stock_actual = 0

                        if int(stock_actual) != nuevo_stock:
                            print(f"      ✏️ Var {sku_web}: {stock_actual} -> {nuevo_stock}")
                            wcapi.put(f"products/{p['id']}/variations/{v['id']}", 
                                      {"manage_stock": True, "stock_quantity": nuevo_stock})
                            productos_actualizados += 1
                            cambios_en_hijos = True
                    else:
                        # Si la variante no está en el Excel, sumamos su stock actual (si tuviera)
                        # para no ocultar el producto por error.
                        if v.get('stock_quantity'):
                            stock_total_calculado += v.get('stock_quantity')

                # LOGICA DE VISIBILIDAD PADRE
                # Si el stock total es > 0, debe ser 'visible'. Si es 0, 'hidden'.
                visibilidad_actual = p.get('catalog_visibility')
                nueva_visibilidad = 'visible' if stock_total_calculado > 0 else 'hidden'
                
                if visibilidad_actual != nueva_visibilidad:
                    print(f"   👀 Actualizando visibilidad PADRE ({p['name']}): {visibilidad_actual} -> {nueva_visibilidad}")
                    wcapi.put(f"products/{p['id']}", {"catalog_visibility": nueva_visibilidad})


            # === CASO B: PRODUCTO SIMPLE (LÍQUIDOS/ACCESORIOS) ===
            else:
                sku_web = p.get('sku')
                if sku_web and sku_web in stock_db:
                    nuevo_stock = stock_db[sku_web]
                    stock_actual = p.get('stock_quantity')
                    if stock_actual is None: stock_actual = 0
                    visibilidad_actual = p.get('catalog_visibility')

                    # Definir nueva visibilidad basada en stock
                    nueva_visibilidad = 'visible' if nuevo_stock > 0 else 'hidden'
                    
                    # Actualizamos si cambió el stock O la visibilidad está mal
                    if int(stock_actual) != nuevo_stock or visibilidad_actual != nueva_visibilidad:
                        print(f"   ✏️ Simple {sku_web}: Stock {stock_actual}->{nuevo_stock} | Vis: {nueva_visibilidad}")
                        batch_simple_update.append({
                            "id": p['id'],
                            "manage_stock": True,
                            "stock_quantity": nuevo_stock,
                            "catalog_visibility": nueva_visibilidad
                        })

        # Enviar lote de simples
        if batch_simple_update:
            wcapi.post("products/batch", {"update": batch_simple_update})
            productos_actualizados += len(batch_simple_update)

        page += 1
        
    print("------------------------------------------------")
    print(f"✅ Sincronización completada. Items procesados: {productos_actualizados}")

if __name__ == '__main__':
    actualizar_woocommerce()