# ----------------------------------------------------------------------
# Copyright (c) 2026 TaskCore.
# Todos los derechos reservados.
# ----------------------------------------------------------------------
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

def restaurar_archivo(nombre_archivo):
    """
    Restaura la base de datos a partir del archivo de respaldo proporcionado.
    nombre_archivo puede ser una ruta absoluta o el nombre de un archivo en BACKUP_DIR.
    """
    carpeta_respaldos = os.getenv("BACKUP_DIR")
    if not carpeta_respaldos:
        ruta_raiz = os.path.dirname(os.path.abspath(__file__))
        carpeta_respaldos = os.path.join(ruta_raiz, "respaldos")
    
    carpeta_respaldos = os.path.abspath(carpeta_respaldos)

    if os.path.isabs(nombre_archivo):
        ruta_seleccionada = os.path.abspath(nombre_archivo)
    else:
        ruta_seleccionada = os.path.abspath(os.path.join(carpeta_respaldos, nombre_archivo))

    if not os.path.exists(ruta_seleccionada):
        return False, f"El archivo de respaldo no existe: {ruta_seleccionada}"

    # VALIDAR FIRMA DE AUTENTICIDAD/INTEGRIDAD (Sello Criptográfico)
    import hmac
    import hashlib
    
    secret_key = os.getenv("SECRET_KEY", "dev_key_temporal_secreta_12345")
    
    try:
        with open(ruta_seleccionada, "r", encoding="utf-8", errors="ignore") as sf:
            lineas = sf.readlines()
    except Exception as e:
        return False, f"No se pudo leer el archivo para verificar el sello: {str(e)}"
        
    if not lineas:
        return False, "El archivo de respaldo está vacío."
        
    # Buscar si la última línea contiene la firma
    ultima_linea = lineas[-1].strip()
    if not ultima_linea.startswith("-- FIRMA_AUTENTICIDAD_TASKCORE:"):
        return False, "Error de Seguridad: El archivo no contiene un sello dinámico de autenticidad válido."
        
    firma_guardada = ultima_linea.replace("-- FIRMA_AUTENTICIDAD_TASKCORE:", "").strip()
    
    # El contenido original es todo excepto la última línea
    contenido_original = "".join(lineas[:-1]).encode('utf-8')
    
    # Calcular firma esperada
    firma_esperada = hmac.new(secret_key.encode('utf-8'), contenido_original, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(firma_guardada, firma_esperada):
        return False, "Error de Seguridad: El sello dinámico no coincide. El archivo ha sido manipulado o proviene de otro sistema."

    db_container = os.getenv("DB_CONTAINER", "taskcore_db")
    db_user = os.getenv("DB_USER", "taskcore_user")
    db_name = os.getenv("DB_NAME", "sistema_taskcore")

    comando = [
        "docker", "exec", "-i", db_container, 
        "psql", "-U", db_user, "-d", db_name
    ]

    try:
        env_cmd = os.environ.copy()
        if os.getenv("DB_PASSWORD"):
            env_cmd["PGPASSWORD"] = os.getenv("DB_PASSWORD")

        # Restaurar enviando solo el contenido original (sin la línea del sello para evitar comentarios basura al final)
        # o enviando todo el archivo ya que el comentario no afecta a psql. Usar el archivo completo es más directo y seguro
        with open(ruta_seleccionada, "r", encoding="utf-8") as f:
            subprocess.run(comando, stdin=f, env=env_cmd, check=True)
        return True, "Base de datos restaurada con éxito."
    except Exception as e:
        return False, str(e)

def restaurar_respaldo():
    carpeta_respaldos = os.getenv("BACKUP_DIR")
    if not carpeta_respaldos:
        ruta_raiz = os.path.dirname(os.path.abspath(__file__))
        carpeta_respaldos = os.path.join(ruta_raiz, "respaldos")

    if not os.path.exists(carpeta_respaldos):
        print(f"[ERROR] No se encontró la carpeta de respaldos en: {carpeta_respaldos}")
        return

    # Obtener archivos .sql ordenados por fecha de modificación (más reciente primero)
    archivos = [f for f in os.listdir(carpeta_respaldos) if f.endswith(".sql")]
    archivos.sort(key=lambda x: os.path.getmtime(os.path.join(carpeta_respaldos, x)), reverse=True)

    if not archivos:
        print("[ERROR] No se encontraron archivos de respaldo (.sql) en la carpeta.")
        return

    print("\n====================================================")
    print("        RESTAURACIÓN DE BASE DE DATOS TASKCORE       ")
    print("====================================================")
    print(" ¡ADVERTENCIA! Restaurar una base de datos sobrescribirá")
    print(" toda la información actual por la del respaldo.")
    print("====================================================\n")

    print("Selecciona el respaldo a restaurar:")
    for idx, archivo in enumerate(archivos):
        ruta_completa = os.path.join(carpeta_respaldos, archivo)
        tamano_kb = os.path.getsize(ruta_completa) / 1024
        print(f" [{idx + 1}] {archivo} ({tamano_kb:.1f} KB)")
    
    print(" [0] Cancelar operación")

    try:
        seleccion = int(input("\nIngresa el número de tu opción: "))
        if seleccion == 0:
            print("[INFO] Operación cancelada.")
            return
            
        if seleccion < 1 or seleccion > len(archivos):
            print("[ERROR] Opción inválida.")
            return
            
        archivo_seleccionado = archivos[seleccion - 1]
        
        print(f"\nRestaurando desde: {archivo_seleccionado}...")
        exito, msg = restaurar_archivo(archivo_seleccionado)
        
        if exito:
            print(f"\n====================================================")
            print(f"[OK] Base de Datos Restaurada con Éxito")
            print(f"====================================================")
            print(f" Respaldo utilizado: {archivo_seleccionado}")
            print(f"====================================================\n")
        else:
            print(f"\n[ERROR] Fallo al restaurar la base de datos: {msg}\n")
        
    except ValueError:
        print("[ERROR] Debes ingresar un número válido.")
    except Exception as e:
        print(f"\n[ERROR] Fallo al restaurar la base de datos: {e}\n")

if __name__ == "__main__":
    restaurar_respaldo()
