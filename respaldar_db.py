# ----------------------------------------------------------------------
# Copyright (c) 2026 TaskCore.
# Todos los derechos reservados.
# ----------------------------------------------------------------------
import os
import datetime
import subprocess
import hmac
import hashlib
from urllib.parse import urlparse
from dotenv import load_dotenv
from database_models import engine

# Cargar variables del archivo .env
load_dotenv()

def realizar_respaldo_python(archivo_salida):
    """
    Genera un respaldo de base de datos en SQL usando Python puro.
    Ideal para entornos sin pg_dump instalado o contenedores Docker ausentes (como Render/Heroku).
    """
    from sqlalchemy.sql import text
    
    is_postgres = "postgresql" in str(engine.url)
    
    with open(archivo_salida, "w", encoding="utf-8") as f:
        # Encabezado
        f.write("-- -----------------------------------------------------\n")
        f.write(f"-- Respaldo TaskCore generado por Python el {datetime.datetime.now()}\n")
        f.write("-- -----------------------------------------------------\n\n")
        
        if is_postgres:
            f.write("SET session_replication_role = 'replica';\n\n")
            tablas = [
                "incidencias", "logs_auditoria", "archivos_adjuntos", 
                "ordenes_trabajo", "pedidos", "usuario_roles", 
                "configuraciones", "precios_materiales", "clientes", "usuarios"
            ]
            f.write(f"TRUNCATE TABLE {', '.join(tablas)} RESTART IDENTITY CASCADE;\n\n")
        else:
            f.write("PRAGMA foreign_keys = OFF;\n\n")
            tablas = [
                "incidencias", "logs_auditoria", "archivos_adjuntos", 
                "ordenes_trabajo", "pedidos", "usuario_roles", 
                "configuraciones", "precios_materiales", "clientes", "usuarios"
            ]
            for t in tablas:
                f.write(f"DELETE FROM {t};\n")
            f.write("\n")
            
        # Orden de inserción para respetar las dependencias
        orden_insercion = [
            "usuarios", "clientes", "precios_materiales", "configuraciones", 
            "usuario_roles", "pedidos", "ordenes_trabajo", "archivos_adjuntos", 
            "logs_auditoria", "incidencias"
        ]
        
        with engine.connect() as conn:
            for tabla_name in orden_insercion:
                f.write(f"-- Datos de la tabla {tabla_name}\n")
                try:
                    result = conn.execute(text(f"SELECT * FROM {tabla_name}"))
                    cols = result.keys()
                    rows = result.all()
                except Exception as table_err:
                    f.write(f"-- Error al leer tabla {tabla_name}: {table_err}\n\n")
                    continue
                
                if not rows:
                    f.write(f"-- Sin registros en {tabla_name}\n\n")
                    continue
                    
                for row in rows:
                    val_list = []
                    for val in row:
                        if val is None:
                            val_list.append("NULL")
                        elif isinstance(val, bool):
                            val_list.append("TRUE" if val else "FALSE")
                        elif isinstance(val, (int, float)):
                            val_list.append(str(val))
                        elif isinstance(val, datetime.datetime):
                            val_list.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
                        else:
                            escapado = str(val).replace("'", "''")
                            val_list.append(f"'{escapado}'")
                            
                    col_str = ", ".join(cols)
                    val_str = ", ".join(val_list)
                    f.write(f"INSERT INTO {tabla_name} ({col_str}) VALUES ({val_str});\n")
                f.write("\n")
                
        if is_postgres:
            f.write("\n-- Actualizar secuencias de autoincremento\n")
            for tabla_name in orden_insercion:
                if tabla_name != "usuario_roles":
                    f.write(f"SELECT setval(pg_get_serial_sequence('{tabla_name}', 'id'), coalesce(max(id), 1), max(id) IS NOT null) FROM {tabla_name};\n")
            f.write("\nSET session_replication_role = 'origin';\n")
        else:
            f.write("PRAGMA foreign_keys = ON;\n")
            
    return True

def realizar_respaldo():
    carpeta_respaldos = os.getenv("BACKUP_DIR")
    if not carpeta_respaldos:
        ruta_raiz = os.path.dirname(os.path.abspath(__file__))
        carpeta_respaldos = os.path.join(ruta_raiz, "respaldos")
        
    if not os.path.exists(carpeta_respaldos):
        try:
            os.makedirs(carpeta_respaldos)
        except Exception as e:
            print(f"[ERROR] No se pudo crear la carpeta de respaldos: {e}")
            ruta_raiz = os.path.dirname(os.path.abspath(__file__))
            carpeta_respaldos = os.path.join(ruta_raiz, "respaldos")
            if not os.path.exists(carpeta_respaldos):
                os.makedirs(carpeta_respaldos)
        
    fecha_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"respaldo_taskcore_{fecha_str}.sql"
    archivo_salida = os.path.join(carpeta_respaldos, nombre_archivo)
    
    # Intentar respaldar usando comandos pg_dump si corresponden y están disponibles
    respaldado = False
    
    # 1. Intentar con Docker si está configurado para desarrollo local
    db_container = os.getenv("DB_CONTAINER")
    if db_container:
        db_user = os.getenv("DB_USER", "taskcore_user")
        db_name = os.getenv("DB_NAME", "sistema_taskcore")
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
            respaldado = True
            print("[INFO] Respaldo generado mediante pg_dump de Docker.")
        except Exception as docker_err:
            print(f"[Aviso] No se pudo respaldar vía Docker: {docker_err}. Probando otras opciones...")

    # 2. Intentar con pg_dump nativo si hay DATABASE_URL configurada y pg_dump disponible
    if not respaldado and "postgresql" in str(engine.url):
        try:
            database_url = os.getenv("DATABASE_URL")
            if database_url:
                url = urlparse(database_url)
                env_cmd = os.environ.copy()
                if url.password:
                    env_cmd["PGPASSWORD"] = url.password
                
                port_val = str(url.port or 5432)
                comando = [
                    "pg_dump",
                    "-h", url.hostname,
                    "-p", port_val,
                    "-U", url.username,
                    "-d", url.path.lstrip('/'),
                    "--clean",
                    "--no-owner",
                    "--no-privileges"
                ]
                with open(archivo_salida, "w", encoding="utf-8") as f:
                    subprocess.run(comando, stdout=f, env=env_cmd, check=True)
                respaldado = True
                print("[INFO] Respaldo generado mediante pg_dump nativo.")
        except Exception as pg_dump_err:
            print(f"[Aviso] No se pudo respaldar vía pg_dump nativo: {pg_dump_err}. Probando fallback a Python...")

    # 3. Fallback a Python puro
    if not respaldado:
        try:
            realizar_respaldo_python(archivo_salida)
            respaldado = True
            print("[INFO] Respaldo generado mediante generador SQL Python puro (Fallback exitoso).")
        except Exception as python_err:
            print(f"[ERROR] Falló el generador SQL Python puro: {python_err}")
            if os.path.exists(archivo_salida):
                os.remove(archivo_salida)
            return False, str(python_err)

    # Si se completó el respaldo, aplicar firma HMAC
    try:
        secret_key = os.getenv("SECRET_KEY", "dev_key_temporal_secreta_12345")
        
        with open(archivo_salida, "r", encoding="utf-8", errors="ignore") as f_read:
            contenido_texto = f_read.read().rstrip()
            
        firma = hmac.new(secret_key.encode('utf-8'), contenido_texto.encode('utf-8'), hashlib.sha256).hexdigest()
        
        with open(archivo_salida, "a", encoding="utf-8", newline="\n") as f_append:
            f_append.write(f"\n-- FIRMA_AUTENTICIDAD_TASKCORE:{firma}\n")

        print(f"\n====================================================")
        print(f"[OK] Respaldo de Base de Datos Creado Exitosamente")
        print(f"====================================================")
        print(f" Archivo: {nombre_archivo}")
        print(f" Sello:   {firma[:10]}... (Verificado)")
        print(f"====================================================\n")
        
        return True, archivo_salida
    except Exception as e:
        print(f"\n[ERROR] No se pudo firmar el respaldo: {e}\n")
        if os.path.exists(archivo_salida):
            os.remove(archivo_salida)
        return False, str(e)

if __name__ == "__main__":
    realizar_respaldo()
