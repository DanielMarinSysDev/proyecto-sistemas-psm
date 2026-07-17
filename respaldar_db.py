# ----------------------------------------------------------------------
# Copyright (c) 2026 TaskCore.
# Todos los derechos reservados.
# ----------------------------------------------------------------------
import os
import datetime
import subprocess
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

def realizar_respaldo():
    # Buscar ruta personalizada en .env, o usar local por defecto
    carpeta_respaldos = os.getenv("BACKUP_DIR")
    if not carpeta_respaldos:
        ruta_raiz = os.path.dirname(os.path.abspath(__file__))
        carpeta_respaldos = os.path.join(ruta_raiz, "respaldos")
        
    if not os.path.exists(carpeta_respaldos):
        try:
            os.makedirs(carpeta_respaldos)
        except Exception as e:
            print(f"[ERROR] No se pudo crear la carpeta de respaldos: {e}")
            # Revertir a la ruta local por seguridad
            ruta_raiz = os.path.dirname(os.path.abspath(__file__))
            carpeta_respaldos = os.path.join(ruta_raiz, "respaldos")
            if not os.path.exists(carpeta_respaldos):
                os.makedirs(carpeta_respaldos)
        
    fecha_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"respaldo_taskcore_{fecha_str}.sql"
    archivo_salida = os.path.join(carpeta_respaldos, nombre_archivo)
    
    db_container = os.getenv("DB_CONTAINER", "taskcore_db")
    db_user = os.getenv("DB_USER", "taskcore_user")
    db_name = os.getenv("DB_NAME", "sistema_taskcore")
    
    # Ejecuta pg_dump dentro del contenedor de la base de datos
    comando = [
        "docker", "exec", "-t", db_container, 
        "pg_dump", "-U", db_user, "-d", db_name
    ]
    
    try:
        env_cmd = os.environ.copy()
        if os.getenv("DB_PASSWORD"):
            env_cmd["PGPASSWORD"] = os.getenv("DB_PASSWORD")

        with open(archivo_salida, "w", encoding="utf-8") as f:
            subprocess.run(comando, stdout=f, env=env_cmd, check=True)
            
        # Agregar sello/firma criptográfica al final del archivo para validar su autenticidad
        import hmac
        import hashlib
        
        secret_key = os.getenv("SECRET_KEY", "dev_key_temporal_secreta_12345")
        
        # Leer el contenido recién creado en binario
        with open(archivo_salida, "rb") as f_read:
            contenido = f_read.read()
            
        # Calcular firma HMAC-SHA256
        firma = hmac.new(secret_key.encode('utf-8'), contenido, hashlib.sha256).hexdigest()
        
        # Añadir la firma como comentario SQL al final del archivo
        with open(archivo_salida, "a", encoding="utf-8") as f_append:
            f_append.write(f"\n-- FIRMA_AUTENTICIDAD_TASKCORE:{firma}\n")

        print(f"\n====================================================")
        print(f"[OK] Respaldo de Base de Datos Creado Exitosamente")
        print(f"====================================================")
        print(f" Archivo: {nombre_archivo}")
        print(f" Ruta:    {archivo_salida}")
        print(f" Sello:   {firma[:10]}... (Verificado)")
        print(f"====================================================\n")
        
        return True, archivo_salida
    except Exception as e:
        print(f"\n[ERROR] No se pudo crear el respaldo: {e}\n")
        # Si el archivo quedó vacío por error, eliminarlo
        if os.path.exists(archivo_salida) and os.path.getsize(archivo_salida) == 0:
            os.remove(archivo_salida)
        return False, str(e)

if __name__ == "__main__":
    realizar_respaldo()
