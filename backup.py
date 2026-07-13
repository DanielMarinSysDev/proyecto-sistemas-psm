import os
import shutil
from datetime import datetime
import zipfile

def realizar_respaldo():
    """
    Script para crear una copia de seguridad de la base de datos SQLite.
    Se ejecuta independientemente del servidor Flask (ej. vía Tareas Programadas de Windows).
    """
    db_file = "sistema_gestion_produccion.db"
    backup_dir = "backups"
    
    if not os.path.exists(db_file):
        print(f"Error: No se encontró la base de datos '{db_file}'.")
        return
        
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"Directorio de respaldos '{backup_dir}' creado.")
        
    fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"taskcore_db_backup_{fecha_str}.zip"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    print(f"Iniciando respaldo de {db_file}...")
    
    try:
        # Crear archivo ZIP con compresión
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(db_file, os.path.basename(db_file))
            
        print(f"✅ Respaldo exitoso: {backup_path}")
        
    except Exception as e:
        print(f"❌ Error durante el respaldo: {e}")

if __name__ == "__main__":
    realizar_respaldo()
