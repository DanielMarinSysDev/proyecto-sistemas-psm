#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import shutil
import logging
from sqlalchemy import text
from database_models import engine
from sqlalchemy.orm import sessionmaker
from file_manager import BASE_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("limpiar_produccion")

def limpiar_base_datos():
    """
    Vacía todas las tablas transaccionales de la base de datos (clientes, pedidos, 
    ordenes_trabajo, archivos_adjuntos, logs_auditoria, incidencias)
    manteniendo usuarios, configuraciones y la lista de precios de materiales.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        print("\n--- 1. LIMPIANDO BASE DE DATOS (TRANSACCIONAL) ---")
        
        # Eliminar registros respetando llaves foráneas en orden descendente de dependencia
        print("Eliminando incidencias...")
        session.execute(text("DELETE FROM incidencias;"))
        
        print("Eliminando logs de auditoría...")
        session.execute(text("DELETE FROM logs_auditoria;"))
        
        print("Eliminando archivos adjuntos...")
        session.execute(text("DELETE FROM archivos_adjuntos;"))
        
        print("Eliminando órdenes de trabajo (artículos)...")
        session.execute(text("DELETE FROM ordenes_trabajo;"))
        
        print("Eliminando pedidos...")
        session.execute(text("DELETE FROM pedidos;"))
        
        print("Eliminando clientes...")
        session.execute(text("DELETE FROM clientes;"))
        
        # Reiniciar secuencias de IDs en PostgreSQL para iniciar desde 1 en la próxima creación
        try:
            print("Reiniciando secuencias de autoincremento (PostgreSQL)...")
            session.execute(text("ALTER SEQUENCE clientes_id_seq RESTART WITH 1;"))
            session.execute(text("ALTER SEQUENCE pedidos_id_seq RESTART WITH 1;"))
            session.execute(text("ALTER SEQUENCE ordenes_trabajo_id_seq RESTART WITH 1;"))
            session.execute(text("ALTER SEQUENCE archivos_adjuntos_id_seq RESTART WITH 1;"))
            session.execute(text("ALTER SEQUENCE logs_auditoria_id_seq RESTART WITH 1;"))
            session.execute(text("ALTER SEQUENCE incidencias_id_seq RESTART WITH 1;"))
        except Exception:
            # Ignorar si es SQLite u otro motor que no soporta ALTER SEQUENCE
            pass
            
        session.commit()
        print("¡Base de datos transaccional limpia con éxito!")
    except Exception as e:
        session.rollback()
        print(f"Error limpiando base de datos: {e}")
    finally:
        session.close()

def vaciar_carpeta(ruta):
    """
    Elimina todos los archivos y subcarpetas dentro de un directorio sin eliminar el directorio base.
    """
    if os.path.exists(ruta):
        for elemento in os.listdir(ruta):
            ruta_elemento = os.path.join(ruta, elemento)
            try:
                if os.path.isfile(ruta_elemento) or os.path.islink(ruta_elemento):
                    os.unlink(ruta_elemento)
                elif os.path.isdir(ruta_elemento):
                    shutil.rmtree(ruta_elemento)
            except Exception as e:
                print(f"No se pudo eliminar {ruta_elemento}: {e}")

def limpiar_archivos_fisicos():
    """
    Elimina las carpetas físicas generadas por los pedidos y limpia las colas de producción,
    pero mantiene intactas las carpetas del flujo de trabajo de las máquinas.
    """
    print("\n--- 2. LIMPIANDO CARPETAS DE ARCHIVOS FÍSICOS ---")
    print(f"Ruta base actual: {BASE_DIR}")
    
    # 1. Limpiar Clientes_Master (carpetas permanentes de clientes)
    clientes_master = os.path.join(BASE_DIR, "Clientes_Master")
    vaciar_carpeta(clientes_master)
    print("✓ Clientes_Master vaciado (conservando directorio raíz).")
    
    # 2. Limpiar Produccion_Grafica (carpetas de pedidos y archivos de diseño)
    produccion_grafica = os.path.join(BASE_DIR, "Produccion_Grafica")
    vaciar_carpeta(produccion_grafica)
    print("✓ Produccion_Grafica vaciado (conservando directorio raíz).")
    
    # 3. Limpiar Cola_Produccion de todas las máquinas sin romper la estructura del flujo
    cola_produccion = os.path.join(BASE_DIR, "Cola_Produccion")
    if os.path.exists(cola_produccion):
        # Vaciar Historial
        historial_dir = os.path.join(cola_produccion, "Historial")
        vaciar_carpeta(historial_dir)
        
        # Vaciar colas de máquinas
        maquinas = ['PLOTTER', 'PLOTTER_CORTE', 'IMPRESORA_UV', 'LASER', 'CNC']
        for m in maquinas:
            m_dir = os.path.join(cola_produccion, m)
            if os.path.exists(m_dir):
                # Eliminar archivos sueltos en la raíz de la máquina
                for item in os.listdir(m_dir):
                    item_path = os.path.join(m_dir, item)
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                
                # Vaciar Procesando y subcarpetas manteniendo 'Completado' e 'Historial_Diario'
                procesando_dir = os.path.join(m_dir, "Procesando")
                if os.path.exists(procesando_dir):
                    for item in os.listdir(procesando_dir):
                        item_path = os.path.join(procesando_dir, item)
                        if item.lower() == "completado":
                            completado_dir = item_path
                            for c_item in os.listdir(completado_dir):
                                c_item_path = os.path.join(completado_dir, c_item)
                                if c_item.lower() == "historial_diario":
                                    vaciar_carpeta(c_item_path)
                                else:
                                    if os.path.isfile(c_item_path) or os.path.islink(c_item_path):
                                        os.unlink(c_item_path)
                                    elif os.path.isdir(c_item_path):
                                        shutil.rmtree(c_item_path)
                        else:
                            if os.path.isfile(item_path) or os.path.islink(item_path):
                                os.unlink(item_path)
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
        print("✓ Colas de Producción de máquinas limpiadas y estructuradas.")

if __name__ == "__main__":
    print("====================================================")
    print("  UTILIDAD DE LIMPIEZA DE ENTORNO DE PRODUCCIÓN     ")
    print("====================================================")
    confirmacion = input("¿Está seguro de vaciar todos los datos de prueba del sistema? (S/N): ")
    if confirmacion.upper() in ["S", "SI"]:
        limpiar_base_datos()
        limpiar_archivos_fisicos()
        print("\n====================================================")
        print("¡El entorno de producción se ha limpiado exitosamente!")
        print("====================================================")
    else:
        print("Operación cancelada por el usuario.")
