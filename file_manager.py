# ----------------------------------------------------------------------
# Copyright (c) 2026 Daniel Marin SysDev.
# Todos los derechos reservados.
# Este archivo es propiedad exclusiva de Daniel Marin.
# Queda prohibida su reproducción o distribución sin autorización.
# ----------------------------------------------------------------------
import os
import shutil
import platform
import logging
from dotenv import load_dotenv
load_dotenv()

# Configurar el logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Definir la ruta base para pruebas locales o contenedores
default_dir = r"D:\TaskCore_Archivos_Test" if (os.name == 'nt' and os.path.exists("D:\\")) else os.path.join(os.path.dirname(os.path.abspath(__file__)), "TaskCore_Archivos")
BASE_DIR = os.environ.get("BASE_DIR", default_dir)

def sanitize_name(name):
    """
    Limpia el nombre de caracteres inválidos para carpetas en Windows.
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    return name.strip()

def inferir_categoria_material(name_or_desc):
    """
    Infiere la categoría del material basado en el texto descriptivo del proyecto.
    Retorna una etiqueta como [VINIL], [LONA], [ACRILICO], [MDF], [PVC], o [OTROS].
    """
    text = name_or_desc.lower()
    if "vinil" in text or "sticker" in text or "adhesivo" in text:
        if "transparente" in text or "clear" in text:
            return "[VINIL_CLEAR]"
        if "microperforado" in text:
            return "[VINIL_MICRO]"
        return "[VINIL]"
    elif "lona" in text or "banner" in text or "mesh" in text or "pendon" in text or "pendón" in text:
        return "[LONA_BANNER]"
    elif "acrilico" in text or "acrílico" in text:
        return "[ACRILICO]"
    elif "mdf" in text or "madera" in text:
        return "[MDF]"
    elif "pvc" in text or "coroplast" in text:
        return "[PVC_RÍGIDO]"
    elif "vidrio" in text:
        return "[VIDRIO]"
    elif "corte" in text:
        return "[CORTE]"
    return "[OTROS]"

def create_master_data_folder(cliente_id, nombre_cliente):
    """
    Crea la carpeta de Master Data para un nuevo cliente.
    Ruta: D:\TaskCore_Archivos_Test\Clientes_Master\[ID]_[Nombre]\Activos_Permanentes
    """
    safe_name = sanitize_name(nombre_cliente)
    folder_name = f"{cliente_id}_{safe_name}"
    
    path = os.path.join(BASE_DIR, "Clientes_Master", folder_name, "Activos_Permanentes")
    
    try:
        os.makedirs(path, exist_ok=True)
        logger.info(f"Carpeta Master Data creada exitosamente en: {path}")
        return path
    except Exception as e:
        logger.error(f"Error creando carpeta Master Data: {e}")
        raise

def create_pedido_folders(cliente_id, pedido_id, articulos_nombres, anio, mes, master_data_path):
    """
    Crea la carpeta Padre para el Pedido y las subcarpetas Hijo para cada Artículo.
    Ruta: BASE_DIR/Servicios_Soporte/[AÑO]/[MES]/[ID_CLIENTE]_PEDIDO_[ID_PEDIDO]/
    """
    folder_name = f"{cliente_id}_PEDIDO_{pedido_id}"
    pedido_path = os.path.join(BASE_DIR, "Servicios_Soporte", str(anio), str(mes), folder_name)
    
    articulos_rutas = []
    
    try:
        # Crear carpeta principal del Pedido
        os.makedirs(pedido_path, exist_ok=True)
        
        # Crear subcarpetas para cada Artículo
        subcarpetas = ['Diagnostico_Firmware', 'Entregables_Reportes', 'Evidencia_Fotos']
        
        for idx, nombre_articulo in enumerate(articulos_nombres, start=1):
            safe_articulo = sanitize_name(nombre_articulo)
            articulo_folder = f"Articulo_{idx}_{safe_articulo}"
            articulo_path = os.path.join(pedido_path, articulo_folder)
            
            for sub in subcarpetas:
                os.makedirs(os.path.join(articulo_path, sub), exist_ok=True)
                
            # Enlace Simbólico directamente en la raíz de la carpeta del artículo
            _create_symlink(master_data_path, articulo_path)
            
            articulos_rutas.append(articulo_path)
            
        logger.info(f"Carpetas de Soporte creadas en: {pedido_path}")
        return pedido_path, articulos_rutas
        
    except Exception as e:
        logger.error(f"Error creando carpetas de soporte: {e}")
        raise

def _create_symlink(target_path, dest_dir):
    """
    Crea un enlace simbólico desde la carpeta de recursos de la orden hacia los Activos Permanentes del cliente.
    En Windows, requiere permisos de administrador o "Developer Mode" activo.
    """
    if not target_path or not os.path.exists(target_path):
        logger.warning(f"Ruta target_path para symlink no válida: {target_path}")
        return

    symlink_name = os.path.join(dest_dir, "ACCESO_DIRECTO_Activos_Permanentes")
    
    try:
        # Intentar crear enlace simbólico real (Requiere permisos en Windows)
        os.symlink(target_path, symlink_name, target_is_directory=True)
        logger.info(f"Enlace simbólico creado: {symlink_name} -> {target_path}")
    except OSError as e:
        # winerror 1314: Un privilegio requerido no está en poder del cliente.
        logger.warning(f"No se pudo crear el enlace simbólico (¿Faltan permisos de Admin?). Creando acceso por texto alternativo. Error: {e}")
        
        # Fallback: Crear un archivo de texto con la ruta en caso de fallo de permisos
        fallback_file = os.path.join(dest_dir, "LEER_Activos_Permanentes.txt")
        with open(fallback_file, "w") as f:
            f.write(f"Los activos permanentes (Logos, Manuales) de este cliente se encuentran en la siguiente ruta:\n\n{target_path}\n\n(Copia y pega esta ruta en el explorador de archivos)")

def vincular_archivos_a_hot_folder(articulo_path, maquina, anio, mes_nombre, dia, prefijo_nombre):
    """
    Busca los archivos en Entregables_Reportes del artículo
    y crea Hard Links en las carpetas de las colas de soporte correspondientes.
    """
    raiz_origen = os.path.join(articulo_path, "Entregables_Reportes")
    mapeos_a_vincular = []
    
    if os.path.exists(raiz_origen):
        archivos_raiz = [f for f in os.listdir(raiz_origen) if os.path.isfile(os.path.join(raiz_origen, f))]
        if archivos_raiz:
            mapeos_a_vincular.append((raiz_origen, maquina))
                
    if not mapeos_a_vincular:
        logger.warning(f"No hay archivos en {articulo_path} para enviar a soporte.")
        return False
        
    exito_total = True
    for origen_dir, maquina_destino in mapeos_a_vincular:
        archivos = [f for f in os.listdir(origen_dir) if os.path.isfile(os.path.join(origen_dir, f))]
        if not archivos:
            continue
            
        maquina_dir = os.path.join(BASE_DIR, "Cola_Soporte", maquina_destino)
        os.makedirs(maquina_dir, exist_ok=True)
        procesando_dir = os.path.join(maquina_dir, "Procesando")
        os.makedirs(procesando_dir, exist_ok=True)
        os.makedirs(os.path.join(procesando_dir, "Completado"), exist_ok=True)
        
        for archivo in archivos:
            ruta_origen = os.path.join(origen_dir, archivo)
            categoria = inferir_categoria_material(prefijo_nombre)
            
            nombre_destino = f"{categoria} {prefijo_nombre} - {archivo}"
            nombre_destino = sanitize_name(nombre_destino)
            ruta_destino = os.path.join(maquina_dir, nombre_destino)
            
            if os.path.exists(ruta_destino):
                continue
                
            try:
                os.link(ruta_origen, ruta_destino)
                logger.info(f"Hard Link creado en la Cola de [{maquina_destino}]: {ruta_destino}")
            except OSError as e:
                logger.warning(f"No se pudo crear Hard Link ({maquina_destino}), copiando archivo... Error: {e}")
                try:
                    shutil.copy2(ruta_origen, ruta_destino)
                    logger.info(f"Archivo copiado a [{maquina_destino}]: {ruta_destino}")
                except Exception as e2:
                    logger.error(f"Error copiando archivo: {e2}")
                    exito_total = False
                    
    return exito_total

def vincular_editable_a_cliente(articulo_path, cliente_activos_path, prefijo_nombre):
    """
    Busca los archivos en 'Diagnostico_Firmware'
    y crea un Hard Link (o copia) en la carpeta de Activos Permanentes del cliente.
    """
    if not cliente_activos_path or not os.path.exists(cliente_activos_path):
        logger.warning(f"Ruta de Activos Permanentes no válida o inexistente: {cliente_activos_path}")
        return False
        
    origen_dir = os.path.join(articulo_path, "Diagnostico_Firmware")
    if not os.path.exists(origen_dir):
        logger.warning(f"No existe la carpeta Diagnostico_Firmware: {origen_dir}")
        return False
        
    archivos = [f for f in os.listdir(origen_dir) if os.path.isfile(os.path.join(origen_dir, f))]
    if not archivos:
        logger.warning(f"No hay archivos en {origen_dir} para respaldar en el cliente.")
        return False
        
    exito = True
    for archivo in archivos:
        ruta_origen = os.path.join(origen_dir, archivo)
        
        categoria = inferir_categoria_material(prefijo_nombre)
        nombre_destino = f"{categoria} {prefijo_nombre} - {archivo}"
        nombre_destino = sanitize_name(nombre_destino)
        ruta_destino = os.path.join(cliente_activos_path, nombre_destino)
        
        if os.path.exists(ruta_destino):
            continue
            
        try:
            os.link(ruta_origen, ruta_destino)
            logger.info(f"Hard Link de diagnóstico creado en Activos del Cliente: {ruta_destino}")
        except OSError as e:
            logger.warning(f"No se pudo crear Hard Link de diagnóstico, copiando... Error: {e}")
            try:
                shutil.copy2(ruta_origen, ruta_destino)
                logger.info(f"Archivo de diagnóstico copiado a Activos del Cliente: {ruta_destino}")
            except Exception as e2:
                logger.error(f"Error copiando archivo de diagnóstico a Activos del Cliente: {e2}")
    return exito

def inicializar_carpetas_sistema():
    """
    Verifica e inicializa la estructura de directorios necesaria para el sistema.
    """
    directorios_principales = [
        os.path.join(BASE_DIR, "Clientes_Master"),
        os.path.join(BASE_DIR, "Servicios_Soporte"),
        os.path.join(BASE_DIR, "Cola_Soporte"),
        os.path.join(BASE_DIR, "Cola_Soporte", "Historial")
    ]
    
    for path in directorios_principales:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            logger.info(f"[INIT] Carpeta del sistema creada: {path}")

    maquinas = ['SOPORTE_TECNICO', 'LABORATORIO_HARDWARE', 'LABORATORIO_SOFTWARE', 'DIAGNOSTICOS', 'CONTROL_CALIDAD']
    for maquina in maquinas:
        maquina_dir = os.path.join(BASE_DIR, "Cola_Soporte", maquina)
        
        rutas_maquina = [
            maquina_dir,
            os.path.join(maquina_dir, "Procesando"),
            os.path.join(maquina_dir, "Procesando", "Completado"),
            os.path.join(maquina_dir, "Procesando", "Completado", "Historial_Diario")
        ]
        for path in rutas_maquina:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
                logger.info(f"[INIT] Carpeta de estación [{maquina}] creada: {path}")

