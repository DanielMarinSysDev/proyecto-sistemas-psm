import os
import sys
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database_models import (
    Base, Usuario, Cliente, Pedido, OrdenTrabajo, 
    Archivo, LogAuditoria, PrecioMaterial, Incidencia
)

def migrar():
    sqlite_url = "sqlite:///sistema_gestion_produccion.db"
    postgres_url = os.getenv("DATABASE_URL")
    
    if not postgres_url:
        print("ERROR: La variable de entorno DATABASE_URL no está configurada.")
        print("Ejemplo: DATABASE_URL=postgresql://user:pass@localhost:5432/db")
        sys.exit(1)
        
    print("--- INICIANDO MIGRACIÓN DE DATOS ---")
    print(f"Origen: {sqlite_url}")
    print(f"Destino: {postgres_url}")
    
    # Crear engines y sessions
    sqlite_engine = create_engine(sqlite_url)
    postgres_engine = create_engine(postgres_url)
    
    SqliteSession = sessionmaker(bind=sqlite_engine)
    PostgresSession = sessionmaker(bind=postgres_engine)
    
    sqlite_session = SqliteSession()
    postgres_session = PostgresSession()
    
    try:
        # 1. Crear las tablas en PostgreSQL si no existen
        print("\nCreando estructuras de tablas en PostgreSQL...")
        Base.metadata.create_all(postgres_engine)
        print("Estructuras creadas/verificadas.")
        
        # Lista de tablas en orden correcto de dependencias (para claves foráneas)
        tablas_a_migrar = [
            (Usuario, "usuarios"),
            (Cliente, "clientes"),
            (Pedido, "pedidos"),
            (OrdenTrabajo, "ordenes_trabajo"),
            (Archivo, "archivos_adjuntos"),
            (LogAuditoria, "logs_auditoria"),
            (PrecioMaterial, "precios_materiales"),
            (Incidencia, "incidencias")
        ]
        
        # 2. Migrar datos tabla por tabla
        for modelo, nombre_tabla in tablas_a_migrar:
            print(f"\nMigrando tabla '{nombre_tabla}'...")
            
            # Limpiar datos previos en PostgreSQL para evitar duplicados si se re-ejecuta
            postgres_session.execute(text(f"TRUNCATE TABLE {nombre_tabla} RESTART IDENTITY CASCADE;"))
            postgres_session.commit()
            
            # Obtener registros de SQLite
            registros = sqlite_session.query(modelo).all()
            total = len(registros)
            
            if total == 0:
                print(f"  Sin registros para migrar en '{nombre_tabla}'.")
                continue
                
            # Clonar registros a la nueva sesión
            for reg in registros:
                # Hacer expunge del registro de SQLite para poder añadirlo a Postgres
                sqlite_session.expunge(reg)
                # Hacer que SQLAlchemy lo detecte como nuevo pero manteniendo el ID original
                postgres_session.merge(reg)
                
            postgres_session.commit()
            print(f"  ¡Éxito! Se migraron {total} registros en '{nombre_tabla}'.")
            
        # 3. Corregir y sincronizar secuencias autoincrementables (SERIAL) en PostgreSQL
        print("\nSincronizando secuencias autoincrementables en PostgreSQL...")
        for _, nombre_tabla in tablas_a_migrar:
            # Consultar si la secuencia existe y poner el valor actual al máximo ID de la tabla + 1
            query_seq = f"""
                SELECT setval(
                    pg_get_serial_sequence('{nombre_tabla}', 'id'),
                    COALESCE((SELECT MAX(id)+1 FROM {nombre_tabla}), 1),
                    false
                );
            """
            try:
                postgres_session.execute(text(query_seq))
                postgres_session.commit()
                print(f"  Secuencia de '{nombre_tabla}' sincronizada.")
            except Exception as seq_err:
                postgres_session.rollback()
                print(f"  (Aviso) No se pudo actualizar secuencia para '{nombre_tabla}': {seq_err}")
                
        print("\n--- ¡MIGRACIÓN COMPLETADA EXITOSAMENTE! ---")
        
    except Exception as e:
        sqlite_session.rollback()
        postgres_session.rollback()
        print(f"\n❌ Ocurrió un error crítico durante la migración: {e}")
        sys.exit(1)
    finally:
        sqlite_session.close()
        postgres_session.close()

if __name__ == "__main__":
    migrar()
