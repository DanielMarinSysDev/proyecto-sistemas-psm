# ----------------------------------------------------------------------
# Copyright (c) 2026 Daniel Marin SysDev.
# Todos los derechos reservados.
# Este archivo es propiedad exclusiva de Daniel Marin.
# Queda prohibida su reproducción o distribución sin autorización.
# ----------------------------------------------------------------------
import time
import os
import re
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configurar SQLAlchemy para conectarse a la DB de forma dinámica
from database_models import Base, OrdenTrabajo, EstadoOrdenEnum, LogAuditoria, Configuracion, Usuario, RolEnum, engine
from file_manager import BASE_DIR
from sqlalchemy.orm import sessionmaker

HEALTHCHECK_URL = "https://hc-ping.com/87dea9cc-59df-4214-a7ce-3a2af1b26dce"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

Session = sessionmaker(bind=engine)

# Carpeta a vigilar (construida dinámicamente)
WATCH_DIR = os.path.join(BASE_DIR, "Cola_Produccion")

# Expresión regular para extraer P#_A# (ej: [P3_A1])
REGEX_ID = re.compile(r"\[P\d+_A(\d+)\]")

class ProduccionEventHandler(FileSystemEventHandler):
    def on_moved(self, event):
        self.procesar_archivo(event.dest_path)
        
    def on_created(self, event):
        self.procesar_archivo(event.src_path)
        
    def procesar_archivo(self, ruta_archivo):
        if os.path.isdir(ruta_archivo):
            return
            
        nombre_archivo = os.path.basename(ruta_archivo)
        ruta_lower = ruta_archivo.lower()
        
        # Buscar ID del artículo en el nombre del archivo
        match = REGEX_ID.search(nombre_archivo)
        if not match:
            return
            
        articulo_id = int(match.group(1))
        
        # Determinar el nuevo estado basado en el nombre de la carpeta destino
        nuevo_estado = None
        if "\\3_completado" in ruta_lower or "\\completado" in ruta_lower or "\\listo" in ruta_lower or "\\terminado" in ruta_lower:
            # Comprobar si quedan otros archivos del mismo artículo en producción activa en otras máquinas
            hay_pendientes = False
            tag_busca = f"_A{articulo_id}]"
            
            for m in ['SOPORTE_TECNICO', 'LABORATORIO_HARDWARE', 'LABORATORIO_SOFTWARE', 'DIAGNOSTICOS', 'CONTROL_CALIDAD', 'PLOTTER', 'PLOTTER_CORTE', 'IMPRESORA_UV', 'LASER', 'CNC']:
                m_dir = os.path.join(WATCH_DIR, m)
                for folder in [m_dir, os.path.join(m_dir, "Procesando")]:
                    if os.path.exists(folder):
                        for item in os.listdir(folder):
                            # Si tiene el ID del artículo y es archivo
                            if tag_busca in item and os.path.isfile(os.path.join(folder, item)):
                                # Si no es el archivo actual que estamos procesando
                                if os.path.join(folder, item).lower() != ruta_archivo.lower():
                                    hay_pendientes = True
                                    break
                if hay_pendientes:
                    break
            
            if hay_pendientes:
                # Quedan procesos pendientes en otra máquina, se mantiene En Producción
                nuevo_estado = EstadoOrdenEnum.EN_PRODUCCION
            else:
                # Todo finalizado en todas las colas
                nuevo_estado = EstadoOrdenEnum.LISTO_INSTALAR_ENTREGAR
        elif "\\2_procesando" in ruta_lower or "\\procesando" in ruta_lower or "\\imprimiendo" in ruta_lower or "\\en_proceso" in ruta_lower or "\\en produccion" in ruta_lower:
            nuevo_estado = EstadoOrdenEnum.EN_PRODUCCION
            
        if nuevo_estado:
            self.actualizar_estado(articulo_id, nuevo_estado, ruta_archivo)
            
    def actualizar_estado(self, articulo_id, nuevo_estado, ruta):
        session = Session()
        try:
            orden = session.query(OrdenTrabajo).filter_by(id=articulo_id).first()
            if not orden:
                return
                
            # Si ya está en ese estado, no hacer nada
            if orden.estado == nuevo_estado:
                return
                
            estado_anterior = orden.estado.value
            orden.estado = nuevo_estado
            
            # Registrar auditoría (Usuario 1 = Admin/Sistema)
            log = LogAuditoria(
                usuario_id=1, 
                orden_id=articulo_id,
                accion="Automatización Hot Folder",
                detalles=f"Orden #{articulo_id} pasó de '{estado_anterior}' a '{nuevo_estado.value}' por movimiento a: {os.path.basename(os.path.dirname(ruta))}"
            )
            session.add(log)
            session.commit()
            
            logging.info(f"✅ ¡Mágia aplicada! Artículo {articulo_id} actualizado a {nuevo_estado.value}")
        except Exception as e:
            session.rollback()
            logging.error(f"Error actualizando DB: {e}")
        finally:
            session.close()

def check_and_archive_history():
    """
    Mantenimiento automático: mueve archivos completados del día anterior a Historial_Diario/[DIA].
    Si cambia el mes, consolida el Historial_Diario del mes anterior al Historial Global Mensual.
    Este proceso es autocurativo y se pondrá al día incluso si el servidor estuvo apagado.
    """
    session = Session()
    try:
        from datetime import datetime, timedelta
        import shutil
        
        # 1. Obtener la fecha del último archivado
        config_db = session.query(Configuracion).filter_by(clave='ultimo_archivo_diario').first()
        hoy = datetime.now().date()
        
        if not config_db:
            # Inicializar con la fecha de ayer
            ayer = hoy - timedelta(days=1)
            config_db = Configuracion(clave='ultimo_archivo_diario', valor=ayer.isoformat())
            session.add(config_db)
            session.commit()
            logging.info(f"📁 Inicializado registro de archivado diario con fecha: {ayer.isoformat()}")
            return
            
        ultimo_registro = datetime.strptime(config_db.valor, "%Y-%m-%d").date()
        
        ayer = hoy - timedelta(days=1)
        if ultimo_registro >= ayer:
            return
            
        # 2. Iterar por cada día faltante (desde ultimo_registro + 1 día hasta ayer)
        dia_a_procesar = ultimo_registro + timedelta(days=1)
        maquinas = ['PLOTTER', 'PLOTTER_CORTE', 'IMPRESORA_UV', 'LASER', 'CNC']
        
        while dia_a_procesar <= ayer:
            dia_num = str(dia_a_procesar.day)
            meses = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
            mes_str = f"{dia_a_procesar.month:02d}{meses[dia_a_procesar.month - 1]}"
            anio_str = str(dia_a_procesar.year)
            
            for m in maquinas:
                completado_dir = os.path.join(WATCH_DIR, m, "Procesando", "Completado")
                if not os.path.exists(completado_dir):
                    continue
                    
                # Buscar archivos completados en esa fecha (según la fecha de modificación del archivo)
                archivos = []
                for f in os.listdir(completado_dir):
                    ruta_f = os.path.join(completado_dir, f)
                    if os.path.isfile(ruta_f):
                        mtime = datetime.fromtimestamp(os.path.getmtime(ruta_f)).date()
                        if mtime == dia_a_procesar:
                            archivos.append(f)
                            
                if archivos:
                    # Crear subcarpeta Historial_Diario/[DIA]
                    historial_diario_dir = os.path.join(completado_dir, "Historial_Diario", dia_num)
                    os.makedirs(historial_diario_dir, exist_ok=True)
                    
                    for archivo in archivos:
                        ruta_origen = os.path.join(completado_dir, archivo)
                        ruta_destino = os.path.join(historial_diario_dir, archivo)
                        try:
                            shutil.move(ruta_origen, ruta_destino)
                            logging.info(f"📁 Archivado diario [{dia_a_procesar.isoformat()}]: {archivo} -> Historial Diario {dia_num}")
                        except Exception as e:
                            logging.error(f"Error al archivar {archivo} para fecha {dia_a_procesar.isoformat()}: {e}")
                            
            # 3. Consolidación Mensual: Si el siguiente día es el primer día de un nuevo mes,
            # consolidamos todo el Historial_Diario del mes que acaba de cerrar al Historial Global.
            siguiente_dia = dia_a_procesar + timedelta(days=1)
            if siguiente_dia.month != dia_a_procesar.month:
                logging.info(f"📅 Cierre de mes detectado ({mes_str}). Consolidando historial mensual...")
                for m in maquinas:
                    historial_diario_root = os.path.join(WATCH_DIR, m, "Procesando", "Completado", "Historial_Diario")
                    if os.path.exists(historial_diario_root):
                        historial_global_dir = os.path.join(WATCH_DIR, "Historial", anio_str, mes_str, m)
                        os.makedirs(historial_global_dir, exist_ok=True)
                        
                        # Mover todos los días contenidos en Historial_Diario al Historial Global
                        for d in os.listdir(historial_diario_root):
                            ruta_origen_dia = os.path.join(historial_diario_root, d)
                            if os.path.isdir(ruta_origen_dia):
                                ruta_destino_dia = os.path.join(historial_global_dir, d)
                                try:
                                    if os.path.exists(ruta_destino_dia):
                                        for f_int in os.listdir(ruta_origen_dia):
                                            shutil.move(os.path.join(ruta_origen_dia, f_int), os.path.join(ruta_destino_dia, f_int))
                                        os.rmdir(ruta_origen_dia)
                                    else:
                                        shutil.move(ruta_origen_dia, ruta_destino_dia)
                                    logging.info(f"📅 Consolidado mensual global para {m}, día {d} a {historial_global_dir}")
                                except Exception as e:
                                    logging.error(f"Error consolidando mes para {m}, carpeta día {d}: {e}")
                                    
            dia_a_procesar = siguiente_dia
            
        config_db.valor = ayer.isoformat()
        session.commit()
        logging.info(f"✅ Mantenimiento de historial al día. Última fecha archivada: {ayer.isoformat()}")
    except Exception as e:
        session.rollback()
        logging.error(f"Error en mantenimiento de archivos históricos: {e}")
    finally:
        session.close()

def check_and_run_daily_backup():
    """
    Realiza un respaldo automático diario de la base de datos a partir de las 20:00 (8:00 PM).
    Persiste la fecha en la base de datos para no repetirlo si el servicio se reinicia.
    """
    from datetime import datetime
    ahora = datetime.now()
    if ahora.hour < 20:
        return

    session = Session()
    try:
        config_db = session.query(Configuracion).filter_by(clave='ultimo_respaldo_diario').first()
        hoy = ahora.date()
        
        if config_db:
            ultimo_respaldo = datetime.strptime(config_db.valor, "%Y-%m-%d").date()
            if ultimo_respaldo >= hoy:
                return
        else:
            config_db = Configuracion(clave='ultimo_respaldo_diario', valor='')
            session.add(config_db)
            
        logging.info("💾 Iniciando proceso de respaldo automático diario...")
        from respaldar_db import realizar_respaldo
        exito, ruta = realizar_respaldo()
        if exito:
            config_db.valor = hoy.isoformat()
            session.commit()
            logging.info(f"💾 Respaldo diario automático completado exitosamente: {ruta}")
        else:
            logging.error(f"❌ Falló el respaldo diario automático: {ruta}")
    except Exception as e:
        session.rollback()
        logging.error(f"❌ Error al ejecutar el respaldo diario automático: {e}")
    finally:
        session.close()

def enviar_latido_healthcheck():
    """
    Envía un ping silencioso a Healthchecks.io para indicar que el vigilante está activo.
    """
    if not HEALTHCHECK_URL:
        return
    import requests
    try:
        requests.get(HEALTHCHECK_URL, timeout=5)
        logging.info("💓 Latido enviado con éxito a Healthchecks.io")
    except Exception as e:
        logging.warning(f"No se pudo enviar el latido a Healthchecks: {e}")

if __name__ == "__main__":
    from file_manager import inicializar_carpetas_sistema
    inicializar_carpetas_sistema()
        
    event_handler = ProduccionEventHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=True)
    observer.start()
    
    logging.info(f"👁️  Guardián de Producción iniciado. Vigilando: {WATCH_DIR}")
    logging.info("Mueve archivos a 'Procesando' o 'Completado' para actualizar el estado.")
    
    # Ejecutar archivado inicial al arrancar
    check_and_archive_history()
    enviar_latido_healthcheck()
    check_and_run_daily_backup()
    
    ultimo_chequeo_mantenimiento = time.time()
    
    try:
        while True:
            time.sleep(1)
            # Ejecutar chequeo de mantenimiento cada 60 segundos
            ahora = time.time()
            if ahora - ultimo_chequeo_mantenimiento >= 60:
                check_and_archive_history()
                enviar_latido_healthcheck()
                check_and_run_daily_backup()
                ultimo_chequeo_mantenimiento = ahora
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
    except Exception as e:
        observer.stop()
        observer.join()
        logging.error(f"💥 Error crítico en el Guardián de Producción: {e}")
        raise e
