import time
import schedule
from datetime import datetime
import os

# Importamos las funciones de tus otros scripts
# (Asegúrate de que tus archivos sincronizar_web.py y actualizar_proveedor.py estén en la misma carpeta)
from sincronizar_web import actualizar_woocommerce
# Si tienes el de proveedor automatizado por API/Link, impórtalo también.
# Si el del proveedor requiere subir un archivo manual, ese NO se puede automatizar al 100% en nube
# a menos que leas el excel de un Google Drive o Dropbox público.

def tarea_sincronizacion():
    print(f"⏰ [INICIO] Ejecutando sincronización automática: {datetime.now()}")
    
    try:
        # 1. Ejecutar sincronización con la web
        actualizar_woocommerce()
        print("✅ Sincronización Web completada.")
        
    except Exception as e:
        print(f"❌ Error durante la ejecución automática: {e}")
        
    print(f"🏁 [FIN] Esperando siguiente ciclo...\n")

# --- CONFIGURACIÓN DEL HORARIO ---
# Opción A: Ejecutar cada 12 horas
schedule.every(12).hours.do(tarea_sincronizacion)

# Opción B: Ejecutar a horas específicas (ej. 8am y 8pm hora servidor)
# schedule.every().day.at("08:00").do(tarea_sincronizacion)
# schedule.every().day.at("20:00").do(tarea_sincronizacion)

print("🤖 Bot de Sincronización iniciado en Railway. Esperando instrucciones...")

# Ejecutar una vez al arrancar para no esperar 12 horas la primera vez
tarea_sincronizacion()

# Bucle Infinito (Mantiene al script vivo en Railway)
while True:
    schedule.run_pending()
    time.sleep(60) # Revisa cada minuto si ya toca trabajar